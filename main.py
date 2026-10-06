from __future__ import annotations

import math
import sys
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from geometry import (
    FigureHit,
    Intersection,
    Point,
    analyze_figures,
    distance_to_segment,
    classify_side,
    format_intersection,
    format_matrix,
    format_membership,
    format_side,
    intersect_segments,
    intersection_brief,
    marker_label,
    polygon_center,
    polygon_kind,
    rotation_about_point,
    scaling_about_point,
    transform_points,
    translation,
)

if sys.platform == "win32":
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass

CANVAS_W = 860
CANVAS_H = 600
ORIGIN_X = CANVAS_W // 2
ORIGIN_Y = CANVAS_H // 2
EDGE_PICK = 8.0
MOUSE_TOL = 0.5

COLORS = (
    "#1d4ed8",
    "#c2410c",
    "#047857",
    "#be185d",
    "#6d28d9",
    "#0e7490",
    "#a16207",
    "#b91c1c",
)
FILLS = {
    "#1d4ed8": "#dbeafe",
    "#c2410c": "#ffedd5",
    "#047857": "#d1fae5",
    "#be185d": "#fce7f3",
    "#6d28d9": "#ede9fe",
    "#0e7490": "#cffafe",
    "#a16207": "#fef3c7",
    "#b91c1c": "#fee2e2",
}

HELP = {
    "draw": (
        "Левая кнопка добавляет вершину. Правая кнопка или Enter завершает фигуру. "
        "Одна вершина — точка, две — ребро, три и больше — замкнутый полигон. "
        "Backspace убирает последнюю вершину."
    ),
    "intersect": (
        "Два щелчка задают первое ребро, либо один щелчок по уже нарисованному ребру. "
        "Дальше два щелчка задают второе ребро: пока ведёте мышь, пересечение считается сразу. "
        "Следующий щелчок начинает новое второе ребро. Правая кнопка сбрасывает только рёбра пробы."
    ),
    "inside": (
        "Каждый щелчок проверяет точку. Для выпуклого полигона — полуплоскости, "
        "для любого — метод лучей. Сцену очищать и режим переключать не нужно."
    ),
    "side": (
        "Щёлкните ребро фигуры или задайте его двумя щелчками. "
        "Следующие щелчки отвечают, слева точка или справа. "
        "Другое ребро выбирается новым щелчком по нему, режим менять не нужно."
    ),
}


