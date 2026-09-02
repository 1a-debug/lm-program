import unittest

from formatter import format_user


class FormatterTests(unittest.TestCase):
    def test_current_format(self):
        self.assertEqual(format_user("Ada", "Lovelace"), "Ada Lovelace")


if __name__ == "__main__":
    unittest.main()
