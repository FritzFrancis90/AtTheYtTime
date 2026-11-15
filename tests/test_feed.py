"""Unit tests for PodcastFeed creation and merging old RSS XML feeds."""

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from podtube.services.feed import PodcastFeed, add_old_episodes_to_new_feed


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


if __name__ == "__main__":
    unittest.main()

