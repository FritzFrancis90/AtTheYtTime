"""Podcast RSS feed creation and episode management."""

import os
import xml.etree.ElementTree as ET
from datetime import datetime
import podgen


class PodcastFeed:
    hoursToSkip = list(range(6)).append(list(range(19, 24)))

    def __init__(self, Name: str, save_location: str = ""):
        self.save_location = save_location
        self.p = podgen.Podcast(
            name=Name,
            description="A podcast stream of audio from the Youtube Channel " + Name,
            website="N/A",
            authors=[podgen.Person(Name, None)],
            skip_hours=self.hoursToSkip,
            category=podgen.Category("Leisure"),
            copyright="N/A",
            language="en-US",
            explicit=True,
        )

    def AddEpisode(
        self,
        filelocation: str,
        datePublished: datetime,
        Title: str,
        Description: str,
        localFileLocation: str = None,
    ):
        ep = podgen.Episode(
            title=Title,
            media=podgen.Media(filelocation),
            publication_date=datePublished,
            summary=Description,
        )
        if localFileLocation is not None:
            ep.media.duration = ep.media.populate_duration_from(localFileLocation)
        self.p.add_episode(ep)

    def SetFeedImage(self, URL: str):
        self.p.image = URL

    def ExportFeed(self, channelID: str, save_location: str = None) -> str:
        base_location = save_location if save_location is not None else self.save_location
        CreatedFilePath = channelID + "/" + channelID + ".xml"
        full_path = base_location + CreatedFilePath
        if os.path.exists(full_path):
            os.remove(full_path)
        self.p.rss_file(full_path, minimize=True)
        return CreatedFilePath


def add_old_episodes_to_new_feed(old_feed_path: str, new_feed: PodcastFeed):
    """Parse an existing RSS feed XML and carry over its episodes to the new feed."""
    for item in ET.parse(old_feed_path).getroot()[0].iter("item"):
        itemTitle = item.find("title").text
        itemURL = item.find("enclosure").attrib["url"]
        itemPublishedDate = item.find("pubDate").text
        if item.find("description") is None:
            itemDescription = "No description"
        else:
            itemDescription = item.find("description").text
        new_feed.AddEpisode(
            itemURL,
            datetime.strptime(itemPublishedDate, "%a, %d %b %Y %H:%M:%S %z"),
            itemTitle,
            itemDescription,
        )
