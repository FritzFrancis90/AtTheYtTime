"""Unit tests for YouTube RSS lookup and Data API v3 fallback."""

from datetime import datetime, timezone
import unittest
from unittest.mock import patch
from urllib import error as urllib_error
from podtube.services.youtube import VideoQuery


class TestYouTubeService(unittest.TestCase):
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

    def test_api_lookup_short_circuits_when_search_returns_no_videos(self):
        query_service = VideoQuery(api_key="dummy-key")
        cutoff = datetime(2026, 10, 1, tzinfo=timezone.utc)

        with patch.object(
            query_service, "YouTubeLookUp", return_value={"items": []}
        ) as mock_lookup:
            result = query_service.GetVideosFromChannelViaAPI("UC123", cutoff)
            self.assertEqual(result, [])
            # Should only call "search" once and NOT make a second "videos" API call
            mock_lookup.assert_called_once()
            self.assertEqual(mock_lookup.call_args[0][0], "search")


if __name__ == "__main__":
    unittest.main()

