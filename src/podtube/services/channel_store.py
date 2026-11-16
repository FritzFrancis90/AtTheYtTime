"""DynamoDB channel storage service and Google Sheet migration helper."""

import logging
from typing import Optional
import boto3
from podtube.models import Channel
from podtube.services.youtube import get_channels

logger = logging.getLogger(__name__)


class DynamoDBChannelStore:
    """Reads and writes PodTube channel configurations in Amazon DynamoDB."""

    def __init__(self, table_name: str, region_name: Optional[str] = None):
        self.table_name = table_name
        self.dynamodb = (
            boto3.resource("dynamodb", region_name=region_name)
            if region_name
            else boto3.resource("dynamodb")
        )
        self.table = self.dynamodb.Table(table_name)

    def get_channels(self) -> list[Channel]:
        """Fetch all channel items from DynamoDB, sorted by channel name."""
        logger.debug("Fetching channel list from DynamoDB table %s...", self.table_name)
        items = []
        response = self.table.scan()
        items.extend(response.get("Items", []))
        while "LastEvaluatedKey" in response:
            response = self.table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"]
            )
            items.extend(response.get("Items", []))

        channels = [Channel(item) for item in items]
        return sorted(channels, key=lambda ch: ch.Name.lower())

    def put_channel(self, channel: Channel) -> None:
        """Insert or update a single channel in DynamoDB."""
        self.table.put_item(Item=channel.to_dynamodb_item())
        logger.info("Saved channel %s (%s) to DynamoDB", channel.Name, channel.ID)

    def import_channels(self, channels: list[Channel]) -> int:
        """Batch-write a list of channels into the DynamoDB table."""
        count = 0
        with self.table.batch_writer() as batch:
            for ch in channels:
                batch.put_item(Item=ch.to_dynamodb_item())
                count += 1
        logger.info(
            "Imported %d channel(s) into DynamoDB table %s", count, self.table_name
        )
        return count


def import_sheet_to_dynamodb(
    spreadsheet_url: str,
    table_name: str,
    region_name: Optional[str] = None,
) -> int:
    """Fetch channels from the Google Sheet CSV and write them into DynamoDB."""
    channels = get_channels(spreadsheet_url)
    store = DynamoDBChannelStore(table_name, region_name=region_name)
    return store.import_channels(channels)

