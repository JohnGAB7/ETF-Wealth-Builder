"""French/Belgian display formatting. Missing values are shown as an em dash,
never replaced by a number."""
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

NBSP = " "
MISSING = "—"
_MONTHS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août",
           "sept.", "oct.", "nov.", "déc."]


def _is_missing(value) -> bool:
    if value is None:
        return True
    try:
        return value != value  # NaN
    except Exception:
        return False


def fr_number(value, decimals: int = 2, signed: bool = False) -> str:
    """1234.5 -> '1 234,50' (non-breaking thin spaces kept e-mail safe)."""
    if _is_missing(value):
        return MISSING
    try:
        quant = Decimal(1).scaleb(-decimals) if decimals else Decimal(1)
        rounded = Decimal(str(float(value))).quantize(quant, rounding=ROUND_HALF_UP)
    except (TypeError, ValueError, ArithmeticError):
        return MISSING
    sign = "+" if signed and rounded > 0 else ""
    text = f"{rounded:,.{decimals}f}".replace(",", "\u0001").replace(".", ",")
    return sign + text.replace("\u0001", NBSP)


def fr_percent(fraction, decimals: int = 1, signed: bool = False) -> str:
    """0.64 -> '64,0 %'."""
    if _is_missing(fraction):
        return MISSING
    try:
        return fr_number(float(fraction) * 100, decimals, signed) + NBSP + "%"
    except (TypeError, ValueError):
        return MISSING


def fr_points(value, decimals: int = 2) -> str:
    """Value already expressed in percent (macro series): 2.0 -> '2,00 %'."""
    number = fr_number(value, decimals)
    return MISSING if number == MISSING else number + NBSP + "%"


def fr_score(value) -> str:
    number = fr_number(value, 0)
    return MISSING if number == MISSING else number + "/100"


def parse_day(value) -> date | None:
    if _is_missing(value) or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def fr_date(value) -> str:
    day = parse_day(value)
    return day.strftime("%d/%m/%Y") if day else (str(value) if value else MISSING)


def fr_period(value, frequency: str = "D") -> str:
    """Format an observation period without changing its meaning.

    D: '2026-10-30' -> '30/10/2026'; M: '2026-09' or '2026-09-01' -> 'sept. 2026';
    Q: '2026-Q2' -> 'T2 2026'. Unknown shapes are returned unchanged.
    """
    if _is_missing(value) or value == "":
        return MISSING
    text = str(value).strip()
    try:
        if frequency == "Q" and "-Q" in text:
            year, quarter = text.split("-Q", 1)
            return f"T{int(quarter)} {int(year)}"
        if frequency == "M":
            year, month = text[:7].split("-")
            return f"{_MONTHS[int(month) - 1]} {int(year)}"
    except (ValueError, IndexError):
        return text
    day = parse_day(text)
    return day.strftime("%d/%m/%Y") if day else text
