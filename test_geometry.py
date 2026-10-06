from __future__ import annotations

import math
import unittest

from geometry import (
    analyze_figures,
    apply_point,
    classify_side,
    format_membership,
    intersect_segments,
    is_convex,
    multiply,
    polygon_center,
    rotation,
    rotation_about_point,
    scaling,
    scaling_about_point,
    transform_points,
    translation,
)

SQUARE = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)]
SQUARE_CW = [(0.0, 0.0), (0.0, 4.0), (4.0, 4.0), (4.0, 0.0)]
ELL = [(0.0, 0.0), (5.0, 0.0), (5.0, 1.0), (1.0, 1.0), (1.0, 4.0), (0.0, 4.0)]


def close(left, right, tol: float = 1e-8) -> bool:
    return math.isclose(left, right, rel_tol=tol, abs_tol=tol)


def matrices_close(left, right) -> bool:
    return all(close(left[i][j], right[i][j]) for i in range(3) for j in range(3))


class AffineTests(unittest.TestCase):
    def test_translation_moves_point(self) -> None:
        point = apply_point(translation(2.0, -3.0), 1.0, 4.0)
        self.assertTrue(close(point[0], 3.0) and close(point[1], 1.0))

    def test_rotation_90_is_counterclockwise(self) -> None:
        point = apply_point(rotation(math.pi / 2.0), 1.0, 0.0)
        self.assertTrue(close(point[0], 0.0) and close(point[1], 1.0))

    def test_rotation_matches_lecture_formula(self) -> None:
        phi = 0.4
        x, y = 2.0, -1.5
        got = apply_point(rotation(phi), x, y)
        cosine, sine = math.cos(phi), math.sin(phi)
        self.assertTrue(close(got[0], x * cosine - y * sine))
        self.assertTrue(close(got[1], x * sine + y * cosine))

    def test_rotation_about_point_matrix(self) -> None:
        phi = 0.7
        a, b = 2.0, -4.0
        cosine, sine = math.cos(phi), math.sin(phi)
        closed = [
            [cosine, sine, 0.0],
            [-sine, cosine, 0.0],
            [-a * cosine + b * sine + a, -a * sine - b * cosine + b, 1.0],
        ]
        self.assertTrue(matrices_close(rotation_about_point(a, b, phi), closed))
        original = (5.0, 1.0)
        self.assertEqual(apply_point(rotation_about_point(a, b, phi), *original), apply_point(closed, *original))

    def test_rotation_about_point_keeps_center(self) -> None:
        moved = apply_point(rotation_about_point(1.0, 0.0, math.pi / 2.0), 2.0, 0.0)
        self.assertTrue(close(moved[0], 1.0) and close(moved[1], 1.0))
        stayed = apply_point(rotation_about_point(1.0, 0.0, math.pi / 2.0), 1.0, 0.0)
        self.assertTrue(close(stayed[0], 1.0) and close(stayed[1], 0.0))

    def test_scale_about_point_matrix(self) -> None:
        alpha, delta = 2.0, 0.5
        a, b = 1.0, 1.0
        closed = [
            [alpha, 0.0, 0.0],
            [0.0, delta, 0.0],
            [(1.0 - alpha) * a, (1.0 - delta) * b, 1.0],
        ]
        self.assertTrue(matrices_close(scaling_about_point(a, b, alpha, delta), closed))
        got = apply_point(scaling_about_point(a, b, alpha, delta), 3.0, 3.0)
        self.assertTrue(close(got[0], 5.0) and close(got[1], 2.0))

    def test_scale_about_origin(self) -> None:
        got = apply_point(scaling(2.0, 3.0), 1.0, 1.0)
        self.assertEqual(got, (2.0, 3.0))

    def test_product_order_is_left_to_right(self) -> None:
        matrix = multiply(translation(-1.0, -1.0), translation(1.0, 1.0))
        got = apply_point(matrix, 4.0, 5.0)
        self.assertTrue(close(got[0], 4.0) and close(got[1], 5.0))


