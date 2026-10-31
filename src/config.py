from pathlib import Path
import os
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

def load_yaml(relative_path: str) -> dict:
    with (ROOT / relative_path).open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def get_secret(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else None
