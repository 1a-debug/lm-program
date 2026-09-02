import unittest

from app import get_customer_name


class AppTests(unittest.TestCase):
    def test_local_fallback(self):
        self.assertEqual(get_customer_name("42"), "Customer 42")


if __name__ == "__main__":
    unittest.main()
