"""YouTube feed and API query service (XML feed & Data API v3) and channel CSV loader."""

import csv
import json
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib import error, request, parse
from podtube.models import Channel, Video

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "application/atom+xml,application/xml,text/xml;q=0.9,*/*;q=0.8",
}


def get_uploads_playlist_id(channel_id: str) -> str:
    """Convert a YouTube channel ID (UC...) into its uploads playlist ID (UU...)."""
    cleaned = channel_id.strip()
    if cleaned.startswith("UC"):
        return "UU" + cleaned[2:]
    return cleaned


def convert_csv_to_object(url: str) -> list[dict]:
    logger.debug("Fetching channel list CSV from spreadsheet...")
    data = []
    with request.urlopen(url) as f:
        channelList = [line.decode("utf-8") for line in f.readlines()]
        cr = csv.reader(channelList)
        crRowCounter = 1
        for row in cr:
            if crRowCounter == 1:
                headers = row
                crRowCounter += 1
                continue
            info = {}
            for cell in range(len(row)):
                key = headers[cell]
                info[key] = row[cell]
            data.append(info)
            crRowCounter += 1
    return data


def get_channels(spreadsheet_url: str) -> list[Channel]:
    channel_rows = convert_csv_to_object(spreadsheet_url)
    return [Channel(row) for row in channel_rows]


class VideoQuery:
    """Queries YouTube channel videos via public Atom XML feed or YouTube Data API v3."""

    def __init__(self, api_key: str = "APIKey"):
        self.api_service_name = "youtube"
        self.api_version = "v3"
        self.APIKey = api_key

    def YouTubeLookUp(self, command: str, params: str) -> dict:
        query = (
            f"https://www.googleapis.com/{self.api_service_name}/{self.api_version}/{command}?{params}"
            f"&key={self.APIKey}"
        )
        logger.debug("YouTube Data API v3 request: %s?%s", command, params)
        response = request.urlopen(query)
        return json.load(response)

    def YouTubeChannelXMLLookUp(
        self,
        channelIDString: str,
        LastRunTimeStamp: datetime,
        max_retries: int = 3,
    ) -> list[Video]:
        videoList = []
        channel_id = channelIDString.strip()
        query = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        req = request.Request(query, headers=DEFAULT_HEADERS)

        raw_xml = None
        for attempt in range(1, max_retries + 1):
            try:
                logger.debug(
                    "Fetching RSS XML feed for %s (attempt %d/%d)",
                    channel_id,
                    attempt,
                    max_retries,
                )
                with request.urlopen(req, timeout=15) as response:
                    raw_xml = response.read()
                break
            except error.HTTPError as exc:
                if attempt < max_retries:
                    delay = 1.5 * attempt
                    logger.debug(
                        "RSS feed returned %s for %s; retrying in %.1fs...",
                        exc,
                        channel_id,
                        delay,
                    )
                    time.sleep(delay)
                else:
                    raise exc

        time.sleep(0.5)
        root = ET.fromstring(raw_xml)
        tree = ET.ElementTree(root)
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "yt": "http://www.youtube.com/xml/schemas/2015",
            "media": "http://search.yahoo.com/mrss/",
        }
        for child in tree.findall("atom:entry", ns):
            publishDateText = child.find("atom:published", ns).text
            publishDate = datetime.fromisoformat(publishDateText)
            if publishDate >= LastRunTimeStamp:
                videoList.append(Video(child, ns))
        return videoList

    def GetVideosFromChannel(
        self,
        channelIDString: str,
        LastRunTimeStamp: datetime,
        currenttPageToken: str = "",
    ) -> list[Video]:
        try:
            return self.YouTubeChannelXMLLookUp(channelIDString, LastRunTimeStamp)
        except Exception as exc:
            logger.warning(
                "RSS feed failed for %s (%s); falling back to YouTube Data API once...",
                channelIDString,
                exc,
            )
            return self.GetVideosFromChannelViaAPI(
                channelIDString, LastRunTimeStamp, currenttPageToken=currenttPageToken
            )

    def GetVideosFromChannelViaAPI(
        self,
        channelIDString: str,
        LastRunTimeStamp: datetime,
        currenttPageToken: str = "",
    ) -> list[Video]:
        """Query channel videos via the UU... uploads playlist (1 quota unit vs 100 for search)."""
        cutoff_dt = (
            LastRunTimeStamp
            if isinstance(LastRunTimeStamp, datetime)
            else datetime.fromisoformat(str(LastRunTimeStamp))
        )
        playlist_id = get_uploads_playlist_id(channelIDString)
        playlist_params = parse.urlencode(
            {
                "part": "snippet,contentDetails",
                "playlistId": playlist_id,
                "maxResults": 50,
                "pageToken": currenttPageToken,
            }
        )
        playlist_response = self.YouTubeLookUp("playlistItems", playlist_params)

        videoIDs = []
        reached_older_videos = False
        for item in playlist_response.get("items", []):
            content_details = item.get("contentDetails", {})
            snippet = item.get("snippet", {})
            video_id = content_details.get("videoId") or snippet.get(
                "resourceId", {}
            ).get("videoId")
            published_str = content_details.get("videoPublishedAt") or snippet.get(
                "publishedAt"
            )
            if not video_id or not published_str:
                continue
            published_dt = datetime.fromisoformat(published_str)
            if published_dt >= cutoff_dt:
                videoIDs.append(video_id)
            else:
                reached_older_videos = True

        if not videoIDs:
            return []

        videoSearchParams = parse.urlencode(
            {"part": "contentDetails,snippet", "id": ",".join(videoIDs)}
        )
        videoSearchResponse = self.YouTubeLookUp("videos", videoSearchParams)
        videoInfo = [Video(x) for x in videoSearchResponse.get("items", [])]

        if "nextPageToken" in playlist_response and not reached_older_videos:
            videoInfo.extend(
                self.GetVideosFromChannelViaAPI(
                    channelIDString,
                    cutoff_dt,
                    currenttPageToken=playlist_response["nextPageToken"],
                )
            )
        return videoInfo
