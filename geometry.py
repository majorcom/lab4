from __future__ import annotations

import math
from dataclasses import dataclass

Point = tuple[float, float]
Matrix = list[list[float]]

EPS = 1e-8


def _clean(value: float) -> float:
    return 0.0 if abs(value) < 1e-12 else value


def format_number(value: float) -> str:
    value = _clean(value)
    return f"{value:.4f}"


def format_matrix(matrix: Matrix) -> str:
    return "\n".join(
        "[" + "  ".join(f"{format_number(value):>10}" for value in row) + "]"
        for row in matrix
    )


def multiply(left: Matrix, right: Matrix) -> Matrix:
    return [
        [
            left[i][0] * right[0][j] + left[i][1] * right[1][j] + left[i][2] * right[2][j]
            for j in range(3)
        ]
        for i in range(3)
    ]


def apply_point(matrix: Matrix, x: float, y: float) -> Point:
    return (
        x * matrix[0][0] + y * matrix[1][0] + matrix[2][0],
        x * matrix[0][1] + y * matrix[1][1] + matrix[2][1],
    )


def transform_points(matrix: Matrix, points: list[Point]) -> list[Point]:
    return [apply_point(matrix, x, y) for x, y in points]


def translation(dx: float, dy: float) -> Matrix:
    return [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [dx, dy, 1.0],
    ]


def rotation(phi: float) -> Matrix:
    cosine = math.cos(phi)
    sine = math.sin(phi)
    return [
        [cosine, sine, 0.0],
        [-sine, cosine, 0.0],
        [0.0, 0.0, 1.0],
    ]


def scaling(alpha: float, delta: float) -> Matrix:
    return [
        [alpha, 0.0, 0.0],
        [0.0, delta, 0.0],
        [0.0, 0.0, 1.0],
    ]


def around_point(ax: float, ay: float, linear: Matrix) -> Matrix:
    return multiply(multiply(translation(-ax, -ay), linear), translation(ax, ay))


def rotation_about_point(ax: float, ay: float, phi: float) -> Matrix:
    return around_point(ax, ay, rotation(phi))


def scaling_about_point(ax: float, ay: float, alpha: float, delta: float) -> Matrix:
    return around_point(ax, ay, scaling(alpha, delta))


def signed_area(points: list[Point]) -> float:
    area = 0.0
    count = len(points)
    for index in range(count):
        x1, y1 = points[index]
        x2, y2 = points[(index + 1) % count]
        area += x1 * y2 - x2 * y1
    return area / 2.0


def polygon_center(points: list[Point]) -> Point:
    count = len(points)
    if count == 0:
        raise ValueError("у фигуры нет вершин")
    if count == 1:
        return points[0]
    if count == 2:
        return (
            (points[0][0] + points[1][0]) / 2.0,
            (points[0][1] + points[1][1]) / 2.0,
        )
    area = signed_area(points)
    if abs(area) <= EPS:
        return (
            sum(point[0] for point in points) / count,
            sum(point[1] for point in points) / count,
        )
    cx = 0.0
    cy = 0.0
    for index in range(count):
        x1, y1 = points[index]
        x2, y2 = points[(index + 1) % count]
        cross = x1 * y2 - x2 * y1
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    return cx / (6.0 * area), cy / (6.0 * area)


def _edge_cross(origin: Point, along: Point, target: Point) -> float:
    xa = along[0] - origin[0]
    ya = along[1] - origin[1]
    xb = target[0] - origin[0]
    yb = target[1] - origin[1]
    return yb * xa - xb * ya


def is_convex(points: list[Point]) -> bool:
    count = len(points)
    if count < 3 or abs(signed_area(points)) <= EPS:
        return False
    positive = False
    negative = False
    for index in range(count):
        cross = _edge_cross(
            points[index],
            points[(index + 1) % count],
            points[(index + 2) % count],
        )
        if cross > EPS:
            positive = True
        elif cross < -EPS:
            negative = True
        if positive and negative:
            return False
    return True


def polygon_kind(points: list[Point]) -> str:
    count = len(points)
    if count <= 1:
        return "точка"
    if count == 2:
        return "ребро"
    if abs(signed_area(points)) <= EPS:
        return "вырожденный полигон"
    if is_convex(points):
        return "выпуклый полигон"
    return "невыпуклый полигон"


def distance_to_segment(start: Point, end: Point, point: Point) -> float:
    abx = end[0] - start[0]
    aby = end[1] - start[1]
    length2 = abx * abx + aby * aby
    if length2 <= EPS:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    factor = ((point[0] - start[0]) * abx + (point[1] - start[1]) * aby) / length2
    factor = min(1.0, max(0.0, factor))
    qx = start[0] + factor * abx
    qy = start[1] + factor * aby
    return math.hypot(point[0] - qx, point[1] - qy)


def on_boundary(points: list[Point], point: Point, tolerance: float) -> bool:
    count = len(points)
    if count < 2:
        return False
    limit = count if count >= 3 else 1
    for index in range(limit):
        if distance_to_segment(points[index], points[(index + 1) % count], point) <= tolerance:
            return True
    return False


