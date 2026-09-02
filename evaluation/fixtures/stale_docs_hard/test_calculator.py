import unittest

from calculator import divide


class CalculatorTests(unittest.TestCase):
    def test_division(self):
        self.assertEqual(divide(8, 2), 4)

    def test_zero_divisor(self):
        with self.assertRaisesRegex(ValueError, "cannot be zero"):
            divide(8, 0)


if __name__ == "__main__":
    unittest.main()
