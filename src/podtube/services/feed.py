"""Podcast RSS feed creation and episode management."""

from datetime import datetime
import io
from pathlib import Path
from typing import Optional, Union
from urllib.parse import unquote, urlparse
import xml.etree.ElementTree as ET
import podgen


class PodcastFeed:
    hoursToSkip = list(range(6)) + list(range(19, 24))

    def __init__(self, Name: str, save_location: Union[str, Path] = ""):
        self.save_location = Path(save_location) if save_location else Path()
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
            ep.media.populate_duration_from(localFileLocation)
        self.p.add_episode(ep)

    def SetFeedImage(self, URL: str):
        self.p.image = URL

    def ExportFeed(self, channelID: str, save_location: Union[str, Path] = None) -> str:
        base_dir = Path(save_location) if save_location is not None else self.save_location
        relative_feed_path = f"{channelID}/{channelID}.xml"
        full_path = base_dir / channelID / f"{channelID}.xml"
        full_path.parent.mkdir(parents=True, exist_ok=True)
        if full_path.exists():
            full_path.unlink()
        self.p.rss_file(str(full_path), minimize=True)
        return relative_feed_path


def add_old_episodes_to_new_feed(old_feed_path: Union[str, Path], new_feed: PodcastFeed):
    """Parse an existing RSS feed XML and carry over its episodes to the new feed."""
    for item in ET.parse(str(old_feed_path)).getroot()[0].iter("item"):
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


def extract_s3_key_from_url(url: str, bucket_name: str) -> Optional[str]:
    """Extract the object key from an S3 URL (path-style or virtual-hosted-style) for bucket_name."""
    if not url or not bucket_name:
        return None
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    path = parsed.path.lstrip("/")
    bucket_lower = bucket_name.lower()

    if host.startswith(f"{bucket_lower}.s3"):
        return unquote(path) if path else None
    if "amazonaws.com" in host and path.startswith(f"{bucket_name}/"):
        key = path[len(bucket_name) + 1 :]
        return unquote(key) if key else None
    return None


def presign_feed_xml(
    xml_content: str,
    storage,
    bucket_name: str,
    expires_in: int = 604800,
) -> str:
    """Rewrite S3 media and image URLs inside an RSS XML document into presigned URLs."""
    for _, (prefix, uri) in ET.iterparse(
        io.StringIO(xml_content), events=["start-ns"]
    ):
        ET.register_namespace(prefix, uri)

    root = ET.fromstring(xml_content)

    def _presign_if_bucket_url(url: Optional[str]) -> Optional[str]:
        if not url:
            return url
        key = extract_s3_key_from_url(url, bucket_name)
        if not key:
            return url
        return storage.GeneratePresignedUrl(key, expires_in=expires_in)

    for element in root.iter():
        tag_name = element.tag.rsplit("}", 1)[-1]
        if tag_name == "enclosure" and "url" in element.attrib:
            element.attrib["url"] = _presign_if_bucket_url(element.attrib["url"])
        elif tag_name == "image" and "href" in element.attrib:
            element.attrib["href"] = _presign_if_bucket_url(element.attrib["href"])

    return ET.tostring(root, encoding="unicode", xml_declaration=True)