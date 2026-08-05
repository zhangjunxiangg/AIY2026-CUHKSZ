from __future__ import annotations

import math
import unittest

import support  # noqa: F401

from student_tasks.geometry import (
    CameraIntrinsics,
    RigidTransform,
    Vector3,
    base_planar_geometry,
    unproject_pixel,
)


class GeometryTests(unittest.TestCase):
    def test_vector_rejects_non_finite_coordinates(self) -> None:
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Vector3(value, 0.0, 0.0)

    def test_intrinsics_and_pixel_bounds_are_validated(self) -> None:
        intrinsics = CameraIntrinsics(100.0, 120.0, 50.0, 40.0, 100, 80)
        self.assertEqual(Vector3(0.1, -1.0 / 12.0, 1.0), unproject_pixel(60.0, 30.0, 1.0, intrinsics))
        for u, v, depth in ((-1.0, 1.0, 1.0), (100.0, 1.0, 1.0), (1.0, 80.0, 1.0), (1.0, 1.0, 0.0)):
            with self.subTest(u=u, v=v, depth=depth), self.assertRaises(ValueError):
                unproject_pixel(u, v, depth, intrinsics)
        with self.assertRaises(ValueError):
            CameraIntrinsics(0.0, 1.0, 0.0, 0.0, 10, 10)

    def test_rigid_transform_requires_right_handed_orthonormal_rotation(self) -> None:
        identity = RigidTransform((1, 0, 0, 0, 1, 0, 0, 0, 1), Vector3(1, 2, 3))
        self.assertEqual(1.0, identity.determinant)
        self.assertEqual(Vector3(2, 4, 6), identity.apply(Vector3(1, 2, 3)))
        invalid_rotations = (
            (2, 0, 0, 0, 1, 0, 0, 0, 1),
            (-1, 0, 0, 0, 1, 0, 0, 0, 1),
            (1, 0, 0, 1, 0, 0, 0, 0, 1),
        )
        for rotation in invalid_rotations:
            with self.subTest(rotation=rotation), self.assertRaises(ValueError):
                RigidTransform(rotation, Vector3(0, 0, 0))

    def test_camera_forward_depth_transforms_to_base_coordinates(self) -> None:
        intrinsics = CameraIntrinsics(100, 100, 50, 40, 100, 80)
        optical_point = unproject_pixel(60, 30, 1.0, intrinsics)
        camera_to_base = RigidTransform(
            (0, 0, 1, -1, 0, 0, 0, -1, 0),
            Vector3(0.1, 0.0, 0.2),
        )
        base_point = camera_to_base.apply(optical_point)
        self.assertAlmostEqual(1.1, base_point.x, places=6)
        self.assertAlmostEqual(-0.1, base_point.y, places=6)
        self.assertAlmostEqual(0.3, base_point.z, places=6)

    def test_planar_distance_and_bearing_ignore_base_height(self) -> None:
        distance, bearing = base_planar_geometry(Vector3(3.0, 4.0, 100.0))
        self.assertEqual(5.0, distance)
        self.assertAlmostEqual(math.atan2(4.0, 3.0), bearing)


if __name__ == "__main__":
    unittest.main()
