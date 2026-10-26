def num(x: float, nd: int = 1) -> str:
    """Number formatted for display (en-US: comma thousands separator, dot decimal)."""
    return f"{x:,.{nd}f}"
