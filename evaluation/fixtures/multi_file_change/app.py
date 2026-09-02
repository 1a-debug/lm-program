from formatter import format_user
from models import User


def render_profile(user: User) -> str:
    return f"Profile: {format_user(user)}"
