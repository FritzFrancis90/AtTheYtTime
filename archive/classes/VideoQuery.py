import os
import json
from classes.Video import Video
from urllib import request, parse
import xml.etree.ElementTree as ET
from datetime import datetime


APIKey = ""
api_service_name = ""
api_version = ""

class VideoQuery:
    def __init__(self, APIKey):
        self.api_service_name = "youtube"
        self.api_version = "v3"
        self.APIKey = APIKey

    def YouTubeLookUp(self, command, params):
        query = ("https://www.googleapis.com/{app}/{version}/{command}?{params}").format(app=self.api_service_name, version=self.api_version, command=command, params=params) + "&key={0}".format(self.APIKey)
        #print(query)
        response = request.urlopen(query)
        data = json.load(response)
        return data
    
    def GetVideosFromChannel(self, channelIDString, LastRunTimeStamp, currenttPageToken = ""):
        channelSearchParams = parse.urlencode({'channelId': channelIDString, 'publishedAfter': LastRunTimeStamp, 'maxResults': 50, 'type': 'video', "pageToken": currenttPageToken})
        channelSearchresponse = self.YouTubeLookUp("search", channelSearchParams)
        videoIDs = list(map(lambda x: x["id"]["videoId"], channelSearchresponse["items"]))
        videoSearchParams = parse.urlencode({'part': 'contentDetails,snippet', 'id': ','.join(videoIDs)})
        videoSearchResponse = self.YouTubeLookUp("videos", videoSearchParams)
        videoInfo = list(map(lambda x: Video(x), videoSearchResponse["items"]))
        if 'nextPageToken' in channelSearchresponse.keys():
        #if (channelSearchresponse["nextPageToken"] != ""):
            videoInfo.extend(self.GetVideosFromChannel(channelIDString, LastRunTimeStamp, currenttPageToken=channelSearchresponse["nextPageToken"]))
        return videoInfo

