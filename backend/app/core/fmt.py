def br(x: float, nd: int = 1) -> str:
    """Número no formato brasileiro (vírgula decimal, ponto de milhar)."""
    return f"{x:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")