class VectorTests(unittest.TestCase):
    def test_left_and_right(self) -> None:
        start, end = (0.0, 0.0), (1.0, 0.0)
        self.assertEqual(classify_side(start, end, (0.0, 1.0)).kind, "left")
        self.assertEqual(classify_side(start, end, (0.0, -1.0)).kind, "right")
        self.assertEqual(classify_side(start, end, (2.0, 0.0)).kind, "on")
        left = classify_side(start, end, (0.0, 1.0))
        self.assertGreater(left.value, 0.0)

    def test_convex_square_both_orientations(self) -> None:
        self.assertTrue(is_convex(SQUARE))
        self.assertTrue(is_convex(SQUARE_CW))
        for square in (SQUARE, SQUARE_CW):
            inside = analyze_figures([square], (2.0, 2.0), 1e-8)[0]
            self.assertEqual(inside.half, "inside")
            self.assertEqual(inside.ray, "inside")
            outside = analyze_figures([square], (6.0, 2.0), 1e-8)[0]
            self.assertEqual(outside.half, "outside")
            self.assertEqual(outside.ray, "outside")
            border = analyze_figures([square], (2.0, 0.0), 1e-8)[0]
            self.assertEqual(border.ray, "boundary")
            self.assertEqual(border.half, "boundary")

    def test_ray_along_edge_does_not_count_it_twice(self) -> None:
        hit = analyze_figures([SQUARE], (-1.0, 0.0), 1e-8)[0]
        self.assertEqual(hit.ray, "outside")
        self.assertEqual(len(hit.crossings), 2)

    def test_concave_halfplane_disagrees_with_ray(self) -> None:
        self.assertFalse(is_convex(ELL))
        inside = analyze_figures([ELL], (0.5, 2.0), 1e-8)[0]
        self.assertEqual(inside.ray, "inside")
        self.assertEqual(inside.half, "outside")
        notch = analyze_figures([ELL], (3.0, 2.0), 1e-8)[0]
        self.assertEqual(notch.ray, "outside")
        text = format_membership([inside], (0.5, 2.0))
        self.assertIn("Метод лучей: принадлежит", text)
        self.assertIn("невыпуклый", text)
        self.assertIn("Полуплоскости: не принадлежит", text)

    def test_center_of_triangle(self) -> None:
        center = polygon_center([(0.0, 0.0), (2.0, 0.0), (0.0, 2.0)])
        self.assertTrue(close(center[0], 2.0 / 3.0) and close(center[1], 2.0 / 3.0))

    def test_segment_crossing(self) -> None:
        hit = intersect_segments((0.0, 0.0), (2.0, 2.0), (0.0, 2.0), (2.0, 0.0))
        self.assertTrue(hit.on_segments)
        self.assertIsNotNone(hit.point)
        assert hit.point is not None
        self.assertTrue(close(hit.point[0], 1.0) and close(hit.point[1], 1.0))
        self.assertTrue(close(hit.t or 0.0, 0.5) and close(hit.u or 0.0, 0.5))

    def test_parallel_and_overlap(self) -> None:
        parallel = intersect_segments((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0))
        self.assertTrue(parallel.parallel and not parallel.collinear)
        apart = intersect_segments((0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0))
        self.assertTrue(apart.collinear and not apart.overlap)
        overlap = intersect_segments((0.0, 0.0), (2.0, 0.0), (1.0, 0.0), (3.0, 0.0))
        self.assertTrue(overlap.overlap and overlap.on_segments)
        assert overlap.point is not None
        self.assertTrue(close(overlap.point[0], 1.5) and close(overlap.point[1], 0.0))

    def test_lines_cross_outside_segments(self) -> None:
        hit = intersect_segments((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 2.0))
        self.assertFalse(hit.parallel)
        self.assertFalse(hit.on_segments)
        self.assertIsNotNone(hit.point)

    def test_transform_points_uses_matrix(self) -> None:
        moved = transform_points(translation(10.0, -2.0), [(1.0, 1.0), (2.0, 3.0)])
        self.assertEqual(moved, [(11.0, -1.0), (12.0, 1.0)])


class AppTests(unittest.TestCase):
    def test_mouse_polygon_transforms_and_queries(self) -> None:
        try:
            import tkinter as tk
        except tk.TclError:
            self.skipTest("нет tkinter")
        from main import ORIGIN_X, ORIGIN_Y, App

        root = tk.Tk()
        root.withdraw()
        try:
            app = App(root)

            class Click:
                def __init__(self, x: float, y: float) -> None:
                    self.x = x
                    self.y = y

            for screen in ((100, 100), (220, 100), (160, 200)):
                app.on_left_click(Click(*screen))
            app.finish_polygon()
            self.assertEqual(len(app.polygons), 1)
            self.assertEqual(len(app.polygons[0].points), 3)
            self.assertTrue(is_convex(app.polygons[0].points))

            app.mode_var.set("inside")
            app.on_mode_changed()
            app.on_left_click(Click(160, 133))
            journal = app.log.get("1.0", tk.END)
            self.assertIn("принадлежит", journal)
            self.assertIn("Метод лучей", journal)

            before = list(app.polygons[0].points)
            app.dx_var.set("40")
            app.dy_var.set("-15")
            app.translate()
            after = app.polygons[0].points
            self.assertTrue(close(after[0][0], before[0][0] + 40.0))
            self.assertTrue(close(after[0][1], before[0][1] - 15.0))
            center_before = polygon_center(after)
            app.angle_var.set("90")
            app.rotate_center()
            center_after = polygon_center(app.polygons[0].points)
            self.assertTrue(close(center_before[0], center_after[0], 1e-6))
            self.assertTrue(close(center_before[1], center_after[1], 1e-6))
            app.undo()
            self.assertTrue(close(app.polygons[0].points[0][0], after[0][0]))

            app.mode_var.set("intersect")
            app.on_mode_changed()
            for screen in ((ORIGIN_X, ORIGIN_Y), (ORIGIN_X + 100, ORIGIN_Y - 100),
                           (ORIGIN_X, ORIGIN_Y - 100), (ORIGIN_X + 100, ORIGIN_Y)):
                app.on_left_click(Click(*screen))
            hit = app._current_intersection()
            self.assertIsNotNone(hit)
            assert hit is not None and hit.point is not None
            self.assertTrue(hit.on_segments)
            self.assertTrue(close(hit.point[0], 50.0, 1e-6))
            self.assertTrue(close(hit.point[1], 50.0, 1e-6))
            self.assertEqual(len(app.polygons), 1)

            app.mode_var.set("side")
            app.on_mode_changed()
            app.side_a = (0.0, 0.0)
            app.side_b = (1.0, 0.0)
            app._side_click((0.0, 2.0))
            self.assertIn("слева", app.log.get("1.0", tk.END))
            self.assertEqual(len(app.polygons), 1)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
