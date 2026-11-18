"""AWS Lambda entry point for scheduled syncs and authenticated private feed serving."""

from dataclasses import asdict
from datetime import datetime, timezone
import hmac
import json
import logging
import os
from pathlib import Path
import tempfile
from typing import Any, Optional
import boto3
from podtube.config import load_config
from podtube.logging_config import setup_logging
from podtube.pipeline import SyncStats, run_sync
from podtube.services.feed import presign_feed_xml
from podtube.services.storage import AWSStorage

logger = logging.getLogger(__name__)

STATE_OBJECT_KEY = "podtube-state.json"


def load_cloud_previous_run(server: AWSStorage) -> Optional[datetime]:
    """Load the last successful sync timestamp from S3 if present."""
    if not server.FileExists(STATE_OBJECT_KEY):
        return None
    with tempfile.TemporaryDirectory() as tmp_dir:
        local_state = Path(tmp_dir) / STATE_OBJECT_KEY
        server.DownloadFile(STATE_OBJECT_KEY, str(local_state))
        if not local_state.exists():
            return None
        try:
            payload = json.loads(local_state.read_text(encoding="utf-8"))
            ts_str = payload.get("previousRun")
            return datetime.fromisoformat(ts_str) if ts_str else None
        except Exception as exc:
            logger.warning("Could not parse %s from S3: %s", STATE_OBJECT_KEY, exc)
            return None


def save_cloud_previous_run(
    server: AWSStorage, run_time: Optional[datetime] = None
) -> str:
    """Persist the latest sync timestamp to S3."""
    ts = (run_time or datetime.now(timezone.utc)).astimezone(timezone.utc)
    formatted_ts = ts.strftime("%Y-%m-%dT%H:%M:%S%z")
    with tempfile.TemporaryDirectory() as tmp_dir:
        local_state = Path(tmp_dir) / STATE_OBJECT_KEY
        local_state.write_text(
            json.dumps({"previousRun": formatted_ts}), encoding="utf-8"
        )
        if server.FileExists(STATE_OBJECT_KEY):
            server.DeleteFile(STATE_OBJECT_KEY)
        server.UploadFile(str(local_state), designatedFileName=STATE_OBJECT_KEY)
    logger.info("Updated %s in S3 to %s", STATE_OBJECT_KEY, formatted_ts)
    return formatted_ts


def send_failure_notification(
    stats: SyncStats,
    sns_topic_arn: str,
    region_name: Optional[str] = None,
) -> None:
    """Publish a failure summary alert to an Amazon SNS topic."""
    sns_client = (
        boto3.client("sns", region_name=region_name)
        if region_name
        else boto3.client("sns")
    )
    subject = (
        f"PodTube Sync Alert: {stats.failed_downloads} failed download(s), "
        f"{stats.channel_errors} channel error(s)"
    )
    message = (
        "PodTube completed a sync run with errors:\n\n"
        f"- Channels Checked: {stats.channels_checked}\n"
        f"- Channels with New Videos: {stats.channels_with_new_videos}\n"
        f"- Episodes Downloaded: {stats.episodes_downloaded}\n"
        f"- Feeds Updated: {stats.feeds_updated}\n"
        f"- Failed Downloads (failed_downloads={stats.failed_downloads}): {stats.failed_downloads}\n"
        f"- Channel Errors (channel_errors={stats.channel_errors}): {stats.channel_errors}\n"
    )
    try:
        sns_client.publish(
            TopicArn=sns_topic_arn,
            Subject=subject[:100],
            Message=message,
        )
        logger.info("Sent failure alert to SNS topic")
    except Exception as exc:
        logger.error("Failed to publish alert to SNS: %s", exc)


def _is_http_event(event: dict[str, Any]) -> bool:
    return "rawPath" in event or "http" in event.get("requestContext", {})


def _extract_request_token(event: dict[str, Any]) -> str:
    query_params = event.get("queryStringParameters") or {}
    if query_params.get("token"):
        return str(query_params["token"])
    headers = {str(k).lower(): str(v) for k, v in (event.get("headers") or {}).items()}
    auth_header = headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return ""


