# PodTube (AtTheYtTime)

A CLI tool and serverless AWS Lambda pipeline that monitors configured YouTube channels, extracts audio and artwork from new uploads, and publishes podcast RSS feeds to Amazon S3.

## Features

* **Resilient YouTube Discovery**: Queries public YouTube RSS XML feeds with retry/backoff and falls back once to the YouTube Data API v3 (`playlistItems` on the channel's `UU...` uploads playlist) if the XML feed fails.
* **Channel Management**: Supports **Amazon DynamoDB** (`podtube-channels`) or a published **Google Sheet CSV**, with a one-command `podtube import-sheet` migration tool.
* **Private Podcast Feeds**: Optionally serves RSS feeds via an authenticated **AWS Lambda Function URL** (`/feed/<channel_id>?token=...`) that dynamically generates temporary **S3 Presigned URLs** for episode audio and artwork—allowing your S3 bucket to block all public access.
* **Cloud-Ready & Decoupled**: Uses Ports & Adapters (`StorageProvider`, `ChannelRepository`, `NotificationProvider`) in `src/podtube/services/interfaces.py` and `factory.py`, S3-backed state persistence (`podtube-state.json`), and **Amazon SNS** failure alerts.

---

## Installation

From the project root directory, install the package in editable mode:

```bash
pip3 install -e .
```

To also install development/testing dependencies (`pytest`, `ruff`):

```bash
pip3 install -e ".[dev]"
```

---

## CLI Usage

Once installed, the `podtube` command is available from any directory:

```bash
# Run a full sync across all active channels
podtube sync

# Preview new videos without downloading or uploading
podtube sync --dry-run -v

# Sync a specific channel (by name or channel ID) looking back 14 days
podtube sync --channel "Channel Name" --days-back 14

# Run a full sync without advancing previousRun in config.yaml
podtube sync --no-update-timestamp

# Run a full sync and delete local MP3/artwork/XML files after uploading to S3
podtube sync --cleanup-local

# Save full debug logs to a file
podtube sync --log-file podtube.log

# List active channels (from DynamoDB if configured, otherwise Google Sheet)
podtube channels

# List all channels (including inactive ones) from a specific DynamoDB table
podtube channels --table podtube-channels --all

# One-time migration of channels from Google Sheet CSV into DynamoDB
podtube import-sheet --table podtube-channels
```

---

## AWS Lambda Deployment & Private Feeds

PodTube includes a `Dockerfile` (`public.ecr.aws/lambda/python:3.12` + static `ffmpeg`/`ffprobe`) and `podtube.lambda_handler.handler`:

* **Automated Deployment**: Run `./scripts/deploy.sh` from your terminal to execute the unit test suite, build the `linux/amd64` Docker image, push it to Amazon ECR, and update the `podtube-sync` Lambda function.
* **Scheduled Syncs (EventBridge)**: Triggered on a schedule (e.g., hourly). Persists `previousRun` in `podtube-state.json` on S3, and skips advancing the timestamp if any channel or download errors occur so failed items are retried on the next run.
* **Failure Alerts (SNS)**: When `PODTUBE_SNS_TOPIC_ARN` is set, publishes an alert email whenever `failed_downloads > 0` or `channel_errors > 0`.
* **Private Feed Endpoint (Lambda Function URL)**:
  * Subscribe your podcast app to:
    ```text
    https://<your-lambda-url>/feed/<channel_id>?token=<PODTUBE_FEED_TOKEN>
    ```
    *(Also supports `Authorization: Bearer <token>`).*
  * When `PODTUBE_FEED_TOKEN` is set, `s3_public_read` defaults to `False` so new objects are uploaded privately without `ACL='public-read'`, and you can enable **Block all public access** on your S3 bucket.
* **Lambda Manual Test Overrides**: Invoke the Lambda function with a test JSON event to override options on the fly:
  ```json
  {
    "dry_run": true,
    "verbose": true,
    "channel": "Channel Name",
    "previous_run": "2026-11-15T00:00:00+00:00"
  }
  ```

---

## Configuration & Environment Variables

Configuration is loaded from `config.yaml` (see `config.example.yaml` for the template). The following environment variables override `config.yaml` values:

| Environment Variable | Description |
| :--- | :--- |
| `PODTUBE_CLOUD_PROVIDER` | Cloud provider adapter (`aws` by default) |
| `PODTUBE_AWS_REGION` / `AWS_REGION` | AWS region (e.g. `us-east-1`) |
| `PODTUBE_AWS_BUCKET_NAME` | Target S3 bucket name |
| `PODTUBE_AWS_BUCKET_LOCATION` | S3 URL format string |
| `PODTUBE_DYNAMODB_TABLE` | DynamoDB table name for channel configs (if unset, uses Google Sheet) |
| `PODTUBE_SPREADSHEET_URL` | Published Google Sheet CSV URL |
| `PODTUBE_API_KEY` | YouTube Data API v3 key (used for fallback) |
| `PODTUBE_SNS_TOPIC_ARN` | SNS topic ARN for failure alerts |
| `PODTUBE_FEED_TOKEN` | Secret token required by the Lambda Function URL `/feed/<channel_id>` endpoint |
| `PODTUBE_S3_PUBLIC_READ` | `true` or `false` (defaults to `false` when `PODTUBE_FEED_TOKEN` is set) |
| `PODTUBE_PRESIGNED_URL_EXPIRY` | Presigned S3 URL lifetime in seconds (default: `604800` / 7 days) |
| `PODTUBE_PROXY_URL` | Optional HTTP/SOCKS proxy URL passed to `yt-dlp` |
| `PODTUBE_PREVIOUS_RUN` | Optional ISO-8601 cutoff timestamp override in Lambda |
| `PODTUBE_SAVE_LOCATION` | Local working directory for audio/artwork (`/tmp/podtube` in Lambda) |
| `PODTUBE_FFMPEG_LOCATION` | Path to `ffmpeg` binary (auto-detected if unset) |

---

## Running Unit Tests & CI

GitHub Actions (`.github/workflows/deploy.yml`) automatically runs the unit test suite on Pull Requests and merges into `main`. To run all tests locally:

```bash
python3 -m unittest discover -s tests -v
```
