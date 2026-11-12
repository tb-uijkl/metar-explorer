"""Run with: python3 -m unittest discover -v"""
import math
import unittest

from metar_tool import wind_components, parse_runway, describe_components


class WindMathTests(unittest.TestCase):
    def test_direct_headwind(self):
        head, cross = wind_components(180, 10, 180, 0)
        self.assertAlmostEqual(head, 10)
        self.assertAlmostEqual(cross, 0)

    def test_direct_tailwind(self):
        head, cross = wind_components(0, 10, 180, 0)
        self.assertAlmostEqual(head, -10)
        self.assertAlmostEqual(cross, 0)

    def test_crosswind_from_right(self):
        head, cross = wind_components(270, 8, 180, 0)
        self.assertAlmostEqual(head, 0, places=6)
        self.assertAlmostEqual(cross, 8)
        self.assertIn("right", describe_components(head, cross))

    def test_crosswind_from_left(self):
        head, cross = wind_components(90, 8, 180, 0)
        self.assertAlmostEqual(head, 0, places=6)
        self.assertAlmostEqual(cross, -8)

    def test_magnetic_variation(self):
        # Runway magnetic 090 + east variation 10 = runway true 100.
        head, cross = wind_components(100, 12, 90, 10)
        self.assertAlmostEqual(head, 12)
        self.assertAlmostEqual(cross, 0, places=6)

    def test_runway_labels(self):
        self.assertEqual(parse_runway("07L"), 70)
        self.assertEqual(parse_runway("36"), 0)


if __name__ == "__main__":
    unittest.main()
