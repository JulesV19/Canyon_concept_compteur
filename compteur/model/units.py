"""Conversions d'unités pour l'écran."""


def kmh(mps: float | None) -> float | None:
    return None if mps is None else mps * 3.6
