import os
import json
from classes.XMLVideo import Video
from urllib import request, parse
import xml.etree.ElementTree as ET
from datetime import datetime


APIKey = ""
api_service_name = ""
api_version = ""

class VideoQuery:
    def __init__(self):
        self.api_service_name = "youtube"
        self.api_version = "v3"
        self.APIKey = "APIKey"

    def YouTubeLookUp(self, command, params):
        query = ("https://www.googleapis.com/{app}/{version}/{command}?{params}").format(app=self.api_service_name, version=self.api_version, command=command, params=params) + "&key={0}".format(self.APIKey)
        #print(query)
        response = request.urlopen(query)
        data = json.load(response)
        return data

    def YouTubeChannelXMLLookUp(self, channelIDString, LastRunTimeStamp):
        videoList = list()
        query = ("https://youtube.com/feeds/videos.xml?channel_id={channelId}").format(channelId=channelIDString)
        #print(query)
        with request.urlopen(query) as response:
            response = response.read()
        root = ET.fromstring(response)
        tree = ET.ElementTree(root)
        #data = json.load(response)
        ns = {
            'atom': 'http://www.w3.org/2005/Atom',
            'yt': 'http://www.youtube.com/xml/schemas/2015',
            'media': 'http://search.yahoo.com/mrss/'
        }
        for child in tree.findall('atom:entry',ns):
            publishDateText = child.find('atom:published', ns).text
            publishDate = datetime.fromisoformat(publishDateText)
            #2026-10-04T23:58:25+00:00
            if publishDate >= LastRunTimeStamp:
                videoList.append(Video(child, ns))
        return videoList
    '''
    def xml_to_dict(element):
        """Recursively converts an ElementTree element into a dictionary."""
        result = {}
        # Extract attributes
        if element.attrib:
            result.update({f"@{k}": v for k, v in element.attrib.items()})

        # Extract children
        for child in element:
            child_data = self.xml_to_dict(child)
            if child.tag in result:
                # If the tag already exists, turn it into a list
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child_data)
            else:
                result[child.tag] = child_data

        # Extract text if there are no children
        if element.text and element.text.strip():
            if result:
                result["#text"] = element.text.strip()
            else:
                return element.text.strip()

        return result if result else None
    '''
    
    def GetVideosFromChannel(self, channelIDString, LastRunTimeStamp, currenttPageToken = ""):
        channelSearchParams = parse.urlencode({'channelId': channelIDString, 'publishedAfter': LastRunTimeStamp, 'maxResults': 50, 'type': 'video', "pageToken": currenttPageToken})
        #channelSearchresponse = self.YouTubeLookUp("search", channelSearchParams)
        channelSearchresponse = self.YouTubeChannelXMLLookUp(channelIDString, LastRunTimeStamp)
        '''
        videoIDs = list(map(lambda x: x["id"]["videoId"], channelSearchresponse["items"]))
        videoSearchParams = parse.urlencode({'part': 'contentDetails,snippet', 'id': ','.join(videoIDs)})
        videoSearchResponse = self.YouTubeLookUp("videos", videoSearchParams)
        videoInfo = list(map(lambda x: Video(x), videoSearchResponse["items"]))
        if 'nextPageToken' in channelSearchresponse.keys():
        #if (channelSearchresponse["nextPageToken"] != ""):
            videoInfo.extend(self.GetVideosFromChannel(channelIDString, LastRunTimeStamp, currenttPageToken=channelSearchresponse["nextPageToken"]))
        return videoInfo
        '''
        return channelSearchresponse

