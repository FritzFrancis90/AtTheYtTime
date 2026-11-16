"""Unit tests for DynamoDB channel storage and Google Sheet import."""

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from podtube.config import AppConfig
from podtube.models import Channel
from podtube.pipeline import run_sync
from podtube.services.channel_store import (
    DynamoDBChannelStore,
    import_sheet_to_dynamodb,
)


class TestChannelStore(unittest.TestCase):
    def test_channel_roundtrip_between_sheet_and_dynamodb_item(self):
        sheet_row = {
            "Youtube Channel ID": " UC12345 ",
            "Youtube Channel Name": " Example Creator ",
            "Key Words To Exclude": "Shorts,#shorts",
            "Key Words To Include": "Podcast,Episode",
            "Minute Limit Per Video": "30",
            "Active": "Y",
        }
        ch_from_sheet = Channel(sheet_row)
        ddb_item = ch_from_sheet.to_dynamodb_item()

        self.assertEqual(
            ddb_item,
            {
                "channel_id": "UC12345",
                "channel_name": "Example Creator",
                "active": True,
                "minute_limit": 30,
                "include_keywords": "Podcast,Episode",
                "exclude_keywords": "Shorts,#shorts",
            },
        )

        # Simulate DynamoDB returning Decimal for numbers
        ddb_item_from_aws = dict(ddb_item, minute_limit=Decimal("30"))
        ch_from_ddb = Channel(ddb_item_from_aws)

        self.assertEqual(ch_from_ddb.ID, "UC12345")
        self.assertEqual(ch_from_ddb.Name, "Example Creator")
        self.assertEqual(ch_from_ddb.isActive, 1)
        self.assertEqual(ch_from_ddb.maxLength, 1800)
        self.assertEqual(ch_from_ddb.includePhrases, ["Podcast", "Episode"])
        self.assertEqual(ch_from_ddb.excludePhrases, ["Shorts", "#shorts"])

    def test_dynamodb_channel_store_get_channels(self):
        with patch("podtube.services.channel_store.boto3.resource") as mock_resource:
            mock_table = MagicMock()
            mock_resource.return_value.Table.return_value = mock_table
            mock_table.scan.return_value = {
                "Items": [
                    {
                        "channel_id": "UC222",
                        "channel_name": "Zeta Channel",
                        "active": True,
                        "minute_limit": Decimal("0"),
                        "include_keywords": "",
                        "exclude_keywords": "",
                    },
                    {
                        "channel_id": "UC111",
                        "channel_name": "Alpha Channel",
                        "active": False,
                        "minute_limit": Decimal("15"),
                        "include_keywords": "News",
                        "exclude_keywords": "",
                    },
                ]
            }

            store = DynamoDBChannelStore("podtube-channels", region_name="us-east-1")
            channels = store.get_channels()

            self.assertEqual([c.Name for c in channels], ["Alpha Channel", "Zeta Channel"])
            self.assertEqual(channels[0].isActive, 0)
            self.assertEqual(channels[0].maxLength, 900)
            self.assertEqual(channels[1].isActive, 1)

    def test_import_sheet_to_dynamodb_writes_all_channels(self):
        sample_channels = [
            Channel(
                {
                    "channel_id": "UC1",
                    "channel_name": "Channel One",
                    "active": True,
                    "minute_limit": 0,
                    "include_keywords": "",
                    "exclude_keywords": "",
                }
            ),
            Channel(
                {
                    "channel_id": "UC2",
                    "channel_name": "Channel Two",
                    "active": False,
                    "minute_limit": 10,
                    "include_keywords": "Talk",
                    "exclude_keywords": "Live",
                }
            ),
        ]

        with patch(
            "podtube.services.channel_store.get_channels",
            return_value=sample_channels,
        ), patch("podtube.services.channel_store.boto3.resource") as mock_resource:
            mock_table = MagicMock()
            mock_batch = MagicMock()
            mock_table.batch_writer.return_value.__enter__.return_value = mock_batch
            mock_resource.return_value.Table.return_value = mock_table

            count = import_sheet_to_dynamodb(
                spreadsheet_url="https://example.com/sheet.csv",
                table_name="podtube-channels",
                region_name="us-east-1",
            )

            self.assertEqual(count, 2)
            self.assertEqual(mock_batch.put_item.call_count, 2)

    def test_run_sync_uses_dynamodb_when_table_name_is_configured(self):
        cfg = AppConfig(
            project_root=Path("/tmp"),
            config_file=Path("/tmp/config.yaml"),
            days_back=7,
            included_font=Path("/tmp/font.ttf"),
            save_location="/tmp/podtube",
            save_dir=Path("/tmp/podtube"),
            spreadsheet_url="",
            api_key="test-key",
            last_run_timestamp=datetime(2026, 11, 10, tzinfo=timezone.utc),
            aws_bucket_name="test-bucket",
            aws_bucket_location="https://s3-{0}.amazonaws.com/{1}/{2}",
            dynamodb_table_name="podtube-channels",
        )
        ch = Channel(
            {
                "channel_id": "UC777",
                "channel_name": "DDB Channel",
                "active": True,
                "minute_limit": 0,
                "include_keywords": "",
                "exclude_keywords": "",
            }
        )

        with patch(
            "podtube.pipeline.DynamoDBChannelStore"
        ) as mock_store_cls, patch(
            "podtube.pipeline.get_channels"
        ) as mock_sheet_get, patch(
            "podtube.pipeline.VideoQuery"
        ) as mock_vq_cls, patch("podtube.pipeline.AWSStorage"):
            mock_store_cls.return_value.get_channels.return_value = [ch]
            mock_vq_cls.return_value.GetVideosFromChannel.return_value = []

            stats = run_sync(cfg, dry_run=True, update_timestamp=False)

            self.assertEqual(stats.channels_checked, 1)
            mock_store_cls.assert_called_once_with(
                "podtube-channels", region_name=None
            )
            mock_sheet_get.assert_not_called()


if __name__ == "__main__":
    unittest.main()

