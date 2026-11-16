"""Factory functions for instantiating cloud storage, channel repository, and notification providers."""

from typing import Optional
from podtube.config import AppConfig
from podtube.services.channel_store import (
    DynamoDBChannelStore,
    GoogleSheetChannelRepository,
)
from podtube.services.interfaces import (
    ChannelRepository,
    NotificationProvider,
    StorageProvider,
)
from podtube.services.notifications import SNSNotificationProvider
from podtube.services.storage import AWSStorage


def create_storage_provider(config: AppConfig) -> StorageProvider:
    """Instantiate the configured cloud StorageProvider."""
    provider = (config.cloud_provider or "aws").lower()
    if provider == "aws":
        return AWSStorage(config.aws_bucket_name, config.aws_bucket_location)
    raise ValueError(f"Unsupported cloud_provider for storage: '{config.cloud_provider}'")


def create_channel_repository(
    config: AppConfig,
    table_override: Optional[str] = None,
) -> ChannelRepository:
    """Instantiate the configured ChannelRepository (DynamoDB or Google Sheet fallback)."""
    provider = (config.cloud_provider or "aws").lower()
    active_table = table_override or config.dynamodb_table_name
    if provider == "aws" and active_table:
        return DynamoDBChannelStore(active_table, region_name=config.aws_region)
    if config.spreadsheet_url:
        return GoogleSheetChannelRepository(config.spreadsheet_url)
    raise ValueError(
        f"No channel repository configured for cloud_provider='{config.cloud_provider}'"
    )


def create_notification_provider(config: AppConfig) -> Optional[NotificationProvider]:
    """Instantiate the configured NotificationProvider if an alert target is configured."""
    provider = (config.cloud_provider or "aws").lower()
    if provider == "aws" and config.sns_topic_arn:
        return SNSNotificationProvider(
            topic_arn=config.sns_topic_arn, region_name=config.aws_region
        )
    return None

