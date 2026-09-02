def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("divisor cannot be zero")
    return a / b
