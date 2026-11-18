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
DEFAULT_FONT_REL_PATH = "fonts/Oswald/static/Oswald-Regular.ttf"


def resolve_project_root() -> Path:
    """Resolve the active project root (supporting AWS Lambda's LAMBDA_TASK_ROOT and editable installs)."""
    lambda_root = os.environ.get("LAMBDA_TASK_ROOT")
    if lambda_root and (Path(lambda_root) / "config.yaml").exists():
        return Path(lambda_root)
    if (PROJECT_ROOT / "config.yaml").exists():
        return PROJECT_ROOT
    return Path.cwd()


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
    dynamodb_table_name: Optional[str] = None
    aws_region: Optional[str] = None
    sns_topic_arn: Optional[str] = None
    cloud_provider: str = "aws"
    proxy_url: Optional[str] = None
    feed_token: Optional[str] = None
    s3_public_read: bool = True
    presigned_url_expiry_seconds: int = 604800


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


def _parse_optional_bool(value) -> Optional[bool]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("true", "1", "yes", "y"):
        return True
    if text in ("false", "0", "no", "n"):
        return False
    return None


def load_config(
    config_path: Optional[Path] = None,
    days_back_override: Optional[int] = None,
) -> AppConfig:
    """Load PodTube configuration from config.yaml with optional environment variable overrides."""
    project_root = resolve_project_root()
    resolved_path = Path(config_path) if config_path else (project_root / "config.yaml")
    with open(resolved_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    days_back = (
        days_back_override
        if days_back_override is not None
        else int(raw.get("defaultDaysToLookBack") or 7)
    )
    previous_run_dt = datetime.strptime(raw["previousRun"], "%Y-%m-%dT%H:%M:%S%z")
    lookback_dt = datetime.now(timezone.utc) - timedelta(days=days_back)
    last_run_timestamp = max(previous_run_dt, lookback_dt)

    font_rel = raw.get("IncludedFont") or DEFAULT_FONT_REL_PATH
    included_font = project_root / font_rel
    save_location = _configure_location(raw)
    save_dir = Path(save_location) if save_location else project_root

    proxy_url = os.environ.get("PODTUBE_PROXY_URL") or raw.get("Proxy_URL")
    feed_token = os.environ.get("PODTUBE_FEED_TOKEN") or raw.get("Feed_Token")
    raw_public_read = _parse_optional_bool(
        os.environ.get("PODTUBE_S3_PUBLIC_READ")
        if "PODTUBE_S3_PUBLIC_READ" in os.environ
        else raw.get("S3_Public_Read")
    )
    s3_public_read = raw_public_read if raw_public_read is not None else (not bool(feed_token))
    presigned_expiry = int(
        os.environ.get("PODTUBE_PRESIGNED_URL_EXPIRY")
        or raw.get("Presigned_URL_Expiry")
        or 604800
    )

    return AppConfig(
        project_root=project_root,
        config_file=resolved_path,
        days_back=days_back,
        included_font=included_font,
        save_location=save_location,
        save_dir=save_dir,
        spreadsheet_url=os.environ.get("PODTUBE_SPREADSHEET_URL") or raw.get("SpreadsheetURL") or "",
        api_key=os.environ.get("PODTUBE_API_KEY") or raw.get("APIKey"),
        last_run_timestamp=last_run_timestamp,
        aws_bucket_name=os.environ.get("PODTUBE_AWS_BUCKET_NAME") or raw.get("AWS_Bucket_Name") or "",
        aws_bucket_location=os.environ.get("PODTUBE_AWS_BUCKET_LOCATION") or raw.get("AWS_Bucket_Location") or "",
        ffmpeg_location=resolve_ffmpeg_location(raw),
        max_threads=int(raw.get("maxThreads") or 4),
        dynamodb_table_name=os.environ.get("PODTUBE_DYNAMODB_TABLE") or raw.get("DynamoDB_Table_Name"),
        aws_region=(
            os.environ.get("PODTUBE_AWS_REGION")
            or os.environ.get("AWS_REGION")
            or raw.get("AWS_Region")
        ),
        sns_topic_arn=os.environ.get("PODTUBE_SNS_TOPIC_ARN") or raw.get("SNS_Topic_ARN"),
        cloud_provider=(
            os.environ.get("PODTUBE_CLOUD_PROVIDER")
            or raw.get("Cloud_Provider")
            or "aws"
        ),
        proxy_url=proxy_url,
        feed_token=feed_token,
        s3_public_read=s3_public_read,
        presigned_url_expiry_seconds=presigned_expiry,
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
