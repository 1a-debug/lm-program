import unittest

from calculator import add, divide


class CalculatorTests(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)

    def test_divide(self):
        self.assertEqual(divide(10, 2), 5)

    def test_divide_by_zero(self):
        with self.assertRaisesRegex(ValueError, "cannot be zero"):
            divide(10, 0)


if __name__ == "__main__":
    unittest.main()
