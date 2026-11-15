"""Unit tests for YouTube RSS lookup and Data API v3 playlistItems fallback."""

from datetime import datetime, timezone
import unittest
from unittest.mock import patch
from urllib import error as urllib_error
from podtube.services.youtube import VideoQuery, get_uploads_playlist_id


class TestYouTubeService(unittest.TestCase):
    def test_get_uploads_playlist_id_converts_uc_to_uu(self):
        self.assertEqual(get_uploads_playlist_id("UC1234567890"), "UU1234567890")
        self.assertEqual(get_uploads_playlist_id(" UCabcdef "), "UUabcdef")
        self.assertEqual(get_uploads_playlist_id("UUalready"), "UUalready")

    def test_get_videos_returns_xml_results_when_successful(self):
        query_service = VideoQuery(api_key="dummy-key")
        cutoff = datetime(2026, 10, 1, tzinfo=timezone.utc)

        with patch.object(
            query_service, "YouTubeChannelXMLLookUp", return_value=["xml_video"]
        ) as mock_xml, patch.object(
            query_service, "GetVideosFromChannelViaAPI"
        ) as mock_api:
            result = query_service.GetVideosFromChannel("UC123", cutoff)
            self.assertEqual(result, ["xml_video"])
            mock_xml.assert_called_once_with("UC123", cutoff)
            mock_api.assert_not_called()

    def test_get_videos_falls_back_to_api_when_xml_fails(self):
        query_service = VideoQuery(api_key="dummy-key")
        cutoff = datetime(2026, 10, 1, tzinfo=timezone.utc)
        http_404 = urllib_error.HTTPError(
            url="https://www.youtube.com/feeds/videos.xml?channel_id=UC123",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        )

        with patch.object(
            query_service, "YouTubeChannelXMLLookUp", side_effect=http_404
        ) as mock_xml, patch.object(
            query_service, "GetVideosFromChannelViaAPI", return_value=["api_video"]
        ) as mock_api:
            result = query_service.GetVideosFromChannel("UC123", cutoff)
            self.assertEqual(result, ["api_video"])
            mock_xml.assert_called_once_with("UC123", cutoff)
            mock_api.assert_called_once_with("UC123", cutoff, currenttPageToken="")

    def test_api_lookup_uses_playlist_items_and_short_circuits_when_no_recent_videos(self):
        query_service = VideoQuery(api_key="dummy-key")
        cutoff = datetime(2026, 10, 15, tzinfo=timezone.utc)

        playlist_response = {
            "items": [
                {
                    "contentDetails": {
                        "videoId": "old_vid",
                        "videoPublishedAt": "2026-10-01T12:00:00Z",
                    }
                }
            ]
        }

        with patch.object(
            query_service, "YouTubeLookUp", return_value=playlist_response
        ) as mock_lookup:
            result = query_service.GetVideosFromChannelViaAPI("UC123", cutoff)
            self.assertEqual(result, [])
            # Should only call "playlistItems" (1 unit) and NOT make a second "videos" API call
            mock_lookup.assert_called_once()
            self.assertEqual(mock_lookup.call_args[0][0], "playlistItems")
            self.assertIn("playlistId=UU123", mock_lookup.call_args[0][1])

    def test_api_lookup_fetches_video_details_for_recent_playlist_items(self):
        query_service = VideoQuery(api_key="dummy-key")
        cutoff = datetime(2026, 10, 15, tzinfo=timezone.utc)

        playlist_response = {
            "items": [
                {
                    "contentDetails": {
                        "videoId": "new_vid",
                        "videoPublishedAt": "2026-10-20T12:00:00Z",
                    }
                },
                {
                    "contentDetails": {
                        "videoId": "old_vid",
                        "videoPublishedAt": "2026-10-01T12:00:00Z",
                    }
                },
            ],
            "nextPageToken": "page2_should_not_be_fetched",
        }
        videos_response = {
            "items": [
                {
                    "id": "new_vid",
                    "snippet": {
                        "channelTitle": "Test Channel",
                        "title": "Recent Upload",
                        "description": "Desc",
                        "publishedAt": "2026-10-20T12:00:00Z",
                        "liveBroadcastContent": "none",
                        "thumbnails": {"high": {"url": "https://example.com/t.jpg"}},
                    },
                    "contentDetails": {"duration": "PT8M"},
                }
            ]
        }

        with patch.object(
            query_service,
            "YouTubeLookUp",
            side_effect=[playlist_response, videos_response],
        ) as mock_lookup:
            result = query_service.GetVideosFromChannelViaAPI("UC123", cutoff)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].ID, "new_vid")
            self.assertEqual(mock_lookup.call_count, 2)
            self.assertEqual(mock_lookup.call_args_list[0][0][0], "playlistItems")
            self.assertEqual(mock_lookup.call_args_list[1][0][0], "videos")


if __name__ == "__main__":
    unittest.main()
