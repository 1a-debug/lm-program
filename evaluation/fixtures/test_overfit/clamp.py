def clamp(value: float, lower: float, upper: float) -> float:
    """Return value constrained to the inclusive [lower, upper] interval."""
    return min(value, upper)
