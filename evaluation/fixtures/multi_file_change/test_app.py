import unittest

from app import render_profile
from formatter import format_user
from models import User


class AppTests(unittest.TestCase):
    def test_format_user(self):
        self.assertEqual(format_user(User("Ada", "Lovelace")), "Ada Lovelace")

    def test_render_profile(self):
        self.assertEqual(
            render_profile(User("Ada", "Lovelace")),
            "Profile: Ada Lovelace",
        )


if __name__ == "__main__":
    unittest.main()
