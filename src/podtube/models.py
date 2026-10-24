"""Domain models (Channel, Video, etc.) for PodTube."""

import os
from urllib import request
import isodate
import yt_dlp as youtube_dl
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC
from podtube.services.artwork import ImageEditor


class Channel:
    def __init__(self, data: dict):
        self.ID = data["Youtube Channel ID"].strip()
        self.Name = data["Youtube Channel Name"].strip()
        self.excludePhrases = data["Key Words To Exclude"].split(",")
        self.includePhrases = data["Key Words To Include"].split(",")
        self.maxLength = 0
        if int(data["Minute Limit Per Video"].strip() or 0) > 0:
            self.maxLength = int(data["Minute Limit Per Video"]) * 60
        self.isActive = 0 if data["Active"] == "N" else 1
        self.videoList = []

    def FilterVideosByLength(self, video) -> bool:
        if video.duration > self.maxLength and self.maxLength > 0:
            return False
        return True

    def FilterVideosByIncludedTitle(self, video) -> bool:
        if len(self.includePhrases) == 1 and self.includePhrases[0] == "":
            return True
        for phrase in self.includePhrases:
            if phrase in video.Title:
                return True
        return False

    def FilterVideosByExcludedTitle(self, video) -> bool:
        if len(self.excludePhrases) == 1 and self.excludePhrases[0] == "":
            return True
        for phrase in self.excludePhrases:
            if phrase in video.Title:
                return False
        return True

    def ApplyFilters(self):
        self.videoList = list(filter(lambda x: self.FilterVideosByLength(x), self.videoList))
        self.videoList = list(filter(lambda x: self.FilterVideosByIncludedTitle(x), self.videoList))
        self.videoList = list(filter(lambda x: self.FilterVideosByExcludedTitle(x), self.videoList))
        self.videoList = list(filter(lambda x: x.alreadyLoaded == 0, self.videoList))
        self.videoList = list(filter(lambda x: x.isValidDownload == 1, self.videoList))

    def MoveVideosToFolder(self, SaveLocation: str):
        channelFolder = SaveLocation + self.ID
        if not os.path.exists(channelFolder):
            os.makedirs(channelFolder)
        for video in self.videoList:
            if os.path.exists(SaveLocation + video.ID + ".mp3"):
                os.rename(
                    SaveLocation + video.ID + ".mp3",
                    channelFolder + "/" + video.ID + ".mp3",
                )
                video.fileLocation = channelFolder + "/" + video.ID + ".mp3"
            if os.path.exists(SaveLocation + video.ID + "-altered.jpg"):
                os.rename(
                    SaveLocation + video.ID + "-altered.jpg",
                    channelFolder + "/" + video.ID + "-altered.jpg",
                )

    def getDatePublished(self, video):
        return video.datePublished

    def GetMostRecentVideo(self):
        validVideoList = list(filter(lambda x: x.isValidDownload == 1, self.videoList))
        return sorted(validVideoList, key=lambda v: self.getDatePublished(v), reverse=True)[0]

    def GetListOfAllVideos(self, SaveLocation: str):
        channelFolder = SaveLocation + "/" + self.ID
        return list(filter(lambda x: x.endswith(".mp3"), os.listdir(channelFolder)))


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

    def DownloadVideoAsAudio(self, folderPath: str, channelID: str) -> bool:
        if os.path.exists(folderPath + "/" + channelID + "/" + self.ID + ".mp3"):
            self.fileLocation = folderPath + "/" + channelID + "/" + self.ID + ".mp3"
            return True
        ydl_opts = {
            "restrictfilenames": True,
            "simulate": False,
            "format": "bestaudio/best",
            "geo_bypass": True,
            "prefer_ffmpeg": True,
            "outtmpl": folderPath + self.ID + ".%(ext)s",
            "ffmpeg_location": "/usr/local/Cellar/ffmpeg/7.1.1_2/bin/ffmpeg",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "128",
                },
                {"key": "FFmpegMetadata"},
            ],
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            print(self.ID + " - " + self.Title)
            try:
                ydl.download(["https://www.youtube.com/watch?v=" + self.ID])
            except Exception:
                return False
            metatag = EasyID3(folderPath + self.ID + ".mp3")
            metatag["title"] = self.Title
            metatag["artist"] = self.Creator
            metatag["album"] = "The YouTube Playlist"
            EasyID3.RegisterTextKey("comment", "COMM")
            metatag["comment"] = ""
            metatag["composer"] = self.Creator
            metatag.save()
            self.fileLocation = folderPath + self.ID + ".mp3"

            request.urlretrieve(self.formattedArtwork, folderPath + self.ID + ".jpg")
            artwork = ImageEditor(folderPath + self.ID + ".jpg")
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
