"""Configuration loading and validation for PodTube."""

import os
import re
import shutil
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
    save_dir: Path
    spreadsheet_url: str
    api_key: Optional[str]
    last_run_timestamp: datetime
    aws_bucket_name: str
    aws_bucket_location: str
    ffmpeg_location: Optional[str] = None
    max_threads: int = 4


def _configure_location(raw_config: dict) -> str:
    env_override = os.environ.get("PODTUBE_SAVE_LOCATION")
    if env_override:
        return env_override
    save_locations = raw_config.get("SaveLocation", {})
    if sys.platform.startswith("linux"):
        return save_locations.get("LinuxLocation") or ""
    if sys.platform.startswith("darwin"):
        return save_locations.get("MacOSLocation") or ""
    if sys.platform.startswith("win32"):
        return save_locations.get("WindowsLocation") or ""
    return ""


def resolve_ffmpeg_location(raw_config: Optional[dict] = None) -> Optional[str]:
    """Resolve the ffmpeg binary path via env var, config.yaml, PATH, or common macOS locations."""
    candidates = [
        os.environ.get("PODTUBE_FFMPEG_LOCATION"),
        (raw_config or {}).get("FFmpegLocation"),
        shutil.which("ffmpeg"),
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/usr/local/Cellar/ffmpeg/7.1.1_2/bin/ffmpeg",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    return None


def load_config(
    config_path: Optional[Path] = None,
    days_back_override: Optional[int] = None,
) -> AppConfig:
    """Load PodTube configuration from config.yaml with optional environment variable overrides."""
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
    save_location = _configure_location(raw)
    save_dir = Path(save_location) if save_location else PROJECT_ROOT

    return AppConfig(
        project_root=PROJECT_ROOT,
        config_file=resolved_path,
        days_back=days_back,
        included_font=included_font,
        save_location=save_location,
        save_dir=save_dir,
        spreadsheet_url=os.environ.get("PODTUBE_SPREADSHEET_URL") or raw["SpreadsheetURL"],
        api_key=os.environ.get("PODTUBE_API_KEY") or raw.get("APIKey"),
        last_run_timestamp=last_run_timestamp,
        aws_bucket_name=os.environ.get("PODTUBE_AWS_BUCKET_NAME") or raw["AWS_Bucket_Name"],
        aws_bucket_location=os.environ.get("PODTUBE_AWS_BUCKET_LOCATION") or raw["AWS_Bucket_Location"],
        ffmpeg_location=resolve_ffmpeg_location(raw),
        max_threads=int(raw.get("maxThreads", 4)),
    )


def update_previous_run(config_path: Path, run_time: Optional[datetime] = None) -> str:
    """Update the previousRun timestamp in config.yaml while preserving comments and formatting."""
    ts = (run_time or datetime.now(timezone.utc)).astimezone(timezone.utc)
    formatted_ts = ts.strftime("%Y-%m-%dT%H:%M:%S%z")
    content = config_path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'^(previousRun:\s*).*$',
        rf'\1"{formatted_ts}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if count == 0:
        updated = content.rstrip() + f'\npreviousRun: "{formatted_ts}"\n'
    config_path.write_text(updated, encoding="utf-8")
    return formatted_ts
