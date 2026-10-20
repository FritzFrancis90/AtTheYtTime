#!/usr/bin/env python
import yaml
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
'''
setup(
    name='PodTube',
    version='0.0.1',
    description='Converting YouTube videos to Podcasts for Less Distractions',
    packages=['PodTube',],
    license='N/A',
    #long_description=open('README.txt').read()
)
'''

def ConfigureLocation():
    if sys.platform.startswith('linux'):
        SaveLocation = config["SaveLocation"]["LinuxLocation"]
    if sys.platform.startswith('darwin'):
        SaveLocation = config["SaveLocation"]["MacOSLocation"]
    if sys.platform.startswith('win32'):
        SaveLocation = config["SaveLocation"]["WindowsLocation"]
    return SaveLocation

script_dir = Path(__file__).parent
config_file_location = script_dir / "config.yaml"
config = yaml.safe_load(open(config_file_location, "r"))
daysBack = config["defaultDaysToLookBack"]
includedFont = config["IncludedFont"]
SaveLocation = ConfigureLocation()
SpreadsheetURL = config["SpreadsheetURL"]
LastRunTimeStamp = max(datetime.strptime(config["previousRun"], '%Y-%m-%dT%H:%M:%S%z'), datetime.now(timezone.utc) - timedelta(days=daysBack)) #or datetime.today() - timedelta(days=daysBack)
AWS_Bucket_Name = config["AWS_Bucket_Name"]
AWS_Bucket_Location = config["AWS_Bucket_Location"]

#yaml
#youtube_dl
#dateutil
#mutagen
#Pillow
#urllib
#isodate
#podgen
#boto3

'''
- Make Multithreaded
- Add Captions
- Create Podcast Feed
'''