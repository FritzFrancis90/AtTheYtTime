"""Domain models (Channel, Video, etc.) for PodTube."""

import logging
from pathlib import Path
from typing import Optional, Union
from urllib import request
import isodate
import yt_dlp as youtube_dl
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC
from podtube.config import resolve_ffmpeg_location
from podtube.logging_config import YtDlpLogger
from podtube.services.artwork import ImageEditor

logger = logging.getLogger(__name__)


class Channel:
    def __init__(self, data: dict):
        if "channel_id" in data:
            self.ID = str(data["channel_id"]).strip()
            self.Name = str(data.get("channel_name", "")).strip()
            raw_exclude = data.get("exclude_keywords", "")
            raw_include = data.get("include_keywords", "")
            self.excludePhrases = (
                [str(x) for x in raw_exclude]
                if isinstance(raw_exclude, list)
                else str(raw_exclude or "").split(",")
            )
            self.includePhrases = (
                [str(x) for x in raw_include]
                if isinstance(raw_include, list)
                else str(raw_include or "").split(",")
            )
            raw_limit = int(data.get("minute_limit") or 0)
            self.maxLength = raw_limit * 60 if raw_limit > 0 else 0
            raw_active = data.get("active", True)
            if isinstance(raw_active, str):
                self.isActive = 0 if raw_active.strip().upper() in ("N", "FALSE", "0") else 1
            else:
                self.isActive = 1 if bool(raw_active) else 0
        else:
            self.ID = data["Youtube Channel ID"].strip()
            self.Name = data["Youtube Channel Name"].strip()
            self.excludePhrases = data["Key Words To Exclude"].split(",")
            self.includePhrases = data["Key Words To Include"].split(",")
            self.maxLength = 0
            if int(data["Minute Limit Per Video"].strip() or 0) > 0:
                self.maxLength = int(data["Minute Limit Per Video"]) * 60
            self.isActive = 0 if data["Active"] == "N" else 1
        self.videoList = []

    def to_dynamodb_item(self) -> dict:
        """Convert this Channel into a DynamoDB item dictionary."""
        return {
            "channel_id": self.ID,
            "channel_name": self.Name,
            "active": bool(self.isActive == 1),
            "minute_limit": int(self.maxLength // 60) if self.maxLength > 0 else 0,
            "include_keywords": ",".join(p for p in self.includePhrases if p),
            "exclude_keywords": ",".join(p for p in self.excludePhrases if p),
        }

    def FilterVideosByLength(self, video) -> bool:
        if video.duration > self.maxLength and self.maxLength > 0:
            logger.debug(
                "Skipping [%s] %s: duration (%ss) exceeds limit (%ss)",
                video.ID,
                video.Title,
                video.duration,
                self.maxLength,
            )
            return False
        return True

    def FilterVideosByIncludedTitle(self, video) -> bool:
        if len(self.includePhrases) == 1 and self.includePhrases[0] == "":
            return True
        for phrase in self.includePhrases:
            if phrase in video.Title:
                return True
        logger.debug(
            "Skipping [%s] %s: title does not match included keywords %s",
            video.ID,
            video.Title,
            self.includePhrases,
        )
        return False

    def FilterVideosByExcludedTitle(self, video) -> bool:
        if len(self.excludePhrases) == 1 and self.excludePhrases[0] == "":
            return True
        for phrase in self.excludePhrases:
            if phrase in video.Title:
                logger.debug(
                    "Skipping [%s] %s: title matched excluded keyword '%s'",
                    video.ID,
                    video.Title,
                    phrase,
                )
                return False
        return True

    def ApplyFilters(self):
        self.videoList = list(filter(lambda x: self.FilterVideosByLength(x), self.videoList))
        self.videoList = list(filter(lambda x: self.FilterVideosByIncludedTitle(x), self.videoList))
        self.videoList = list(filter(lambda x: self.FilterVideosByExcludedTitle(x), self.videoList))
        for v in self.videoList:
            if v.alreadyLoaded != 0:
                logger.debug("Skipping [%s] %s: already exists on S3", v.ID, v.Title)
            elif v.isValidDownload != 1:
                logger.debug("Skipping [%s] %s: marked invalid/live broadcast", v.ID, v.Title)
        self.videoList = list(filter(lambda x: x.alreadyLoaded == 0, self.videoList))
        self.videoList = list(filter(lambda x: x.isValidDownload == 1, self.videoList))

    def MoveVideosToFolder(self, SaveLocation: Union[str, Path]):
        base_dir = Path(SaveLocation)
        channel_folder = base_dir / self.ID
        channel_folder.mkdir(parents=True, exist_ok=True)
        for video in self.videoList:
            src_mp3 = base_dir / f"{video.ID}.mp3"
            dst_mp3 = channel_folder / f"{video.ID}.mp3"
            if src_mp3.exists():
                src_mp3.rename(dst_mp3)
                video.fileLocation = str(dst_mp3)
            src_art = base_dir / f"{video.ID}-altered.jpg"
            dst_art = channel_folder / f"{video.ID}-altered.jpg"
            if src_art.exists():
                src_art.rename(dst_art)

    def getDatePublished(self, video):
        return video.datePublished

    def GetMostRecentVideo(self):
        validVideoList = list(filter(lambda x: x.isValidDownload == 1, self.videoList))
        return sorted(validVideoList, key=lambda v: self.getDatePublished(v), reverse=True)[0]

    def GetListOfAllVideos(self, SaveLocation: Union[str, Path]):
        channel_folder = Path(SaveLocation) / self.ID
        return [p.name for p in channel_folder.iterdir() if p.suffix == ".mp3"]


class Video:
    """Video model supporting both YouTube XML feed entries and YouTube Data API v3 items."""

    def __init__(self, item, ns: dict = None):
        self.artwork = ""
        self.captions = ""
        self.fileLocation = ""
        self.alreadyLoaded = 0
        self.isValidDownload = 1

        if ns is not None:
            # Initialized from XML feed entry (XMLVideo)
            self.ID = item.find("yt:videoId", ns).text
            self.Creator = item.find("atom:author", ns).find("atom:name", ns).text
            self.Title = item.find("atom:title", ns).text
            self.description = (
                item.find("media:group", ns).find("media:description", ns).text
                or "no description"
            )
            self.datePublished = item.find("atom:published", ns).text
            self.duration = 999
            self.thumbnailURL = (
                item.find("media:group", ns).find("media:thumbnail", ns).attrib["url"]
            )
            self.formattedArtwork = self.thumbnailURL
        else:
            # Initialized from YouTube Data API v3 dict (Video)
            self.ID = item["id"]
            self.Creator = item["snippet"]["channelTitle"]
            self.Title = item["snippet"]["title"]
            self.description = item["snippet"]["description"]
            self.datePublished = item["snippet"]["publishedAt"]
            if item["snippet"]["liveBroadcastContent"] == "none":
                self.duration = isodate.parse_duration(
                    item["contentDetails"]["duration"]
                ).total_seconds()
            else:
                self.isValidDownload = 0
                self.duration = 0
            if "maxres" in item["snippet"]["thumbnails"].keys():
                self.thumbnailURL = item["snippet"]["thumbnails"]["maxres"]["url"]
                self.formattedArtwork = item["snippet"]["thumbnails"]["maxres"]["url"]
            else:
                self.thumbnailURL = item["snippet"]["thumbnails"]["high"]["url"]
                self.formattedArtwork = item["snippet"]["thumbnails"]["high"]["url"]

    def DownloadVideoAsAudio(
        self,
        folderPath: Union[str, Path],
        channelID: str,
        ffmpeg_location: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ) -> bool:
        base_dir = Path(folderPath)
        existing_path = base_dir / channelID / f"{self.ID}.mp3"
        if existing_path.exists():
            logger.debug("Audio already downloaded locally: %s/%s.mp3", channelID, self.ID)
            self.fileLocation = str(existing_path)
            return True

        resolved_ffmpeg = ffmpeg_location or resolve_ffmpeg_location()
        ydl_opts = {
            "restrictfilenames": True,
            "simulate": False,
            "format": "bestaudio/best",
            "geo_bypass": True,
            "prefer_ffmpeg": True,
            "outtmpl": str(base_dir / f"{self.ID}.%(ext)s"),
            "logger": YtDlpLogger(logger),
            "noprogress": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "128",
                },
                {"key": "FFmpegMetadata"},
            ],
        }
        if resolved_ffmpeg:
            ydl_opts["ffmpeg_location"] = resolved_ffmpeg
        if proxy_url:
            ydl_opts["proxy"] = proxy_url

        mp3_path = base_dir / f"{self.ID}.mp3"
        jpg_path = base_dir / f"{self.ID}.jpg"

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            logger.info("Downloading audio: [%s] %s", self.ID, self.Title)
            try:
                ydl.download(["https://www.youtube.com/watch?v=" + self.ID])
            except Exception as exc:
                logger.error("Failed to download [%s] %s: %s", self.ID, self.Title, exc)
                return False
            metatag = EasyID3(str(mp3_path))
            metatag["title"] = self.Title
            metatag["artist"] = self.Creator
            metatag["album"] = "The YouTube Playlist"
            EasyID3.RegisterTextKey("comment", "COMM")
            metatag["comment"] = ""
            metatag["composer"] = self.Creator
            metatag.save()
            self.fileLocation = str(mp3_path)

            request.urlretrieve(self.formattedArtwork, str(jpg_path))
            artwork = ImageEditor(str(jpg_path))
            artwork = artwork.CropToCenter()
            artwork.ScaleImage(2)
            self.formattedArtwork = artwork.SaveImage()

            with open(self.formattedArtwork, "rb") as albumart:
                audio = ID3(self.fileLocation)
                audio["APIC"] = APIC(
                    encoding=3,
                    mime="image/jpeg",
                    type=3,
                    desc="Cover",
                    data=albumart.read(),
                )
            audio.save()
            return True