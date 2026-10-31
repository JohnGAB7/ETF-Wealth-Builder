from pathlib import Path
import json
from datetime import datetime, timezone

def write_report(payload: dict, output_dir: str = "data/reports") -> Path:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    filename = path / f"daily_report_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.json"
    filename.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return filename
