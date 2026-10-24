"""Configuration loading and validation for PodTube."""

import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
import yaml


# Default project root (two levels up from src/podtube/config.py)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class AppConfig:
    project_root: Path
    config_file: Path
    days_back: int
    included_font: Path
    save_location: str
    spreadsheet_url: str
    dj_spreadsheet_url: Optional[str]
    api_key: Optional[str]
    last_run_timestamp: datetime
    aws_bucket_name: str
    aws_bucket_location: str
    max_threads: int = 4


def _configure_location(raw_config: dict) -> str:
    save_locations = raw_config.get("SaveLocation", {})
    if sys.platform.startswith("linux"):
        return save_locations.get("LinuxLocation") or ""
    if sys.platform.startswith("darwin"):
        return save_locations.get("MacOSLocation") or ""
    if sys.platform.startswith("win32"):
        return save_locations.get("WindowsLocation") or ""
    return ""


def load_config(
    config_path: Optional[Path] = None,
    days_back_override: Optional[int] = None,
) -> AppConfig:
    """Load PodTube configuration from config.yaml."""
    resolved_path = Path(config_path) if config_path else (PROJECT_ROOT / "config.yaml")
    with open(resolved_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    days_back = (
        days_back_override
        if days_back_override is not None
        else int(raw["defaultDaysToLookBack"])
    )
    previous_run_dt = datetime.strptime(raw["previousRun"], "%Y-%m-%dT%H:%M:%S%z")
    lookback_dt = datetime.now(timezone.utc) - timedelta(days=days_back)
    last_run_timestamp = max(previous_run_dt, lookback_dt)

    included_font = PROJECT_ROOT / raw["IncludedFont"]

    return AppConfig(
        project_root=PROJECT_ROOT,
        config_file=resolved_path,
        days_back=days_back,
        included_font=included_font,
        save_location=_configure_location(raw),
        spreadsheet_url=raw["SpreadsheetURL"],
        api_key=raw.get("APIKey"),
        last_run_timestamp=last_run_timestamp,
        aws_bucket_name=raw["AWS_Bucket_Name"],
        aws_bucket_location=raw["AWS_Bucket_Location"],
        max_threads=int(raw.get("maxThreads", 4)),
    )
