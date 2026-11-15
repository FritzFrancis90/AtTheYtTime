"""Unit tests for pipeline date parsing and local file cleanup."""

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from podtube.config import AppConfig
from podtube.models import Channel, Video
from podtube.pipeline import (
    cleanup_channel_local_files,
    parse_video_published_date,
    run_sync,
)


def _make_test_config(tmp_path: Path) -> AppConfig:
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text('previousRun: "2025-01-19T12:00:00+0000"\n', encoding="utf-8")
    return AppConfig(
        project_root=tmp_path,
        config_file=cfg_file,
        days_back=7,
        included_font=tmp_path / "font.ttf",
        save_location=str(tmp_path),
        save_dir=tmp_path,
        spreadsheet_url="https://example.com/sheet.csv",
        api_key="test-key",
        last_run_timestamp=datetime(2026, 10, 1, tzinfo=timezone.utc),
        aws_bucket_name="test-bucket",
        aws_bucket_location="https://s3-{0}.amazonaws.com/{1}/{2}",
    )


class TestPipeline(unittest.TestCase):
    def test_parse_video_published_date_handles_xml_and_api_formats(self):
        xml_dt = parse_video_published_date("2026-10-04T23:58:25+00:00")
        api_dt = parse_video_published_date("2026-10-04T23:58:25Z")
        api_ms_dt = parse_video_published_date("2026-10-04T23:58:25.500Z")

        expected = datetime(2026, 10, 4, 23, 58, 25, tzinfo=timezone.utc)
        self.assertEqual(xml_dt, expected)
        self.assertEqual(api_dt, expected)
        self.assertEqual(
            api_ms_dt,
            datetime(2026, 10, 4, 23, 58, 25, 500000, tzinfo=timezone.utc),
        )

    def test_cleanup_channel_local_files_removes_channel_dir_and_root_jpgs(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            ch = Channel(
                {
                    "Youtube Channel ID": "UC999",
                    "Youtube Channel Name": "Cleanup Test",
                    "Key Words To Exclude": "",
                    "Key Words To Include": "",
                    "Minute Limit Per Video": "0",
                    "Active": "Y",
                }
            )
            vid = Video(
                {
                    "id": "vid123",
                    "snippet": {
                        "channelTitle": "Cleanup Test",
                        "title": "Ep 1",
                        "description": "Desc",
                        "publishedAt": "2026-10-20T12:00:00.250Z",
                        "liveBroadcastContent": "none",
                        "thumbnails": {"high": {"url": "https://example.com/t.jpg"}},
                    },
                    "contentDetails": {"duration": "PT5M"},
                }
            )
            ch.videoList = [vid]

            channel_dir = base_dir / "UC999"
            channel_dir.mkdir(parents=True)
            (channel_dir / "vid123.mp3").write_bytes(b"mp3data")
            (channel_dir / "UC999.xml").write_text("<rss/>", encoding="utf-8")
            root_jpg = base_dir / "vid123.jpg"
            root_jpg.write_bytes(b"jpgdata")

            cleanup_channel_local_files(ch, base_dir)

            self.assertFalse(channel_dir.exists())
            self.assertFalse(root_jpg.exists())

    def test_run_sync_with_fractional_seconds_and_cleanup_local(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            cfg = _make_test_config(base_dir)

            ch = Channel(
                {
                    "Youtube Channel ID": "UC123",
                    "Youtube Channel Name": "Test Channel",
                    "Key Words To Exclude": "",
                    "Key Words To Include": "",
                    "Minute Limit Per Video": "0",
                    "Active": "Y",
                }
            )
            vid = Video(
                {
                    "id": "v001",
                    "snippet": {
                        "channelTitle": "Test Channel",
                        "title": "API Fallback Video",
                        "description": "Desc",
                        "publishedAt": "2026-10-20T12:00:00.123Z",
                        "liveBroadcastContent": "none",
                        "thumbnails": {"high": {"url": "https://example.com/t.jpg"}},
                    },
                    "contentDetails": {"duration": "PT5M"},
                }
            )

            def fake_download(save_dir, channel_id, ffmpeg_location=None):
                mp3_file = Path(save_dir) / "v001.mp3"
                mp3_file.write_bytes(b"fake-mp3")
                vid.fileLocation = str(mp3_file)
                return True

            vid.DownloadVideoAsAudio = MagicMock(side_effect=fake_download)

            with patch("podtube.pipeline.get_channels", return_value=[ch]), patch(
                "podtube.pipeline.VideoQuery"
            ) as mock_vq_cls, patch(
                "podtube.pipeline.AWSStorage"
            ) as mock_s3_cls, patch(
                "podtube.pipeline.create_podcast_image",
                return_value=str(base_dir / "UC123" / "cover.jpg"),
            ), patch(
                "podtube.services.feed.podgen.Media.populate_duration_from"
            ):
                mock_vq = mock_vq_cls.return_value
                mock_vq.GetVideosFromChannel.return_value = [vid]

                mock_s3 = mock_s3_cls.return_value
                mock_s3.FileExists.return_value = False
                mock_s3.GetProposedNewFileLocation.return_value = (
                    "https://s3.amazonaws.com/test-bucket/UC123/v001.mp3"
                )
                mock_s3.UploadFile.return_value = (
                    "https://s3.amazonaws.com/test-bucket/UC123/v001.mp3"
                )

                stats = run_sync(
                    cfg,
                    dry_run=False,
                    update_timestamp=False,
                    cleanup_local=True,
                )

                self.assertEqual(stats.episodes_downloaded, 1)
                self.assertEqual(stats.feeds_updated, 1)
                self.assertFalse((base_dir / "UC123").exists())


if __name__ == "__main__":
    unittest.main()

