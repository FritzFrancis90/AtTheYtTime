import os
import datetime

class channel:
    ID = ""
    Name = ""
    excludePhrases = []
    includePhrases = []
    isActive = 1
    maxLength = 0
    videoList = []

    def __init__(self, data):
        self.ID = data['Youtube Channel ID']
        self.Name = data['Youtube Channel Name']
        self.excludePhrases = data['Key Words To Exclude'].split(",")
        self.includePhrases = data['Key Words To Include'].split(",")
        if int(data['Minute Limit Per Video'].strip() or 0) > 0:
            self.maxLength = int(data['Minute Limit Per Video']) * 60
        if data['Active'] == 'N':
            self.isActive = 0

    def FilterVideosByLength(self, video):
        if video.duration > self.maxLength and self.maxLength > 0:
            return False
        return True

    def FilterVideosByIncludedTitle(self, video):
        if len(self.includePhrases) == 1 and self.includePhrases[0] == "":
            return True
        for phrase in self.includePhrases:
            if phrase in video.Title:
                return True
        return False

    def FilterVideosByExcludedTitle(self, video):
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

    def MoveVideosToFolder(self, SaveLocation):
        channelFolder = SaveLocation + self.ID
        if not os.path.exists(channelFolder):
            os.makedirs(channelFolder)
        for video in self.videoList:
            if os.path.exists(SaveLocation + video.ID + '.mp3'):
                os.rename(SaveLocation + video.ID + '.mp3', channelFolder + '/' + video.ID + '.mp3')
                video.fileLocation = channelFolder + '/' + video.ID + '.mp3'
            if os.path.exists(SaveLocation + video.ID + '-altered.jpg'):
                os.rename(SaveLocation + video.ID + '-altered.jpg', channelFolder + '/' + video.ID + '-altered.jpg')
    
    def getDatePublished(self, video):
        return video.datePublished

    def GetMostRecentVideo(self):
        validVideoList = list(filter(lambda x: x.isValidDownload == 1, self.videoList))
        return sorted(validVideoList, key = lambda v: self.getDatePublished(v), reverse = True)[0]

    def GetListOfAllVideos(self, SaveLocation):
        channelFolder = SaveLocation + '/' + self.ID
        return list(filter(lambda x: x.endswith(".mp3"), os.listdir(channelFolder)))