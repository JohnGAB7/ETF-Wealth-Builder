def suggested_tranche(cash_eur: float, score: float, max_fraction: float = 0.35,
                      daily_cap_eur: float = 2000, buffer_eur: float = 0) -> float:
    """Indicative tranche only; assumes cash ledger has already been reconciled."""
    available = max(0.0, cash_eur - buffer_eur)
    if score < 55 or available <= 0:
        return 0.0
    strength = min(1.0, max(0.0, (score - 55) / 45))
    return round(min(available * max_fraction * strength, daily_cap_eur), 2)