@dataclass(frozen=True)
class Side:
    kind: str
    value: float
    distance: float
    xa: float
    ya: float
    xb: float
    yb: float


def classify_side(start: Point, end: Point, point: Point, tolerance: float = EPS) -> Side:
    xa = end[0] - start[0]
    ya = end[1] - start[1]
    xb = point[0] - start[0]
    yb = point[1] - start[1]
    value = yb * xa - xb * ya
    length = math.hypot(xa, ya)
    distance = 0.0 if length <= EPS else value / length
    if length <= EPS or abs(distance) <= tolerance:
        kind = "on"
    elif value > 0.0:
        kind = "left"
    else:
        kind = "right"
    return Side(kind, value, distance, xa, ya, xb, yb)


def format_side(start: Point, end: Point, point: Point, side: Side) -> str:
    names = {"left": "слева", "right": "справа", "on": "на прямой ребра"}
    lines = [
        f"Ребро ({format_number(start[0])}, {format_number(start[1])})"
        f" → ({format_number(end[0])}, {format_number(end[1])})",
        f"Точка ({format_number(point[0])}, {format_number(point[1])})",
        f"xa = {format_number(side.xa)}, ya = {format_number(side.ya)}, "
        f"xb = {format_number(side.xb)}, yb = {format_number(side.yb)}",
        f"yb·xa − xb·ya = {format_number(side.value)}",
        f"Расстояние до прямой: {format_number(side.distance)}",
        f"Ответ: точка {names[side.kind]}.",
    ]
    return "\n".join(lines)


def _halfplane(points: list[Point], point: Point) -> str:
    area = signed_area(points)
    if abs(area) <= EPS:
        return "degenerate"
    want = "right" if area < 0.0 else "left"
    count = len(points)
    for index in range(count):
        side = classify_side(points[index], points[(index + 1) % count], point, EPS)
        if side.kind == "on":
            continue
        if side.kind != want:
            return "outside"
    return "inside"


def _ray(points: list[Point], point: Point) -> tuple[str, list[Point]]:
    x, y = point
    inside = False
    crossings: list[Point] = []
    count = len(points)
    for index in range(count):
        x1, y1 = points[index]
        x2, y2 = points[(index + 1) % count]
        if (y1 > y) == (y2 > y):
            continue
        x_cross = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
        if x < x_cross:
            inside = not inside
            crossings.append((x_cross, y))
    return ("inside" if inside else "outside"), crossings


@dataclass(frozen=True)
class FigureHit:
    index: int
    kind_name: str
    convex: bool
    clockwise: bool | None
    half: str
    ray: str
    crossings: tuple[Point, ...]


def _belong(kind: str) -> str:
    if kind == "inside":
        return "принадлежит"
    if kind == "outside":
        return "не принадлежит"
    if kind == "boundary":
        return "принадлежит, точка на границе"
    if kind == "degenerate":
        return "полигон вырожденный"
    return kind


def analyze_figures(polygons: list[list[Point]], point: Point, tolerance: float) -> list[FigureHit]:
    hits: list[FigureHit] = []
    for index, points in enumerate(polygons, start=1):
        kind_name = polygon_kind(points)
        if len(points) < 3:
            hits.append(FigureHit(index, kind_name, False, None, "skipped", "skipped", ()))
            continue
        area = signed_area(points)
        clockwise = None if abs(area) <= EPS else area < 0.0
        convex = is_convex(points)
        if on_boundary(points, point, tolerance):
            hits.append(FigureHit(index, kind_name, convex, clockwise, "boundary", "boundary", ()))
            continue
        half = _halfplane(points, point)
        ray_kind, crossings = _ray(points, point)
        hits.append(
            FigureHit(index, kind_name, convex, clockwise, half, ray_kind, tuple(crossings))
        )
    return hits


def format_membership(hits: list[FigureHit], point: Point) -> str:
    lines = [f"Точка ({format_number(point[0])}, {format_number(point[1])})"]
    if not hits:
        lines.append("На сцене нет фигур.")
        return "\n".join(lines)
    tested = False
    for hit in hits:
        if hit.ray == "skipped":
            lines.append(
                f"Фигура {hit.index}: {hit.kind_name}. "
                "Для принадлежности нужен полигон хотя бы из трёх вершин."
            )
            continue
        tested = True
        if hit.convex:
            turn = "по часовой" if hit.clockwise else "против часовой"
            side = "справа" if hit.clockwise else "слева"
            lines.append(f"Фигура {hit.index}: выпуклый полигон, обход {turn}.")
            lines.append(f"Полуплоскости ({side} от всех рёбер): {_belong(hit.half)}.")
        else:
            lines.append(f"Фигура {hit.index}: {hit.kind_name}.")
            lines.append(f"Полуплоскости: {_belong(hit.half)}.")
        lines.append(f"Метод лучей: {_belong(hit.ray)}.")
        if hit.ray != "boundary":
            lines.append(f"Пересечений луча: {len(hit.crossings)}.")
    if not tested:
        lines.append("Нарисуйте полигон из трёх и более вершин и щёлкните точку ещё раз.")
    return "\n".join(lines)


