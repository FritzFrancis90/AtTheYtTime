import yt_dlp as youtube_dl
import ffmpeg
import isodate
import os
from classes.imageEditor import ImageEditor
from urllib import request
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC
import xml.etree.ElementTree as ET


class Video:
    ID = ""
    Creator = ""
    Title = ""
    description = ""
    datePublished = ""
    duration = 0
    thumbnailURL = ""
    artwork = ""
    formattedArtwork = ""
    captions = ""
    fileLocation = ""
    alreadyLoaded = 0
    isValidDownload = 1
    

    def __init__(self, item, ns):   
        self.ID = item.find('yt:videoId', ns).text
        self.Creator = item.find('atom:author', ns).find('atom:name', ns).text
        self.Title = item.find('atom:title', ns).text
        self.description = item.find('media:group', ns).find('media:description', ns).text or 'no description'
        self.datePublished = item.find('atom:published', ns).text
        self.duration = 999
        self.thumbnailURL = item.find('media:group', ns).find('media:thumbnail', ns).attrib['url']
        self.formattedArtwork = item.find('media:group', ns).find('media:thumbnail', ns).attrib['url']

    def DownloadVideoAsAudio(self, folderPath, channelID):
        if os.path.exists(folderPath + '/' + channelID + '/' + self.ID + '.mp3'):
            self.fileLocation = folderPath + '/' + channelID + '/' + self.ID + '.mp3'
            return True
        ydl_opts = {
            'restrictfilenames': True,
            'simulate': False,
            'format': 'bestaudio/best',
            'geo_bypass': True,
            'prefer_ffmpeg': True,
            'outtmpl': folderPath + self.ID + '.%(ext)s',
            'ffmpeg_location': '/usr/local/Cellar/ffmpeg/7.1.1_2/bin/ffmpeg',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128'
                },{
                'key': 'FFmpegMetadata'
            
            }]
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            print(self.ID + " - " + self.Title)
            try:
                ydl.download(['https://www.youtube.com/watch?v=' + self.ID])
            except:
                return False
            metatag = EasyID3(folderPath + self.ID + '.mp3')
            metatag['title'] = self.Title
            metatag['artist'] = self.Creator
            metatag['album'] = "The YouTube Playlist"
            EasyID3.RegisterTextKey('comment', 'COMM')
            metatag['comment'] = '' #Captions for a later date?
            metatag['composer'] = self.Creator
            metatag.save()
            self.fileLocation = folderPath + self.ID + '.mp3'

            request.urlretrieve(self.formattedArtwork, folderPath + self.ID + ".jpg")
            artwork = ImageEditor(folderPath + self.ID + ".jpg")            
            artwork = artwork.CropToCenter()
            artwork.ScaleImage(2)
            self.formattedArtwork = artwork.SaveImage()

            with open(self.formattedArtwork, 'rb') as albumart:
                audio = ID3(self.fileLocation)
                audio['APIC'] = APIC(
                                encoding=3,
                                mime='image/jpeg',
                                type=3, desc=u'Cover',
                                data=albumart.read()
                                )            
            audio.save()
            return True