@dataclass
class Polygon:
    points: list[Point]
    color: str


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("ЛР4 — аффинные преобразования")
        self.root.minsize(1120, 640)
        self.polygons: list[Polygon] = []
        self.selected: int | None = None
        self.draft: list[Point] = []
        self.rubber: Point | None = None
        self.history: list[tuple[list[Polygon], int | None]] = []
        self.pivot: Point | None = None
        self.awaiting_pivot = False
        self.pending: tuple[str, tuple[float, ...]] | None = None
        self.probe_a: Point | None = None
        self.probe_b: Point | None = None
        self.probe_c: Point | None = None
        self.probe_d: Point | None = None
        self.probe_live: str | None = None
        self.side_a: Point | None = None
        self.side_b: Point | None = None
        self.side_live: str | None = None
        self.side_points: list[Point] = []
        self.inside_points: list[Point] = []
        self._updating_list = False
        self.mode = "draw"
        self._build()
        self.message_var.set("Щёлкните холст, чтобы поставить вершину.")
        self.redraw()

    def _build(self) -> None:
        status = ttk.Frame(self.root, padding=(8, 4))
        status.pack(side=tk.BOTTOM, fill=tk.X)
        self.message_var = tk.StringVar()
        self.coords_var = tk.StringVar(value="x = —    y = —")
        ttk.Label(status, textvariable=self.message_var).pack(side=tk.LEFT)
        ttk.Label(status, textvariable=self.coords_var).pack(side=tk.RIGHT)

        body = ttk.Frame(self.root)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(
            body,
            width=CANVAS_W,
            height=CANVAS_H,
            bg="#f8fafc",
            highlightthickness=1,
            highlightbackground="#cbd5e1",
        )
        self.canvas.pack(side=tk.LEFT)
        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<Button-3>", self.on_right_click)

        panel = ttk.Frame(body, padding=8)
        panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        ttk.Label(panel, text="Лабораторная работа 4", font=("Segoe UI", 12, "bold")).pack(anchor=tk.W)
        ttk.Label(
            panel,
            text="Аффинные преобразования и векторные алгоритмы",
            wraplength=320,
        ).pack(anchor=tk.W, pady=(0, 6))

        self.mode_var = tk.StringVar(value="draw")
        modes = ttk.LabelFrame(panel, text="Режим", padding=6)
        modes.pack(fill=tk.X)
        for value, title in (
            ("draw", "Рисование полигона"),
            ("intersect", "Пересечение рёбер"),
            ("inside", "Принадлежность точки"),
            ("side", "Слева или справа от ребра"),
        ):
            ttk.Radiobutton(
                modes,
                text=title,
                value=value,
                variable=self.mode_var,
                command=self.on_mode_changed,
            ).pack(anchor=tk.W)

        self.help_var = tk.StringVar(value=HELP["draw"])
        ttk.Label(panel, textvariable=self.help_var, wraplength=320, justify=tk.LEFT).pack(
            anchor=tk.W, pady=6
        )

        buttons = ttk.Frame(panel)
        buttons.pack(fill=tk.X)
        ttk.Button(buttons, text="Завершить фигуру", command=self.finish_polygon).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        ttk.Button(buttons, text="Очистить сцену", command=self.clear_scene).pack(side=tk.LEFT)
        row2 = ttk.Frame(panel)
        row2.pack(fill=tk.X, pady=4)
        ttk.Button(row2, text="Удалить выбранную", command=self.delete_selected).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        ttk.Button(row2, text="Отменить", command=self.undo).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(row2, text="Сбросить построения", command=self.clear_overlays).pack(side=tk.LEFT)

        ttk.Label(panel, text="Фигуры").pack(anchor=tk.W, pady=(6, 0))
        self.listbox = tk.Listbox(panel, height=5, exportselection=False, font=("Segoe UI", 9))
        self.listbox.pack(fill=tk.X)
        self.listbox.bind("<<ListboxSelect>>", self.on_list_select)

        transforms = ttk.LabelFrame(panel, text="Аффинные преобразования выбранной фигуры", padding=6)
        transforms.pack(fill=tk.X, pady=8)
        self.dx_var = tk.StringVar(value="40")
        self.dy_var = tk.StringVar(value="0")
        self.angle_var = tk.StringVar(value="45")
        self.alpha_var = tk.StringVar(value="1.5")
        self.delta_var = tk.StringVar(value="1.5")
        self._row(transforms, 0, "dx", self.dx_var, "dy", self.dy_var, "Сместить", self.translate)
        ttk.Label(transforms, text="dy > 0 — вверх, φ > 0 — против часовой").grid(
            row=1, column=0, columnspan=5, sticky=tk.W
        )
        ttk.Label(transforms, text="φ°").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(transforms, textvariable=self.angle_var, width=7).grid(row=2, column=1, sticky=tk.EW, padx=2)
        ttk.Button(transforms, text="Вокруг центра", command=self.rotate_center).grid(
            row=2, column=2, columnspan=2, sticky=tk.EW, padx=2
        )
        ttk.Button(transforms, text="Вокруг точки", command=self.rotate_point).grid(
            row=2, column=4, sticky=tk.EW, padx=2
        )
        self._row(transforms, 3, "α", self.alpha_var, "δ", self.delta_var, "От центра", self.scale_center)
        ttk.Button(transforms, text="От точки", command=self.scale_point).grid(
            row=4, column=4, sticky=tk.EW, padx=2, pady=2
        )
        ttk.Button(transforms, text="Задать точку A", command=self.arm_pivot).grid(
            row=4, column=0, columnspan=2, sticky=tk.EW, pady=2
        )
        self.pivot_var = tk.StringVar(value="Точка A не задана")
        ttk.Label(transforms, textvariable=self.pivot_var).grid(row=4, column=2, columnspan=2, sticky=tk.W)
        for column in range(5):
            transforms.columnconfigure(column, weight=1)

        journal = ttk.LabelFrame(panel, text="Журнал", padding=4)
        journal.pack(fill=tk.BOTH, expand=True)
        self.log = ScrolledText(journal, height=12, font=("Consolas", 9), wrap=tk.WORD)
        self.log.pack(fill=tk.BOTH, expand=True)
        ttk.Button(journal, text="Очистить журнал", command=self.clear_log).pack(anchor=tk.E, pady=(4, 0))

        self.root.bind("<Return>", self.on_return)
        self.root.bind("<Escape>", self.on_escape)
        self.root.bind("<BackSpace>", self.on_backspace)
        self.root.bind("<Control-z>", lambda _event: self.undo())
        self.root.bind("<Control-Z>", lambda _event: self.undo())

    def _row(
        self,
        parent: ttk.LabelFrame,
        row: int,
        label_a: str,
        var_a: tk.StringVar,
        label_b: str | None,
        var_b: tk.StringVar | None,
        button: str,
        command,
    ) -> None:
        ttk.Label(parent, text=label_a).grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(parent, textvariable=var_a, width=7).grid(row=row, column=1, sticky=tk.EW, padx=2)
        if label_b is not None and var_b is not None:
            ttk.Label(parent, text=label_b).grid(row=row, column=2, sticky=tk.W)
            ttk.Entry(parent, textvariable=var_b, width=7).grid(row=row, column=3, sticky=tk.EW, padx=2)
        ttk.Button(parent, text=button, command=command).grid(row=row, column=4, sticky=tk.EW, padx=2)

    def to_math(self, screen_x: float, screen_y: float) -> Point:
        return (screen_x - ORIGIN_X, ORIGIN_Y - screen_y)

    def to_screen(self, point: Point) -> tuple[float, float]:
        return (ORIGIN_X + point[0], ORIGIN_Y - point[1])

    def on_mode_changed(self) -> None:
        self.mode = self.mode_var.get()
        self.help_var.set(HELP[self.mode])
        self.redraw()

    def on_motion(self, event: tk.Event) -> None:
        point = self.to_math(event.x, event.y)
        self.coords_var.set(f"x = {point[0]:.1f}    y = {point[1]:.1f}")
        self.rubber = point
        if self.mode == "draw" and self.draft:
            self.redraw()
        elif self.mode == "intersect" and self.probe_live:
            self.redraw()
            self._show_live_intersection()
        elif self.mode == "side" and self.side_live:
            self.redraw()

    def on_left_click(self, event: tk.Event) -> None:
        self.canvas.focus_set()
        point = self.to_math(event.x, event.y)
        if self.awaiting_pivot:
            self._accept_pivot(point)
            return
        if self.mode == "draw":
            self._add_vertex(point)
        elif self.mode == "intersect":
            self._intersect_click(point)
        elif self.mode == "inside":
            self._inside_click(point)
        elif self.mode == "side":
            self._side_click(point)
        self.redraw()

    def on_right_click(self, event: tk.Event) -> str:
        if self.mode == "draw":
            self.finish_polygon()
        elif self.mode == "intersect":
            self.probe_a = self.probe_b = self.probe_c = self.probe_d = None
            self.probe_live = None
            self.message_var.set("Рёбра пробы сброшены. Задайте первое заново, полигоны на месте.")
            self.redraw()
        elif self.mode == "side":
            self.side_a = self.side_b = None
            self.side_live = None
            self.side_points.clear()
            self.message_var.set("Опорное ребро сброшено. Выберите другое, полигоны на месте.")
            self.redraw()
        return "break"

    def on_return(self, _event: tk.Event) -> None:
        if self._typing() or self.mode != "draw":
            return
        self.finish_polygon()

    def on_escape(self, _event: tk.Event) -> None:
        if self._typing():
            return
        if self.awaiting_pivot:
            self.awaiting_pivot = False
            self.pending = None
            self.message_var.set("Выбор точки A отменён.")
            return
        if self.mode == "draw" and self.draft:
            self.draft.pop()
            self.message_var.set("Последняя вершина убрана.")
            self.redraw()
        elif self.mode == "intersect" and self.probe_live:
            self._cancel_probe_live()
        elif self.mode == "side" and self.side_live:
            self.side_a = None
            self.side_live = None
            self.message_var.set("Ребро не задано.")
            self.redraw()

    def on_backspace(self, _event: tk.Event) -> None:
        if self._typing() or self.mode != "draw" or not self.draft:
            return
        self.draft.pop()
        self.message_var.set("Последняя вершина убрана.")
        self.redraw()

    def _typing(self) -> bool:
        widget = self.root.focus_get()
        if widget is None:
            return False
        return widget.winfo_class() in {"Entry", "TEntry", "Text"}

    def _add_vertex(self, point: Point) -> None:
        if self.draft:
            last = self.draft[-1]
            if math.hypot(point[0] - last[0], point[1] - last[1]) < 2.0:
                return
        self.draft.append(point)
        self.message_var.set(
            f"Вершина {len(self.draft)}. Правая кнопка или Enter завершает фигуру."
        )

    def finish_polygon(self) -> None:
        if not self.draft:
            self.message_var.set("Нет вершин: щёлкните по холсту.")
            return
        self._push()
        color = COLORS[len(self.polygons) % len(COLORS)]
        self.polygons.append(Polygon([tuple(point) for point in self.draft], color))
        self.selected = len(self.polygons) - 1
        kind = polygon_kind(self.polygons[-1].points)
        self.draft.clear()
        self._sync_list()
        self.message_var.set(f"Фигура {self.selected + 1}: {kind}.")
        self._log(f"Добавлена фигура {self.selected + 1}: {kind}, вершин {len(self.polygons[-1].points)}.")
        self.redraw()

    def clear_scene(self) -> None:
        self._push()
        self.polygons.clear()
        self.selected = None
        self.draft.clear()
        self.pivot = None
        self.awaiting_pivot = False
        self.pending = None
        self.pivot_var.set("Точка A не задана")
        self.clear_overlays(record=False)
        self._sync_list()
        self.message_var.set("Сцена очищена.")
        self._log("Сцена очищена.")
        self.redraw()

    def clear_overlays(self, record: bool = True) -> None:
        self.probe_a = self.probe_b = self.probe_c = self.probe_d = None
        self.probe_live = None
        self.side_a = self.side_b = None
        self.side_live = None
        self.side_points.clear()
        self.inside_points.clear()
        if record:
            self.message_var.set("Вспомогательные рёбра и отметки сброшены, фигуры на месте.")
            self.redraw()

    def delete_selected(self) -> None:
        if self.selected is None or not (0 <= self.selected < len(self.polygons)):
            self.message_var.set("Сначала выберите фигуру в списке.")
            return
        self._push()
        number = self.selected + 1
        del self.polygons[self.selected]
        self.selected = min(self.selected, len(self.polygons) - 1) if self.polygons else None
        self._sync_list()
        self.message_var.set(f"Фигура {number} удалена.")
        self.redraw()

    def undo(self) -> None:
        if self._typing() and self.root.focus_get() is not self.canvas:
            return
        if not self.history:
            self.message_var.set("Отменять нечего.")
            return
        self.polygons, self.selected = self.history.pop()
        self._sync_list()
        self.message_var.set("Последнее действие отменено.")
        self.redraw()

    def _push(self) -> None:
        snapshot = [Polygon([tuple(point) for point in poly.points], poly.color) for poly in self.polygons]
        self.history.append((snapshot, self.selected))
        if len(self.history) > 40:
            self.history.pop(0)

    def on_list_select(self, _event: tk.Event) -> None:
        if self._updating_list:
            return
        chosen = self.listbox.curselection()
        self.selected = chosen[0] if chosen else None
        self.redraw()

    def _sync_list(self) -> None:
        self._updating_list = True
        self.listbox.delete(0, tk.END)
        for index, poly in enumerate(self.polygons, start=1):
            self.listbox.insert(tk.END, f"{index}. {polygon_kind(poly.points)}, вершин {len(poly.points)}")
        if self.selected is not None and 0 <= self.selected < len(self.polygons):
            self.listbox.selection_set(self.selected)
            self.listbox.see(self.selected)
        self._updating_list = False

    def _current(self) -> Polygon | None:
        if self.selected is None or not (0 <= self.selected < len(self.polygons)):
            return None
        return self.polygons[self.selected]

    def _read_float(self, var: tk.StringVar, title: str) -> float | None:
        raw = var.get().strip().replace(",", ".")
        try:
            return float(raw)
        except ValueError:
            self.message_var.set(f"Некорректное число в поле «{title}».")
            return None

    def translate(self) -> None:
        dx = self._read_float(self.dx_var, "dx")
        dy = self._read_float(self.dy_var, "dy")
        if dx is None or dy is None:
            return
        matrix = translation(dx, dy)
        self._apply(matrix, f"Смещение на dx = {dx:g}, dy = {dy:g}\nM = T\n{format_matrix(matrix)}")

    def rotate_center(self) -> None:
        degrees = self._read_float(self.angle_var, "φ")
        poly = self._current()
        if degrees is None or poly is None:
            if poly is None:
                self.message_var.set("Сначала выберите фигуру в списке.")
            return
        center = polygon_center(poly.points)
        self._rotate(degrees, center, "своего центра")

    def rotate_point(self) -> None:
        degrees = self._read_float(self.angle_var, "φ")
        if degrees is None:
            return
        if self.pivot is None:
            self.pending = ("rotate", (degrees,))
            self.awaiting_pivot = True
            self.message_var.set("Щёлкните точку A — вокруг неё выполнится поворот.")
            return
        self._rotate(degrees, self.pivot, "точки A")

    def scale_center(self) -> None:
        factors = self._read_scale()
        poly = self._current()
        if factors is None or poly is None:
            if factors is not None and poly is None:
                self.message_var.set("Сначала выберите фигуру в списке.")
            return
        self._scale(factors[0], factors[1], polygon_center(poly.points), "своего центра")

    def scale_point(self) -> None:
        factors = self._read_scale()
        if factors is None:
            return
        if self.pivot is None:
            self.pending = ("scale", factors)
            self.awaiting_pivot = True
            self.message_var.set("Щёлкните точку A — относительно неё выполнится масштаб.")
            return
        self._scale(factors[0], factors[1], self.pivot, "точки A")

    def _read_scale(self) -> tuple[float, float] | None:
        alpha = self._read_float(self.alpha_var, "α")
        delta = self._read_float(self.delta_var, "δ")
        if alpha is None or delta is None:
            return None
        return alpha, delta

    def arm_pivot(self) -> None:
        self.awaiting_pivot = not self.awaiting_pivot
        self.pending = None
        self.message_var.set(
            "Следующий щелчок задаёт точку A и не добавляет вершину."
            if self.awaiting_pivot
            else "Выбор точки A отменён."
        )

    def _accept_pivot(self, point: Point) -> None:
        self.pivot = point
        self.awaiting_pivot = False
        self.pivot_var.set(f"A = ({point[0]:.2f}, {point[1]:.2f})")
        pending = self.pending
        self.pending = None
        self.message_var.set(f"Точка A: ({point[0]:.2f}, {point[1]:.2f}).")
        self.redraw()
        if pending is None:
            return
        kind, values = pending
        if kind == "rotate":
            self._rotate(values[0], point, "точки A")
        else:
            self._scale(values[0], values[1], point, "точки A")

    def _rotate(self, degrees: float, center: Point, about: str) -> None:
        phi = math.radians(degrees)
        matrix = rotation_about_point(center[0], center[1], phi)
        self._apply(
            matrix,
            "Поворот на "
            f"{degrees:g}° вокруг {about} ({center[0]:.2f}, {center[1]:.2f})\n"
            "M = T_(−A) · R · T_A\n"
            f"{format_matrix(matrix)}",
        )

    def _scale(self, alpha: float, delta: float, center: Point, about: str) -> None:
        matrix = scaling_about_point(center[0], center[1], alpha, delta)
        self._apply(
            matrix,
            f"Масштаб α = {alpha:g}, δ = {delta:g} относительно {about} "
            f"({center[0]:.2f}, {center[1]:.2f})\n"
            "M = T_(−A) · D · T_A\n"
            f"{format_matrix(matrix)}",
        )

    def _apply(self, matrix, description: str) -> None:
        poly = self._current()
        if poly is None:
            self.message_var.set("Сначала выберите фигуру в списке.")
            return
        self._push()
        poly.points = transform_points(matrix, poly.points)
        number = (self.selected or 0) + 1
        self._sync_list()
        self.message_var.set(f"Преобразование применено к фигуре {number}.")
        self._log(f"Фигура {number}. {description}")
        self.redraw()

    def _iter_edges(self):
        for poly in self.polygons:
            count = len(poly.points)
            if count == 2:
                yield poly.points[0], poly.points[1]
            elif count >= 3:
                for index in range(count):
                    yield poly.points[index], poly.points[(index + 1) % count]

    def _pick_edge(self, point: Point) -> tuple[Point, Point] | None:
        best: tuple[Point, Point] | None = None
        best_distance = EDGE_PICK
        for start, end in self._iter_edges():
            distance = distance_to_segment(start, end, point)
            if distance <= best_distance:
                best_distance = distance
                best = (tuple(start), tuple(end))
        return best

    def _intersect_click(self, point: Point) -> None:
        if self.probe_live == "b":
            self.probe_b = point
            self.probe_live = None
            self.message_var.set("Первое ребро зафиксировано. Щёлкните начало второго.")
            return
        if self.probe_live == "d":
            self.probe_d = point
            self.probe_live = None
            self._log_fixed_intersection()
            self.message_var.set("Второе ребро зафиксировано. Следующий щелчок начнёт новое.")
            return
        if self.probe_a is None:
            picked = self._pick_edge(point)
            if picked is not None:
                self.probe_a, self.probe_b = picked
                self.probe_c = self.probe_d = None
                self.message_var.set("Первое ребро взято с фигуры. Щёлкните начало второго.")
                return
            self.probe_a = point
            self.probe_live = "b"
            self.message_var.set("Щёлкните конец первого ребра.")
            return
        self.probe_c = point
        self.probe_d = None
        self.probe_live = "d"
        self.message_var.set("Ведите второе ребро: пересечение обновляется вместе с мышью.")

    def _cancel_probe_live(self) -> None:
        if self.probe_live == "b":
            self.probe_a = None
            self.probe_b = None
        elif self.probe_live == "d":
            self.probe_c = None
        self.probe_live = None
        self.message_var.set("Текущее ребро отменено.")
        self.redraw()

    def _probe_pair(self) -> tuple[tuple[Point, Point] | None, tuple[Point, Point] | None]:
        first = None
        second = None
        if self.probe_a is not None:
            if self.probe_live == "b" and self.rubber is not None:
                first = (self.probe_a, self.rubber)
            elif self.probe_b is not None:
                first = (self.probe_a, self.probe_b)
        if self.probe_c is not None:
            if self.probe_live == "d" and self.rubber is not None:
                second = (self.probe_c, self.rubber)
            elif self.probe_d is not None:
                second = (self.probe_c, self.probe_d)
        return first, second

    def _current_intersection(self) -> Intersection | None:
        first, second = self._probe_pair()
        if first is None or second is None:
            return None
        return intersect_segments(first[0], first[1], second[0], second[1])

    def _show_live_intersection(self) -> None:
        hit = self._current_intersection()
        if hit is not None:
            self.message_var.set(intersection_brief(hit))

    def _log_fixed_intersection(self) -> None:
        first, second = self._probe_pair()
        if first is None or second is None:
            return
        hit = intersect_segments(first[0], first[1], second[0], second[1])
        self._log(format_intersection(first[0], first[1], second[0], second[1], hit))
        self.message_var.set(intersection_brief(hit))

    def _side_edge(self) -> tuple[Point, Point] | None:
        if self.side_a is None:
            return None
        if self.side_live == "b" and self.rubber is not None:
            return self.side_a, self.rubber
        if self.side_b is not None:
            return self.side_a, self.side_b
        return None

    def _side_click(self, point: Point) -> None:
        if self.side_live == "b":
            self.side_b = point
            self.side_live = None
            self.message_var.set("Ребро задано. Следующие щелчки классифицируют точки.")
            return
        if self.side_a is None:
            picked = self._pick_edge(point)
            if picked is not None:
                self.side_a, self.side_b = picked
                self.message_var.set("Ребро фигуры выбрано. Щёлкайте точки.")
                return
            self.side_a = point
            self.side_live = "b"
            self.message_var.set("Щёлкните конец ребра.")
            return
        assert self.side_b is not None
        picked = self._pick_edge(point)
        if picked is not None and not _same_edge(picked, (self.side_a, self.side_b)):
            self.side_a, self.side_b = picked
            self.side_points.clear()
            self.message_var.set("Выбрано другое ребро. Щёлкайте точки относительно него.")
            return
        self.side_points.append(point)
        side = classify_side(self.side_a, self.side_b, point, MOUSE_TOL)
        self._log(format_side(self.side_a, self.side_b, point, side))
        names = {"left": "слева", "right": "справа", "on": "на прямой"}
        self.message_var.set(f"Точка {names[side.kind]}. Можно щёлкнуть следующую.")

    def _inside_click(self, point: Point) -> None:
        self.inside_points.append(point)
        polygons = [poly.points for poly in self.polygons]
        hits = analyze_figures(polygons, point, MOUSE_TOL)
        self._log(format_membership(hits, point))
        self.message_var.set(f"Точка: {marker_label(hits)}. Подробности в журнале.")

    def _log(self, text: str) -> None:
        self.log.insert(tk.END, text.rstrip() + "\n\n")
        self.log.see(tk.END)

    def clear_log(self) -> None:
        self.log.delete("1.0", tk.END)

    def redraw(self) -> None:
        self.canvas.delete("all")
        self._draw_background()
        for index, poly in enumerate(self.polygons):
            self._draw_polygon(poly, index == self.selected)
        self._draw_draft()
        self._draw_pivot()
        if self.mode == "intersect":
            self._draw_intersection()
        elif self.mode == "side":
            self._draw_side()
        elif self.mode == "inside":
            self._draw_inside()

    def _draw_background(self) -> None:
        step = 40
        x = math.floor((-ORIGIN_X) / step) * step
        while x <= CANVAS_W - ORIGIN_X:
            sx, _sy = self.to_screen((x, 0))
            self.canvas.create_line(sx, 0, sx, CANVAS_H, fill="#e7eef6")
            x += step
        y = math.floor((ORIGIN_Y - CANVAS_H) / step) * step
        while y <= ORIGIN_Y:
            _sx, sy = self.to_screen((0, y))
            self.canvas.create_line(0, sy, CANVAS_W, sy, fill="#e7eef6")
            y += step
        self.canvas.create_line(0, ORIGIN_Y, CANVAS_W - 12, ORIGIN_Y, arrow=tk.LAST, fill="#64748b", width=1.5)
        self.canvas.create_line(ORIGIN_X, CANVAS_H, ORIGIN_X, 12, arrow=tk.LAST, fill="#64748b", width=1.5)
        self.canvas.create_text(CANVAS_W - 16, ORIGIN_Y - 12, text="X", fill="#334155", font=("Segoe UI", 10, "bold"))
        self.canvas.create_text(ORIGIN_X + 14, 16, text="Y", fill="#334155", font=("Segoe UI", 10, "bold"))
        self.canvas.create_text(ORIGIN_X - 12, ORIGIN_Y + 12, text="O", fill="#64748b", font=("Segoe UI", 9))
        for value in range(-400, 401, 100):
            if value == 0:
                continue
            sx, sy = self.to_screen((value, 0))
            if 0 <= sx <= CANVAS_W:
                self.canvas.create_text(sx, sy + 12, text=str(value), fill="#94a3b8", font=("Segoe UI", 8))
            sx, sy = self.to_screen((0, value))
            if 0 <= sy <= CANVAS_H:
                self.canvas.create_text(sx - 16, sy, text=str(value), fill="#94a3b8", font=("Segoe UI", 8))

    def _draw_polygon(self, poly: Polygon, selected: bool) -> None:
        points = poly.points
        count = len(points)
        width = 3 if selected else 2
        if count >= 3:
            flat: list[float] = []
            for point in points:
                sx, sy = self.to_screen(point)
                flat.extend((sx, sy))
            self.canvas.create_polygon(*flat, fill=FILLS[poly.color], outline="")
        if count == 2:
            self._arrow(points[0], points[1], poly.color, width)
        elif count >= 3:
            for index in range(count):
                self._arrow(points[index], points[(index + 1) % count], poly.color, width)
        for index, point in enumerate(points, start=1):
            sx, sy = self.to_screen(point)
            radius = 5 if count == 1 else 4
            self.canvas.create_oval(sx - radius, sy - radius, sx + radius, sy + radius, fill=poly.color, outline="white")
            self.canvas.create_text(sx + 10, sy - 10, text=str(index), fill=poly.color, font=("Segoe UI", 9, "bold"))
        if selected and points:
            center = polygon_center(points)
            sx, sy = self.to_screen(center)
            self.canvas.create_line(sx - 6, sy, sx + 6, sy, fill=poly.color)
            self.canvas.create_line(sx, sy - 6, sx, sy + 6, fill=poly.color)
            self.canvas.create_text(sx + 12, sy + 10, text="C", fill=poly.color, font=("Segoe UI", 8, "bold"))

    def _arrow(self, start: Point, end: Point, color: str, width: int) -> None:
        x1, y1 = self.to_screen(start)
        x2, y2 = self.to_screen(end)
        self.canvas.create_line(x1, y1, x2, y2, fill=color, width=width, arrow=tk.LAST, arrowshape=(10, 12, 4))

    def _draw_draft(self) -> None:
        if not self.draft:
            return
        screen = [self.to_screen(point) for point in self.draft]
        if len(screen) >= 2:
            flat: list[float] = []
            for sx, sy in screen:
                flat.extend((sx, sy))
            self.canvas.create_line(*flat, fill="#334155", dash=(4, 3), width=2)
        if self.mode == "draw" and self.rubber is not None:
            sx, sy = self.to_screen(self.rubber)
            lx, ly = screen[-1]
            self.canvas.create_line(lx, ly, sx, sy, fill="#64748b", dash=(3, 3))
            if len(self.draft) >= 2:
                fx, fy = screen[0]
                self.canvas.create_line(sx, sy, fx, fy, fill="#94a3b8", dash=(2, 4))
        for index, (sx, sy) in enumerate(screen, start=1):
            self.canvas.create_oval(sx - 4, sy - 4, sx + 4, sy + 4, fill="#0f172a", outline="white")
            self.canvas.create_text(sx + 10, sy - 10, text=str(index), fill="#0f172a", font=("Segoe UI", 9))

    def _draw_pivot(self) -> None:
        if self.pivot is None:
            return
        sx, sy = self.to_screen(self.pivot)
        self.canvas.create_oval(sx - 5, sy - 5, sx + 5, sy + 5, outline="#0f172a", width=2)
        self.canvas.create_line(sx - 9, sy, sx + 9, sy, fill="#0f172a")
        self.canvas.create_line(sx, sy - 9, sx, sy + 9, fill="#0f172a")
        self.canvas.create_text(sx + 12, sy - 12, text="A", fill="#0f172a", font=("Segoe UI", 9, "bold"))

    def _draw_intersection(self) -> None:
        first, second = self._probe_pair()
        if first is not None:
            self._arrow(first[0], first[1], "#7c3aed", 3)
        if second is not None:
            self._arrow(second[0], second[1], "#db2777", 3)
        hit = self._current_intersection()
        if hit is None or hit.point is None:
            return
        sx, sy = self.to_screen(hit.point)
        if hit.on_segments:
            self.canvas.create_oval(sx - 6, sy - 6, sx + 6, sy + 6, fill="#dc2626", outline="white", width=2)
        else:
            self.canvas.create_oval(sx - 6, sy - 6, sx + 6, sy + 6, outline="#dc2626", width=2)
        self.canvas.create_text(sx + 8, sy + 14, text=f"({hit.point[0]:.1f}, {hit.point[1]:.1f})", fill="#dc2626")

    def _draw_side(self) -> None:
        edge = self._side_edge()
        if edge is None:
            return
        self._arrow(edge[0], edge[1], "#7c3aed", 3)
        if self.side_live == "b" or self.side_b is None:
            return
        names = {"left": "слева", "right": "справа", "on": "на прямой"}
        colors = {"left": "#047857", "right": "#c2410c", "on": "#1d4ed8"}
        for point in self.side_points:
            side = classify_side(edge[0], edge[1], point, MOUSE_TOL)
            sx, sy = self.to_screen(point)
            color = colors[side.kind]
            self.canvas.create_oval(sx - 4, sy - 4, sx + 4, sy + 4, fill=color, outline="white")
            self.canvas.create_text(sx + 8, sy - 12, text=names[side.kind], fill=color, font=("Segoe UI", 9))

    def _draw_inside(self) -> None:
        polygons = [poly.points for poly in self.polygons]
        for number, point in enumerate(self.inside_points, start=1):
            hits = analyze_figures(polygons, point, MOUSE_TOL)
            sx, sy = self.to_screen(point)
            label = marker_label(hits)
            color = "#047857" if label == "внутри" else "#c2410c" if label == "снаружи" else "#a16207"
            if number == len(self.inside_points):
                self._draw_ray(point, hits)
            self.canvas.create_oval(sx - 5, sy - 5, sx + 5, sy + 5, fill=color, outline="white", width=2)
            self.canvas.create_text(sx + 10, sy - 12, text=f"{number}. {label}", fill=color, font=("Segoe UI", 9, "bold"))

    def _draw_ray(self, point: Point, hits: list[FigureHit]) -> None:
        sx, sy = self.to_screen(point)
        self.canvas.create_line(sx, sy, CANVAS_W, sy, fill="#94a3b8", dash=(4, 3))
        for hit, poly in zip(hits, self.polygons):
            for crossing in hit.crossings:
                cx, cy = self.to_screen(crossing)
                self.canvas.create_rectangle(cx - 3, cy - 3, cx + 3, cy + 3, outline=poly.color, width=2)


def _same_edge(first: tuple[Point, Point], second: tuple[Point, Point]) -> bool:
    def near(left: Point, right: Point) -> bool:
        return math.hypot(left[0] - right[0], left[1] - right[1]) < 1.0

    return (near(first[0], second[0]) and near(first[1], second[1])) or (
        near(first[0], second[1]) and near(first[1], second[0])
    )


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
