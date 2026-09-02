from models import User


def format_user(user: User) -> str:
    return f"{user.first_name} {user.last_name}"
