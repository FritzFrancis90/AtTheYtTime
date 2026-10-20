import boto3
from botocore.client import Config
from botocore.errorfactory import ClientError


class AWSStorage:

    BUCKET_NAME = ''
    bucketLocation = ''
    s3 = boto3.resource('s3')

    def __init__(self, AWS_Bucket_Name, AWS_Bucket_Location):
        self.BUCKET_NAME = AWS_Bucket_Name
        self.BUCKET_FORMAT = AWS_Bucket_Location
        self.s3 = boto3.resource('s3')
        self.bucketLocation = self.s3.meta.client.get_bucket_location(Bucket=self.BUCKET_NAME)

    def GetFilesFromBucket(self, filename):
        response = self.s3.meta.client.list_objects(
            Bucket=self.BUCKET_NAME,
            #Delimiter='string',
            #EncodingType='url',
            #Marker='string',
            Prefix=filename
            #RequestPayer='requester'
            #ExpectedBucketOwner='string'
        )
        return response['Contents']

    def GetProposedNewFileLocation(self, filepath, designatedFileName = None):
        return self.BUCKET_FORMAT.format(self.bucketLocation['LocationConstraint'], self.BUCKET_NAME, designatedFileName)

    def UploadFile(self, filepath, designatedFileName = None):
        try:
            self.s3.meta.client.upload_file(filepath, self.BUCKET_NAME, designatedFileName, ExtraArgs={'ACL':'public-read'}) #upload document
            objectURL = self.BUCKET_FORMAT.format(self.bucketLocation['LocationConstraint'], self.BUCKET_NAME, designatedFileName)
            return objectURL
        except ClientError as e:
            print(e)
        print("Done")


    def DownloadFile(self, filename, designatedFileName = None):
        try:
            #self.s3.Object(self.BUCKET_NAME).download_file(filename, designatedFileName) #download
            self.s3.meta.client.download_file(self.BUCKET_NAME, filename, designatedFileName) #download document
        except ClientError as e:
            print(e)
        print("Done")

    def FileExists(self, filename):
        try:
            self.s3.meta.client.head_object(Bucket=self.BUCKET_NAME, Key=filename)
            return True
        except ClientError:
            # Not found
            return False

    def DeleteFile(self, filename):
        #self.s3.Object(self.BUCKET_NAME, filename).delete()
        self.s3.meta.client.delete_object(Bucket=self.BUCKET_NAME, Key=filename)
        return True

    #print(AWSStorage().GetFilesFromBucket('ind'))