def marker_label(hits: list[FigureHit]) -> str:
    checked = [hit for hit in hits if hit.ray != "skipped"]
    if not checked:
        return "нет полигона"
    if all(hit.ray in ("inside", "boundary") for hit in checked):
        return "внутри"
    if all(hit.ray == "outside" for hit in checked):
        return "снаружи"
    return "по-разному"


@dataclass(frozen=True)
class Intersection:
    point: Point | None
    t: float | None
    u: float | None
    parallel: bool
    collinear: bool
    overlap: bool
    on_segments: bool
    degenerate: bool


def intersect_segments(a: Point, b: Point, c: Point, d: Point) -> Intersection:
    abx = b[0] - a[0]
    aby = b[1] - a[1]
    cdx = d[0] - c[0]
    cdy = d[1] - c[1]
    ab_len = math.hypot(abx, aby)
    cd_len = math.hypot(cdx, cdy)
    if ab_len <= EPS or cd_len <= EPS:
        return Intersection(None, None, None, False, False, False, False, True)

    nx = -cdy
    ny = cdx
    denominator = nx * abx + ny * aby
    scale = max(ab_len * cd_len, 1.0)
    if abs(denominator) <= EPS * scale:
        cross_c = abx * (c[1] - a[1]) - aby * (c[0] - a[0])
        cross_d = abx * (d[1] - a[1]) - aby * (d[0] - a[0])
        collinear = abs(cross_c) <= EPS * ab_len and abs(cross_d) <= EPS * ab_len
        if not collinear:
            return Intersection(None, None, None, True, False, False, False, False)
        length2 = abx * abx + aby * aby
        def parameter(point: Point) -> float:
            return ((point[0] - a[0]) * abx + (point[1] - a[1]) * aby) / length2
        low = max(0.0, min(parameter(c), parameter(d)))
        high = min(1.0, max(parameter(c), parameter(d)))
        if high < low - EPS:
            return Intersection(None, None, None, True, True, False, False, False)
        mid = (low + high) / 2.0
        return Intersection((a[0] + mid * abx, a[1] + mid * aby), mid, None, True, True, True, True, False)

    t = -(nx * (a[0] - c[0]) + ny * (a[1] - c[1])) / denominator
    point = (a[0] + t * abx, a[1] + t * aby)
    cd2 = cdx * cdx + cdy * cdy
    u = ((point[0] - c[0]) * cdx + (point[1] - c[1]) * cdy) / cd2
    on_segments = -EPS <= t <= 1.0 + EPS and -EPS <= u <= 1.0 + EPS
    return Intersection(point, t, u, False, False, False, on_segments, False)


def format_intersection(a: Point, b: Point, c: Point, d: Point, hit: Intersection) -> str:
    lines = [
        f"Ребро 1: ({format_number(a[0])}, {format_number(a[1])}) → "
        f"({format_number(b[0])}, {format_number(b[1])})",
        f"Ребро 2: ({format_number(c[0])}, {format_number(c[1])}) → "
        f"({format_number(d[0])}, {format_number(d[1])})",
    ]
    if hit.degenerate:
        lines.append("Одно из рёбер имеет нулевую длину, пересечение не ищется.")
        return "\n".join(lines)
    if hit.parallel and hit.overlap and hit.point is not None:
        lines.append(
            "Рёбра лежат на одной прямой и пересекаются по отрезку. "
            f"Точка на этом отрезке: ({format_number(hit.point[0])}, {format_number(hit.point[1])})."
        )
        return "\n".join(lines)
    if hit.parallel and hit.collinear:
        lines.append("Рёбра лежат на одной прямой и не пересекаются.")
        return "\n".join(lines)
    if hit.parallel:
        lines.append("Прямые параллельны, точки пересечения нет.")
        return "\n".join(lines)
    assert hit.point is not None and hit.t is not None and hit.u is not None
    cdx = d[0] - c[0]
    cdy = d[1] - c[1]
    lines.append(f"n = ({format_number(-cdy)}, {format_number(cdx)})")
    lines.append(f"t = {format_number(hit.t)}, u = {format_number(hit.u)}")
    lines.append(f"P = ({format_number(hit.point[0])}, {format_number(hit.point[1])})")
    if hit.on_segments:
        lines.append("Рёбра пересекаются.")
    else:
        lines.append("Прямые пересекаются вне ребра.")
    return "\n".join(lines)


def intersection_brief(hit: Intersection) -> str:
    if hit.degenerate:
        return "Ребро нулевой длины"
    if hit.parallel and hit.overlap and hit.point is not None:
        return (
            "Рёбра пересекаются по отрезку, точка "
            f"({format_number(hit.point[0])}, {format_number(hit.point[1])})"
        )
    if hit.parallel and hit.collinear:
        return "На одной прямой, общего участка нет"
    if hit.parallel:
        return "Прямые параллельны"
    assert hit.point is not None and hit.t is not None and hit.u is not None
    place = f"({format_number(hit.point[0])}, {format_number(hit.point[1])})"
    if hit.on_segments:
        return f"Рёбра пересекаются в {place}"
    return f"Прямые пересекаются в {place}, рёбра — нет"