def handle_feed_request(event: dict[str, Any]) -> dict[str, Any]:
    """Serve an authenticated podcast RSS XML feed with temporary S3 presigned URLs."""
    setup_logging(verbose=False)
    cfg = load_config()

    provided_token = _extract_request_token(event)
    if (
        not cfg.feed_token
        or not provided_token
        or not hmac.compare_digest(provided_token, cfg.feed_token)
    ):
        return {
            "statusCode": 403,
            "headers": {"Content-Type": "text/plain"},
            "body": "Forbidden",
        }

    raw_path = str(event.get("rawPath", "")).strip("/")
    parts = [p for p in raw_path.split("/") if p]
    if len(parts) != 2 or parts[0] != "feed":
        return {
            "statusCode": 404,
            "headers": {"Content-Type": "text/plain"},
            "body": "Not Found",
        }

    channel_id = parts[1]
    if channel_id.endswith(".xml"):
        channel_id = channel_id[:-4]
    if not channel_id or ".." in channel_id:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "text/plain"},
            "body": "Invalid channel ID",
        }

    server = AWSStorage(
        cfg.aws_bucket_name,
        cfg.aws_bucket_location,
        public_read=cfg.s3_public_read,
    )
    xml_key = f"{channel_id}/{channel_id}.xml"
    if not server.FileExists(xml_key):
        return {
            "statusCode": 404,
            "headers": {"Content-Type": "text/plain"},
            "body": "Feed Not Found",
        }

    with tempfile.TemporaryDirectory() as tmp_dir:
        local_xml = Path(tmp_dir) / f"{channel_id}.xml"
        server.DownloadFile(xml_key, str(local_xml))
        raw_xml = local_xml.read_text(encoding="utf-8")

    signed_xml = presign_feed_xml(
        raw_xml,
        server,
        bucket_name=cfg.aws_bucket_name,
        expires_in=cfg.presigned_url_expiry_seconds,
    )
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/rss+xml; charset=utf-8",
            "Cache-Control": "private, max-age=300",
        },
        "body": signed_xml,
    }


def handler(event: Optional[dict[str, Any]], context: Any) -> dict[str, Any]:
    """AWS Lambda handler supporting both HTTP Function URL feed requests and scheduled syncs."""
    event = event or {}
    if _is_http_event(event):
        return handle_feed_request(event)

    os.environ.setdefault("PODTUBE_SAVE_LOCATION", "/tmp/podtube")

    verbose = bool(event.get("verbose", False))
    dry_run = bool(event.get("dry_run", False))
    channel_filter = event.get("channel")
    days_back = event.get("days_back")
    previous_run_override = event.get("previous_run") or os.environ.get(
        "PODTUBE_PREVIOUS_RUN"
    )
    cleanup_local = bool(event.get("cleanup_local", True))
    update_timestamp = bool(event.get("update_timestamp", True))

    setup_logging(verbose=verbose)
    sync_start_time = datetime.now(timezone.utc)

    cfg = load_config(days_back_override=days_back)
    Path(cfg.save_dir).mkdir(parents=True, exist_ok=True)

    server = AWSStorage(
        cfg.aws_bucket_name,
        cfg.aws_bucket_location,
        public_read=cfg.s3_public_read,
    )
    if previous_run_override:
        cfg.last_run_timestamp = datetime.fromisoformat(str(previous_run_override))
        logger.info(
            "Using explicit previous_run override: %s",
            cfg.last_run_timestamp.isoformat(),
        )
    elif days_back is None:
        cloud_prev = load_cloud_previous_run(server)
        if cloud_prev is not None:
            cfg.last_run_timestamp = max(cloud_prev, cfg.last_run_timestamp)

    stats = run_sync(
        cfg,
        channel_filter=channel_filter,
        dry_run=dry_run,
        update_timestamp=False,
        cleanup_local=cleanup_local,
    )

    if not dry_run and not channel_filter and update_timestamp:
        if stats.failed_downloads == 0 and stats.channel_errors == 0:
            save_cloud_previous_run(server, sync_start_time)
        else:
            logger.warning(
                "Skipping %s update in S3 due to errors (failed_downloads=%d, channel_errors=%d); "
                "failed items will be retried on the next run.",
                STATE_OBJECT_KEY,
                stats.failed_downloads,
                stats.channel_errors,
            )

    if cfg.sns_topic_arn and (stats.failed_downloads > 0 or stats.channel_errors > 0):
        send_failure_notification(
            stats, cfg.sns_topic_arn, region_name=cfg.aws_region
        )

    return {
        "statusCode": 200,
        "stats": asdict(stats),
    }
