

import yaml
import csv
import threading
import sys
import os
import PodTubeSetup
import xml
import xml.etree.ElementTree as ET
import pytz
from datetime import datetime, timedelta
from classes.channel import channel
from classes.XMLVideoQuery import VideoQuery
from classes.XMLVideo import Video
from classes.PodcastFeed import PodcastFeed
from classes.imageEditor import ImageEditor
from classes.ServerContact import AWSStorage
from urllib import request


def GetChannels():
    newList = []
    url = PodTubeSetup.SpreadsheetURL
    channelObject = ConvertCSVToObject(url)
    for c in channelObject:
        #newcna = channel(c)
        newList.append(channel(c))
    return newList

def ConvertCSVToObject(url):
    data = []
    with request.urlopen(url) as f:
        channelList = [l.decode('utf-8') for l in f.readlines()]
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

def CreateGlobalFeed():
    channelFolder = PodTubeSetup.SaveLocation
    return list(filter(lambda x: x.endswith(".mp3"), os.listdir(channelFolder)))

def CreatePodcastImage(video):
    image = ImageEditor(video.fileLocation.replace('.mp3', '-altered.jpg')).CropToCenter().ScaleImage(2).ApplyGradient(6, 0.6).AddTextToImage('Latest Episode\n "' + video.Title + '"').SaveImage()
    return image

def AddOldEpisodestoNewFeed(oldFeed, NewFeed):
    for item in ET.parse(oldFeed).getroot()[0].iter('item'):
    #for item in ET.parse(oldFeed).iter('item'):
        #NewFeed.AddEpisode(item[3].attrib['url'], datetime.strptime(item[4].text, '%a, %d %b %Y %H:%M:%S %z'), item[0].text, item[1].text)
        itemTitle = item.find('title').text
        itemURL = item.find('enclosure').attrib['url']
        itemPublishedDate = item.find('pubDate').text
        if (item.find('description') is None):
            itemDescription = 'No description'
        else:
            itemDescription = item.find('description').text            
        NewFeed.AddEpisode(itemURL, datetime.strptime(itemPublishedDate, '%a, %d %b %Y %H:%M:%S %z'), itemTitle, itemDescription)

def AssignAlreadyLoaded(channel):
    global server
    for video in channel.videoList:
        if server.FileExists(channel.ID + '/' + video.ID + '.mp3') == True:
            video.alreadyLoaded = 1

def UploadFeedtoAWS(PodcastFeed):
    global server
    if server.FileExists(PodcastFeed):
        server.DeleteFile(PodcastFeed)
    server.UploadFile(PodTubeSetup.SaveLocation + PodcastFeed, PodcastFeed)

class videoDownloadException(Exception): pass

downloader = VideoQuery()
server = AWSStorage(PodTubeSetup.AWS_Bucket_Name, PodTubeSetup.AWS_Bucket_Location)

channelList = list(filter(lambda x: x.isActive == 1, GetChannels()))
for channel in channelList:
    try:
        channel.videoList = downloader.GetVideosFromChannel(channel.ID, PodTubeSetup.LastRunTimeStamp)
        AssignAlreadyLoaded(channel)
        channel.ApplyFilters()
        if len(channel.videoList) > 0:
            print(channel.Name + ' - ' + str(len(channel.videoList)))
            XMLFileName = channel.ID + '/' + channel.ID + '.xml'
            NewFeed = PodcastFeed(channel.Name)
            for newVideo in channel.videoList:
                newVideoResult = newVideo.DownloadVideoAsAudio(PodTubeSetup.SaveLocation, channel.ID)
                if newVideoResult == False:
                    #raise videoDownloadException()
                    newVideo.isValidDownload = 0
            channel.MoveVideosToFolder(PodTubeSetup.SaveLocation)
            for video in channel.videoList:
                if video.isValidDownload == 1:
                    DefaultVideoDescription = "Video: https://www.youtube.com/watch?v=" + video.ID + " \n\n"
                    AudioURL = server.GetProposedNewFileLocation(video.fileLocation, designatedFileName=channel.ID + '/' + video.ID + '.mp3')
                    NewFeed.AddEpisode(AudioURL, datetime.strptime(video.datePublished, '%Y-%m-%dT%H:%M:%S%z'), video.Title, DefaultVideoDescription + video.description, video.fileLocation)
                    AudioURL = server.UploadFile(video.fileLocation, designatedFileName=channel.ID + '/' + video.ID + '.mp3')
            if len(list(filter(lambda x: x.isValidDownload == 1, channel.videoList))) > 0:
                MostRecentVideo = channel.GetMostRecentVideo()
                podcastImage = CreatePodcastImage(MostRecentVideo)
                now = str(datetime.now())
                now = ''.join(ch for ch in now if ch.isdigit())
                designatedFilepath = channel.ID + '/' + channel.ID + '-' + now + '.jpg'
                if server.FileExists(designatedFilepath):
                    server.DeleteFile(designatedFilepath)
                ImageURL = server.UploadFile(podcastImage, designatedFileName=designatedFilepath)
                NewFeed.SetFeedImage(ImageURL)
                if server.FileExists(XMLFileName) == True:
                    OldFeedXML = 'OLD-' + channel.ID + '.xml'
                    server.DownloadFile(XMLFileName, OldFeedXML)
                    AddOldEpisodestoNewFeed(OldFeedXML, NewFeed)
                    os.remove(OldFeedXML)
                NewFeedFile = NewFeed.ExportFeed(channel.ID)
                UploadFeedtoAWS(NewFeedFile)
    except videoDownloadException:
        pass    
    #break

