from __future__ import annotations

import unittest

import support  # noqa: F401

import student_tasks


class PublicApiTests(unittest.TestCase):
    def test_every_declared_public_symbol_is_importable(self) -> None:
        self.assertEqual(len(student_tasks.__all__), len(set(student_tasks.__all__)))
        for name in student_tasks.__all__:
            with self.subTest(name=name):
                self.assertTrue(hasattr(student_tasks, name))

    def test_coordinate_helpers_document_base_link_si_units(self) -> None:
        self.assertIn("base_link", student_tasks.__doc__)
        self.assertIn("SI-unit", student_tasks.__doc__)
        self.assertIn("x forward", student_tasks.Velocity.__doc__)
        self.assertIn("z is height", student_tasks.base_planar_geometry.__doc__)


if __name__ == "__main__":
    unittest.main()
