"""Alert and notification service implementations."""

import logging
from typing import Optional
import boto3

logger = logging.getLogger(__name__)


class SNSNotificationProvider:
    """Amazon SNS implementation of NotificationProvider."""

    def __init__(self, topic_arn: str, region_name: Optional[str] = None):
        self.topic_arn = topic_arn
        self.region_name = region_name

    def send_alert(self, subject: str, message: str) -> None:
        sns_client = (
            boto3.client("sns", region_name=self.region_name)
            if self.region_name
            else boto3.client("sns")
        )
        try:
            sns_client.publish(
                TopicArn=self.topic_arn,
                Subject=subject[:100],
                Message=message,
            )
            logger.info("Sent failure alert to SNS topic")
        except Exception as exc:
            logger.error("Failed to publish alert to SNS: %s", exc)

