"""Unit tests for AWS Lambda handler and S3 cloud state persistence."""

from datetime import datetime, timezone
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from podtube.config import AppConfig
from podtube.lambda_handler import (
    STATE_OBJECT_KEY,
    handler,
    load_cloud_previous_run,
    save_cloud_previous_run,
)
from podtube.pipeline import SyncStats


class TestLambdaHandler(unittest.TestCase):
    def test_save_and_load_cloud_previous_run(self):
        mock_server = MagicMock()
        saved_payload = {}

        def fake_upload(filepath, designatedFileName=None):
            saved_payload["key"] = designatedFileName
            saved_payload["content"] = Path(filepath).read_text(encoding="utf-8")
            return "https://s3.amazonaws.com/bucket/podtube-state.json"

        mock_server.UploadFile.side_effect = fake_upload

        ts = datetime(2026, 11, 15, 16, 0, 0, tzinfo=timezone.utc)
        formatted = save_cloud_previous_run(mock_server, ts)
        self.assertEqual(formatted, "2026-11-15T16:00:00+0000")
        self.assertEqual(saved_payload["key"], STATE_OBJECT_KEY)
        self.assertEqual(
            json.loads(saved_payload["content"]),
            {"previousRun": "2026-11-15T16:00:00+0000"},
        )

        # Now verify loading it back from S3
        mock_server.FileExists.return_value = True

        def fake_download(filename, designatedFileName=None):
            Path(designatedFileName).write_text(
                saved_payload["content"], encoding="utf-8"
            )

        mock_server.DownloadFile.side_effect = fake_download

        loaded_dt = load_cloud_previous_run(mock_server)
        self.assertEqual(loaded_dt, ts)

    def test_lambda_handler_executes_sync_and_updates_cloud_state(self):
        fake_cfg = AppConfig(
            project_root=Path("/tmp"),
            config_file=Path("/tmp/config.yaml"),
            days_back=7,
            included_font=Path("/tmp/font.ttf"),
            save_location="/tmp/podtube",
            save_dir=Path("/tmp/podtube"),
            spreadsheet_url="https://example.com/sheet.csv",
            api_key="test-key",
            last_run_timestamp=datetime(2026, 11, 10, tzinfo=timezone.utc),
            aws_bucket_name="test-bucket",
            aws_bucket_location="https://s3-{0}.amazonaws.com/{1}/{2}",
        )
        fake_stats = SyncStats(
            channels_checked=5,
            channels_with_new_videos=1,
            episodes_downloaded=2,
            feeds_updated=1,
        )

        with patch("podtube.lambda_handler.setup_logging"), patch(
            "podtube.lambda_handler.load_config", return_value=fake_cfg
        ), patch("podtube.lambda_handler.AWSStorage") as mock_s3_cls, patch(
            "podtube.lambda_handler.load_cloud_previous_run",
            return_value=datetime(2026, 11, 14, tzinfo=timezone.utc),
        ), patch(
            "podtube.lambda_handler.run_sync", return_value=fake_stats
        ) as mock_run_sync, patch(
            "podtube.lambda_handler.save_cloud_previous_run",
            return_value="2026-11-15T16:00:00+0000",
        ) as mock_save_state:
            response = handler({"dry_run": False}, context=None)

            self.assertEqual(response["statusCode"], 200)
            self.assertEqual(response["stats"]["channels_checked"], 5)
            self.assertEqual(response["stats"]["episodes_downloaded"], 2)
            # Cloud timestamp (Nov 14) is newer than config cutoff (Nov 10)
            self.assertEqual(
                fake_cfg.last_run_timestamp,
                datetime(2026, 11, 14, tzinfo=timezone.utc),
            )
            mock_run_sync.assert_called_once_with(
                fake_cfg,
                channel_filter=None,
                dry_run=False,
                update_timestamp=False,
                cleanup_local=True,
            )
            mock_save_state.assert_called_once()
            self.assertEqual(
                mock_save_state.call_args[0][0], mock_s3_cls.return_value
            )


if __name__ == "__main__":
    unittest.main()

