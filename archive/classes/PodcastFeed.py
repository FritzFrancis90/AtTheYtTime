import podgen
import os
import PodTubeSetup
import datetime
from io import BytesIO

class PodcastFeed:
    p = None
    hoursToSkip = list(range(6)).append(list(range(19, 24)))
    channel = None

    def __init__(self, Name):
        self.p = podgen.Podcast(
            name = Name,
            description = "A podcast stream of audio from the Youtube Channel " + Name,
            website = "N/A",
            authors = [podgen.Person(Name, None)],
            #feed_url = PodTubeSetup.SaveLocation + channel.ID + "/podcast.rss"  # URL of this feed    
            skip_hours = self.hoursToSkip, # Set of hours on which podcatchers won't need to refresh the feed.
            category = podgen.Category("Leisure"),
            copyright = "N/A",
            language = "en-US",
            explicit = True                   
        )

    def AddEpisode(self, filelocation, datePublished, Title, Description, localFileLocation=None):
        #datePublished = pytz.timezone('UTC').localize(datetime.datetime.strptime(datePublished, '%Y-%m-%dT%H:%M:%SZ'))
        ep = podgen.Episode(
            title = Title,
            media = podgen.Media(filelocation),
            publication_date = datePublished,
            summary = Description
        )
        if(localFileLocation != None):
            ep.media.duration = ep.media.populate_duration_from(localFileLocation)            
        self.p.add_episode(ep)

    def SetFeedImage(self, URL):
        self.p.image = URL

    def ExportFeed(self, channelID):
        CreatedFilePath = channelID + '/' + channelID + ".xml"
        if os.path.exists(PodTubeSetup.SaveLocation + CreatedFilePath):
            os.remove(PodTubeSetup.SaveLocation + CreatedFilePath)
        #rss = self.p.rss_str()
        self.p.rss_file(PodTubeSetup.SaveLocation + CreatedFilePath, minimize=True)
        return CreatedFilePath