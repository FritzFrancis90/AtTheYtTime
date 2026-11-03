"""Core pipeline orchestration for syncing channels and updating feeds."""

from dataclasses import dataclass
from datetime import datetime
import logging
import os
from typing import Optional
from urllib import error as urllib_error
from podtube.config import AppConfig
from podtube.models import Channel
from podtube.services.artwork import create_podcast_image
from podtube.services.feed import PodcastFeed, add_old_episodes_to_new_feed
from podtube.services.storage import AWSStorage
from podtube.services.youtube import VideoQuery, get_channels

logger = logging.getLogger(__name__)


class VideoDownloadException(Exception):
    pass


@dataclass
class SyncStats:
    channels_checked: int = 0
    channels_with_new_videos: int = 0
    episodes_downloaded: int = 0
    feeds_updated: int = 0
    failed_downloads: int = 0
    channel_errors: int = 0


def assign_already_loaded(channel: Channel, server: AWSStorage):
    for video in channel.videoList:
        if server.FileExists(channel.ID + "/" + video.ID + ".mp3") is True:
            video.alreadyLoaded = 1


def upload_feed_to_aws(podcast_feed_file: str, save_location: str, server: AWSStorage):
    if server.FileExists(podcast_feed_file):
        server.DeleteFile(podcast_feed_file)
    server.UploadFile(save_location + podcast_feed_file, podcast_feed_file)


def run_sync(
    config: AppConfig,
    channel_filter: Optional[str] = None,
    dry_run: bool = False,
) -> SyncStats:
    """Execute the channel sync and podcast feed generation workflow."""
    stats = SyncStats()
    downloader = VideoQuery(api_key=config.api_key or "APIKey")
    server = AWSStorage(config.aws_bucket_name, config.aws_bucket_location)

    all_channels = get_channels(config.spreadsheet_url)
    channel_list = [ch for ch in all_channels if ch.isActive == 1]

    if channel_filter:
        query_lower = channel_filter.lower()
        channel_list = [
            ch
            for ch in channel_list
            if query_lower in ch.ID.lower() or query_lower in ch.Name.lower()
        ]

    logger.info(
        "Starting %ssync for %d active channel(s) (cutoff: %s)",
        "dry-run " if dry_run else "",
        len(channel_list),
        config.last_run_timestamp.isoformat(),
    )

    for channel in channel_list:
        stats.channels_checked += 1
        try:
            logger.debug("Checking %s (%s)...", channel.Name, channel.ID)
            channel.videoList = downloader.GetVideosFromChannel(
                channel.ID, config.last_run_timestamp
            )
            raw_count = len(channel.videoList)
            assign_already_loaded(channel, server)
            channel.ApplyFilters()

            if len(channel.videoList) == 0:
                logger.debug(
                    "%s (%s): %d video(s) since cutoff, 0 new after filters.",
                    channel.Name,
                    channel.ID,
                    raw_count,
                )
                continue

            stats.channels_with_new_videos += 1
            logger.info(
                "%s (%s): %d new video(s) to process",
                channel.Name,
                channel.ID,
                len(channel.videoList),
            )
            if dry_run:
                for v in channel.videoList:
                    logger.info(
                        "  [dry-run] Would process: [%s] %s (published %s)",
                        v.ID,
                        v.Title,
                        v.datePublished,
                    )
                continue

            XMLFileName = channel.ID + "/" + channel.ID + ".xml"
            NewFeed = PodcastFeed(channel.Name, save_location=config.save_location)
            for newVideo in channel.videoList:
                newVideoResult = newVideo.DownloadVideoAsAudio(
                    config.save_location, channel.ID
                )
                if newVideoResult is False:
                    newVideo.isValidDownload = 0
                    stats.failed_downloads += 1
                else:
                    stats.episodes_downloaded += 1

            channel.MoveVideosToFolder(config.save_location)
            for video in channel.videoList:
                if video.isValidDownload == 1:
                    DefaultVideoDescription = (
                        "Video: https://www.youtube.com/watch?v=" + video.ID + " \n\n"
                    )
                    AudioURL = server.GetProposedNewFileLocation(
                        video.fileLocation,
                        designatedFileName=channel.ID + "/" + video.ID + ".mp3",
                    )
                    NewFeed.AddEpisode(
                        AudioURL,
                        datetime.strptime(
                            video.datePublished, "%Y-%m-%dT%H:%M:%S%z"
                        ),
                        video.Title,
                        DefaultVideoDescription + video.description,
                        video.fileLocation,
                    )
                    AudioURL = server.UploadFile(
                        video.fileLocation,
                        designatedFileName=channel.ID + "/" + video.ID + ".mp3",
                    )

            if len([x for x in channel.videoList if x.isValidDownload == 1]) > 0:
                MostRecentVideo = channel.GetMostRecentVideo()
                podcastImage = create_podcast_image(
                    MostRecentVideo, font_path=config.included_font
                )
                now = str(datetime.now())
                now = "".join(ch for ch in now if ch.isdigit())
                designatedFilepath = (
                    channel.ID + "/" + channel.ID + "-" + now + ".jpg"
                )
                if server.FileExists(designatedFilepath):
                    server.DeleteFile(designatedFilepath)
                ImageURL = server.UploadFile(
                    podcastImage, designatedFileName=designatedFilepath
                )
                NewFeed.SetFeedImage(ImageURL)
                if server.FileExists(XMLFileName) is True:
                    OldFeedXML = "OLD-" + channel.ID + ".xml"
                    server.DownloadFile(XMLFileName, OldFeedXML)
                    add_old_episodes_to_new_feed(OldFeedXML, NewFeed)
                    os.remove(OldFeedXML)
                NewFeedFile = NewFeed.ExportFeed(
                    channel.ID, save_location=config.save_location
                )
                upload_feed_to_aws(NewFeedFile, config.save_location, server)
                stats.feeds_updated += 1
                logger.info("Updated podcast feed for %s (%s)", channel.Name, NewFeedFile)
        except urllib_error.HTTPError as exc:
            stats.channel_errors += 1
            logger.error(
                "Failed to fetch feed for %s (%s): %s",
                channel.Name,
                channel.ID,
                exc,
            )
        except VideoDownloadException:
            stats.channel_errors += 1

    return stats

    return stats

