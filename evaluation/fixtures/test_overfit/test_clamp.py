import unittest

from clamp import clamp


class ClampTests(unittest.TestCase):
    def test_value_inside_range(self):
        self.assertEqual(clamp(5, 0, 10), 5)

    def test_value_above_upper_bound(self):
        self.assertEqual(clamp(15, 0, 10), 10)


if __name__ == "__main__":
    unittest.main()
