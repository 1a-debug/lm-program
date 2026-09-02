def add(a: float, b: float) -> float:
    return a + b


def divide(a: float, b: float) -> float:
    """Divide a by b."""
    if b == 0:
        raise ValueError("divisor cannot be zero")
    return a / b
