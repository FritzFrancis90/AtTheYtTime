"""Core pipeline orchestration for syncing channels and updating feeds."""

import os
from datetime import datetime
from typing import Optional
from urllib import error as urllib_error
from podtube.config import AppConfig
from podtube.models import Channel
from podtube.services.artwork import create_podcast_image
from podtube.services.feed import PodcastFeed, add_old_episodes_to_new_feed
from podtube.services.storage import AWSStorage
from podtube.services.youtube import VideoQuery, get_channels


class VideoDownloadException(Exception):
    pass


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
):
    """Execute the channel sync and podcast feed generation workflow."""
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

    for channel in channel_list:
        try:
            if dry_run:
                print(
                    f"Checking {channel.Name} ({channel.ID}) since {config.last_run_timestamp.isoformat()}..."
                )
            channel.videoList = downloader.GetVideosFromChannel(
                channel.ID, config.last_run_timestamp
            )
            raw_count = len(channel.videoList)
            assign_already_loaded(channel, server)
            channel.ApplyFilters()
            if dry_run and len(channel.videoList) == 0:
                print(
                    f"  [dry-run] {raw_count} video(s) found in XML feed since cutoff; 0 remaining after filters/already-uploaded check."
                )
            if len(channel.videoList) > 0:
                print(channel.Name + " - " + str(len(channel.videoList)))
                if dry_run:
                    for v in channel.videoList:
                        print(f"  [dry-run] Would process: {v.ID} - {v.Title} (published {v.datePublished})")
                    continue

                XMLFileName = channel.ID + "/" + channel.ID + ".xml"
                NewFeed = PodcastFeed(channel.Name, save_location=config.save_location)
                for newVideo in channel.videoList:
                    newVideoResult = newVideo.DownloadVideoAsAudio(
                        config.save_location, channel.ID
                    )
                    if newVideoResult is False:
                        newVideo.isValidDownload = 0
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
        except urllib_error.HTTPError as exc:
            print(f"  [error] Failed to fetch feed for {channel.Name} ({channel.ID}): {exc}")
        except VideoDownloadException:
            pass
