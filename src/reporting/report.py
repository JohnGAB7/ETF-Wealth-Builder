from pathlib import Path
import json
import math
from datetime import datetime, timezone


def _clean(value):
    """Replace NaN/inf by None so the report is strict, portable JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    return value


def write_report(payload: dict, output_dir: str = "data/reports") -> Path:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    filename = path / f"daily_report_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.json"
    filename.write_text(
        json.dumps(_clean(payload), indent=2, default=str, allow_nan=False),
        encoding="utf-8",
    )
    return filename
