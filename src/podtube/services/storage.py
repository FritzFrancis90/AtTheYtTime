"""Cloud storage service (AWS S3) for podcast audio, artwork, and RSS XML files."""

import logging
import os
import boto3
from botocore.errorfactory import ClientError

logger = logging.getLogger(__name__)


class AWSStorage:
    def __init__(self, AWS_Bucket_Name: str, AWS_Bucket_Location: str):
        self.BUCKET_NAME = AWS_Bucket_Name
        self.BUCKET_FORMAT = AWS_Bucket_Location
        self.s3 = boto3.resource("s3")
        self.bucketLocation = self.s3.meta.client.get_bucket_location(
            Bucket=self.BUCKET_NAME
        )

    def GetFilesFromBucket(self, filename: str):
        response = self.s3.meta.client.list_objects(
            Bucket=self.BUCKET_NAME,
            Prefix=filename,
        )
        return response.get("Contents", [])

    def GetProposedNewFileLocation(self, filepath: str, designatedFileName: str = None):
        return self.BUCKET_FORMAT.format(
            self.bucketLocation["LocationConstraint"],
            self.BUCKET_NAME,
            designatedFileName,
        )

    def UploadFile(self, filepath: str, designatedFileName: str = None):
        target_name = designatedFileName or os.path.basename(filepath)
        try:
            self.s3.meta.client.upload_file(
                filepath,
                self.BUCKET_NAME,
                designatedFileName,
                ExtraArgs={"ACL": "public-read"},
            )
            objectURL = self.BUCKET_FORMAT.format(
                self.bucketLocation["LocationConstraint"],
                self.BUCKET_NAME,
                designatedFileName,
            )
            logger.debug("Uploaded %s", target_name)
            return objectURL
        except ClientError as e:
            logger.error("S3 upload failed for %s: %s", target_name, e)
            return None

    def DownloadFile(self, filename: str, designatedFileName: str = None):
        try:
            self.s3.meta.client.download_file(
                self.BUCKET_NAME, filename, designatedFileName
            )
            logger.debug("Downloaded %s", filename)
        except ClientError as e:
            logger.error("S3 download failed for %s: %s", filename, e)

    def FileExists(self, filename: str) -> bool:
        try:
            self.s3.meta.client.head_object(Bucket=self.BUCKET_NAME, Key=filename)
            return True
        except ClientError:
            return False

    def DeleteFile(self, filename: str) -> bool:
        self.s3.meta.client.delete_object(Bucket=self.BUCKET_NAME, Key=filename)
        logger.debug("Deleted %s", filename)
        return True
