"""Unit tests for Channel and Video models."""

import unittest
import xml.etree.ElementTree as ET
from podtube.models import Channel, Video


SAMPLE_XML_ENTRY = """
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns:media="http://search.yahoo.com/mrss/">
  <entry>
    <yt:videoId>abc123xyz</yt:videoId>
    <title>Episode 42 - Deep Dive</title>
    <published>2026-10-20T14:30:00+00:00</published>
    <author>
      <name>Test Creator</name>
    </author>
    <media:group>
      <media:description>Show notes go here</media:description>
      <media:thumbnail url="https://i.ytimg.com/vi/abc123xyz/hqdefault.jpg"/>
    </media:group>
  </entry>
</feed>
"""

XML_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}


def make_channel_row(**overrides) -> dict:
    row = {
        "Youtube Channel ID": " UC1234567890 ",
        "Youtube Channel Name": " Test Channel ",
        "Key Words To Exclude": "",
        "Key Words To Include": "",
        "Minute Limit Per Video": "0",
        "Active": "Y",
    }
    row.update(overrides)
    return row


def make_api_video_item(
    video_id: str = "vid001",
    title: str = "Sample Video",
    published_at: str = "2026-10-20T12:00:00Z",
    duration: str = "PT10M",
    live_content: str = "none",
) -> dict:
    return {
        "id": video_id,
        "snippet": {
            "channelTitle": "Test Creator",
            "title": title,
            "description": "API description",
            "publishedAt": published_at,
            "liveBroadcastContent": live_content,
            "thumbnails": {
                "high": {"url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"}
            },
        },
        "contentDetails": {
            "duration": duration,
        },
    }


class TestModels(unittest.TestCase):
    def test_channel_strips_whitespace_and_parses_limits(self):
        ch = Channel(
            make_channel_row(
                **{
                    "Minute Limit Per Video": " 15 ",
                    "Active": "N",
                }
            )
        )
        self.assertEqual(ch.ID, "UC1234567890")
        self.assertEqual(ch.Name, "Test Channel")
        self.assertEqual(ch.maxLength, 900)
        self.assertEqual(ch.isActive, 0)

    def test_video_from_xml_entry(self):
        root = ET.fromstring(SAMPLE_XML_ENTRY)
        entry = root.find("atom:entry", XML_NS)
        video = Video(entry, XML_NS)

        self.assertEqual(video.ID, "abc123xyz")
        self.assertEqual(video.Creator, "Test Creator")
        self.assertEqual(video.Title, "Episode 42 - Deep Dive")
        self.assertEqual(video.description, "Show notes go here")
        self.assertEqual(video.datePublished, "2026-10-20T14:30:00+00:00")
        self.assertEqual(
            video.thumbnailURL, "https://i.ytimg.com/vi/abc123xyz/hqdefault.jpg"
        )
        self.assertEqual(video.isValidDownload, 1)

    def test_video_from_api_dict_and_live_broadcast(self):
        normal_video = Video(make_api_video_item(duration="PT5M30S"))
        self.assertEqual(normal_video.duration, 330.0)
        self.assertEqual(normal_video.isValidDownload, 1)

        live_video = Video(make_api_video_item(live_content="live"))
        self.assertEqual(live_video.isValidDownload, 0)
        self.assertEqual(live_video.duration, 0)

    def test_channel_apply_filters(self):
        ch = Channel(
            make_channel_row(
                **{
                    "Key Words To Include": "Podcast,Interview",
                    "Key Words To Exclude": "Shorts,#shorts",
                    "Minute Limit Per Video": "20",
                }
            )
        )
        v_valid = Video(
            make_api_video_item(
                video_id="v1", title="Podcast Ep 1", duration="PT15M"
            )
        )
        v_too_long = Video(
            make_api_video_item(
                video_id="v2", title="Podcast Ep 2", duration="PT25M"
            )
        )
        v_missing_include = Video(
            make_api_video_item(
                video_id="v3", title="Random Vlog", duration="PT10M"
            )
        )
        v_excluded = Video(
            make_api_video_item(
                video_id="v4", title="Podcast Clip #shorts", duration="PT1M"
            )
        )
        v_already_loaded = Video(
            make_api_video_item(
                video_id="v5", title="Interview Guest", duration="PT10M"
            )
        )
        v_already_loaded.alreadyLoaded = 1

        ch.videoList = [
            v_valid,
            v_too_long,
            v_missing_include,
            v_excluded,
            v_already_loaded,
        ]
        ch.ApplyFilters()

        self.assertEqual([v.ID for v in ch.videoList], ["v1"])

    def test_get_most_recent_video(self):
        ch = Channel(make_channel_row())
        v_older = Video(
            make_api_video_item(
                video_id="old", published_at="2026-10-18T12:00:00Z"
            )
        )
        v_newer = Video(
            make_api_video_item(
                video_id="new", published_at="2026-10-21T12:00:00Z"
            )
        )
        ch.videoList = [v_older, v_newer]
        self.assertEqual(ch.GetMostRecentVideo().ID, "new")


if __name__ == "__main__":
    unittest.main()

