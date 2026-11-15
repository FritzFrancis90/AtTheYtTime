# PodTube (AtTheYtTime)

A CLI tool that monitors configured YouTube channels, extracts audio and artwork from new uploads, and publishes podcast RSS feeds to AWS S3.

## Installation

From the project root directory, install the package in editable mode:

```bash
pip3 install -e .
```

To also install development/testing dependencies (`pytest`, `ruff`):

```bash
pip3 install -e ".[dev]"
```

## Usage

Once installed, the `podtube` command is available from any directory:

```bash
# Run a full sync across all active channels
podtube sync

# Preview new videos without downloading or uploading
podtube sync --dry-run -v

# Sync a specific channel (by name or channel ID) looking back 14 days
podtube sync --channel "Channel Name" --days-back 14

# Run a full sync and delete local MP3/artwork/XML files after uploading to S3
podtube sync --cleanup-local

# List active channels from the configured Google Sheet
podtube channels

# List all channels (including inactive ones)
podtube channels --all
```

## Configuration & Environment Variables

Configuration is loaded from `config.yaml` (see `config.example.yaml` for the template). The following environment variables can be used to override `config.yaml` values (e.g., in cloud environments):

* `PODTUBE_SPREADSHEET_URL`
* `PODTUBE_API_KEY`
* `PODTUBE_AWS_BUCKET_NAME`
* `PODTUBE_AWS_BUCKET_LOCATION`
* `PODTUBE_SAVE_LOCATION`
* `PODTUBE_FFMPEG_LOCATION`

## Running Unit Tests

```bash
python3 -m unittest discover -s tests -v
```

