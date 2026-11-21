"""Unit tests for PodcastFeed creation and merging old RSS XML feeds."""

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock
import xml.etree.ElementTree as ET
from podtube.services.feed import (
    PodcastFeed,
    add_old_episodes_to_new_feed,
    extract_s3_key_from_url,
    presign_feed_xml,
)


class TestFeed(unittest.TestCase):
    def test_hours_to_skip_is_valid_hour_list(self):
        self.assertEqual(
            PodcastFeed.hoursToSkip,
            [0, 1, 2, 3, 4, 5, 19, 20, 21, 22, 23],
        )

    def test_export_feed_and_merge_old_episodes(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)

            # 1. Create an initial feed with one episode and export it
            old_feed = PodcastFeed("Test Channel", save_location=base_dir)
            old_feed.AddEpisode(
                "https://example.com/UC123/ep1.mp3",
                datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc),
                "Episode 1",
                "First episode description",
            )
            rel_path = old_feed.ExportFeed("UC123", save_location=base_dir)
            exported_xml_path = base_dir / rel_path
            self.assertTrue(exported_xml_path.exists())

            # 2. Create a new feed with Episode 2 and merge Episode 1 from the exported XML
            new_feed = PodcastFeed("Test Channel", save_location=base_dir)
            new_feed.AddEpisode(
                "https://example.com/UC123/ep2.mp3",
                datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc),
                "Episode 2",
                "Second episode description",
            )
            add_old_episodes_to_new_feed(exported_xml_path, new_feed)

            titles = [ep.title for ep in new_feed.p.episodes]
            self.assertEqual(titles, ["Episode 2", "Episode 1"])

    def test_extract_s3_key_from_url_supports_path_and_virtual_hosted_styles(self):
        bucket = "ffrancis-podtube-bucket"
        self.assertEqual(
            extract_s3_key_from_url(
                f"https://s3-us-east-1.amazonaws.com/{bucket}/UC123/vid1.mp3", bucket
            ),
            "UC123/vid1.mp3",
        )
        self.assertEqual(
            extract_s3_key_from_url(
                f"https://s3-None.amazonaws.com/{bucket}/UC123/vid1.mp3", bucket
            ),
            "UC123/vid1.mp3",
        )
        self.assertEqual(
            extract_s3_key_from_url(
                f"https://{bucket}.s3.us-east-1.amazonaws.com/UC123/cover.jpg", bucket
            ),
            "UC123/cover.jpg",
        )
        self.assertIsNone(
            extract_s3_key_from_url("https://example.com/other/file.mp3", bucket)
        )

    def test_presign_feed_xml_rewrites_enclosures_and_images(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            bucket = "ffrancis-podtube-bucket"

            feed = PodcastFeed("Private Show", save_location=base_dir)
            feed.SetFeedImage(
                f"https://s3-us-east-1.amazonaws.com/{bucket}/UC123/cover.jpg"
            )
            feed.AddEpisode(
                f"https://s3-us-east-1.amazonaws.com/{bucket}/UC123/ep1.mp3",
                datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc),
                "Private Episode 1",
                "Description",
            )
            rel_path = feed.ExportFeed("UC123", save_location=base_dir)
            raw_xml = (base_dir / rel_path).read_text(encoding="utf-8")

            mock_storage = MagicMock()
            mock_storage.GeneratePresignedUrl.side_effect = (
                lambda key, expires_in=604800: f"https://{bucket}.s3.amazonaws.com/{key}?X-Amz-Signature=sig123&Expires={expires_in}"
            )

            signed_xml = presign_feed_xml(
                raw_xml, mock_storage, bucket_name=bucket, expires_in=3600
            )
            root = ET.fromstring(signed_xml)
            channel_el = root.find("channel")
            enclosure_url = channel_el.find("item").find("enclosure").attrib["url"]
            itunes_image_href = channel_el.find(
                "{http://www.itunes.com/dtds/podcast-1.0.dtd}image"
            ).attrib["href"]

            self.assertEqual(
                enclosure_url,
                f"https://{bucket}.s3.amazonaws.com/UC123/ep1.mp3?X-Amz-Signature=sig123&Expires=3600",
            )
            self.assertEqual(
                itunes_image_href,
                f"https://{bucket}.s3.amazonaws.com/UC123/cover.jpg?X-Amz-Signature=sig123&Expires=3600",
            )


if __name__ == "__main__":
    unittest.main()

