"""Unit tests for configuration loading and timestamp updating."""

from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from podtube.config import load_config, update_previous_run


SAMPLE_CONFIG_YAML = """# Top comment preserved
SpreadsheetURL: https://example.com/sheet.csv
APIKey: test-api-key
AWS_Bucket_Name: test-bucket
AWS_Bucket_Location: https://s3-{0}.amazonaws.com/{1}/{2}
IncludedFont: fonts/Oswald/static/Oswald-Regular.ttf
previousRun: "2025-01-19T12:00:00+0000"
SaveLocation:
    MacOSLocation: /tmp/podtube-mac/
    LinuxLocation: /tmp/podtube-linux/
    WindowsLocation: C:/temp/podtube/
defaultDaysToLookBack: 7
maxThreads: 4
# Bottom comment preserved
"""


class TestConfig(unittest.TestCase):
    def test_load_config_and_days_back_override(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg_file = Path(tmp_dir) / "config.yaml"
            cfg_file.write_text(SAMPLE_CONFIG_YAML, encoding="utf-8")

            cfg = load_config(config_path=cfg_file, days_back_override=14)
            self.assertEqual(cfg.days_back, 14)
            self.assertEqual(cfg.aws_bucket_name, "test-bucket")
            self.assertEqual(cfg.api_key, "test-api-key")
            self.assertEqual(cfg.max_threads, 4)

    def test_env_var_overrides(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg_file = Path(tmp_dir) / "config.yaml"
            cfg_file.write_text(SAMPLE_CONFIG_YAML, encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "PODTUBE_API_KEY": "env-secret-key",
                    "PODTUBE_AWS_BUCKET_NAME": "env-bucket",
                    "PODTUBE_PROXY_URL": "http://user:pass@proxy.example.com:12321",
                },
            ):
                cfg = load_config(config_path=cfg_file)
                self.assertEqual(cfg.api_key, "env-secret-key")
                self.assertEqual(cfg.aws_bucket_name, "env-bucket")
                self.assertEqual(
                    cfg.proxy_url, "http://user:pass@proxy.example.com:12321"
                )

    def test_update_previous_run_preserves_comments(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg_file = Path(tmp_dir) / "config.yaml"
            cfg_file.write_text(SAMPLE_CONFIG_YAML, encoding="utf-8")

            target_dt = datetime(2026, 11, 15, 14, 0, 0, tzinfo=timezone.utc)
            formatted = update_previous_run(cfg_file, target_dt)

            self.assertEqual(formatted, "2026-11-15T14:00:00+0000")
            updated_text = cfg_file.read_text(encoding="utf-8")
            self.assertIn('previousRun: "2026-11-15T14:00:00+0000"', updated_text)
            self.assertIn("# Top comment preserved", updated_text)
            self.assertIn("# Bottom comment preserved", updated_text)

    def test_lambda_task_root_and_example_config_fallback(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            task_root = Path(tmp_dir)
            # Simulate config.example.yaml where fields like IncludedFont are blank
            minimal_yaml = (
                "SpreadsheetURL:\n"
                "APIKey:\n"
                "AWS_Bucket_Name:\n"
                "AWS_Bucket_Location:\n"
                "IncludedFont:\n"
                'previousRun: "2025-01-19T12:00:00+0000"\n'
                "SaveLocation:\n"
                "    MacOSLocation:\n"
                "    LinuxLocation:\n"
                "    WindowsLocation:\n"
                "defaultDaysToLookBack: 7\n"
                "maxThreads: 4\n"
            )
            (task_root / "config.yaml").write_text(minimal_yaml, encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "LAMBDA_TASK_ROOT": str(task_root),
                    "PODTUBE_SPREADSHEET_URL": "https://example.com/sheet.csv",
                    "PODTUBE_API_KEY": "lambda-key",
                    "PODTUBE_AWS_BUCKET_NAME": "lambda-bucket",
                    "PODTUBE_AWS_BUCKET_LOCATION": "https://s3-{0}.amazonaws.com/{1}/{2}",
                },
            ):
                cfg = load_config()
                self.assertEqual(cfg.project_root, task_root)
                self.assertEqual(cfg.config_file, task_root / "config.yaml")
                self.assertEqual(
                    cfg.included_font,
                    task_root / "fonts/Oswald/static/Oswald-Regular.ttf",
                )
                self.assertEqual(cfg.aws_bucket_name, "lambda-bucket")

    def test_feed_token_and_s3_public_read_defaults(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg_file = Path(tmp_dir) / "config.yaml"
            cfg_file.write_text(SAMPLE_CONFIG_YAML, encoding="utf-8")

            # Without feed token, s3_public_read defaults to True for backwards compatibility
            cfg_default = load_config(config_path=cfg_file)
            self.assertIsNone(cfg_default.feed_token)
            self.assertTrue(cfg_default.s3_public_read)

            # With PODTUBE_FEED_TOKEN set, s3_public_read automatically defaults to False
            with patch.dict(os.environ, {"PODTUBE_FEED_TOKEN": "my-secret-token"}):
                cfg_private = load_config(config_path=cfg_file)
                self.assertEqual(cfg_private.feed_token, "my-secret-token")
                self.assertFalse(cfg_private.s3_public_read)

            # Explicit PODTUBE_S3_PUBLIC_READ overrides the default
            with patch.dict(
                os.environ,
                {
                    "PODTUBE_FEED_TOKEN": "my-secret-token",
                    "PODTUBE_S3_PUBLIC_READ": "true",
                },
            ):
                cfg_override = load_config(config_path=cfg_file)
                self.assertTrue(cfg_override.s3_public_read)


if __name__ == "__main__":
    unittest.main()

