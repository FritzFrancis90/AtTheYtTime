"""Unit tests for cloud-provider decoupling (Interfaces, Factory, and Dependency Injection)."""

from datetime import datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from podtube.config import AppConfig
from podtube.models import Channel
from podtube.pipeline import run_sync
from podtube.services.channel_store import (
    DynamoDBChannelStore,
    GoogleSheetChannelRepository,
)
from podtube.services.factory import (
    create_channel_repository,
    create_notification_provider,
    create_storage_provider,
)
from podtube.services.interfaces import (
    ChannelRepository,
    NotificationProvider,
    StorageProvider,
)
from podtube.services.notifications import SNSNotificationProvider
from podtube.services.storage import AWSStorage


class InMemoryStorage:
    """Provider-agnostic in-memory StorageProvider for testing decoupling."""

    def __init__(self):
        self.files: dict[str, bytes] = {}

    def GetFilesFromBucket(self, filename: str) -> list:
        return [k for k in self.files if k.startswith(filename)]

    def GetProposedNewFileLocation(
        self, filepath: str, designatedFileName: str = None
    ) -> str:
        return f"https://storage.example.com/{designatedFileName}"

    def UploadFile(self, filepath: str, designatedFileName: str = None) -> str:
        key = designatedFileName or Path(filepath).name
        self.files[key] = b"uploaded"
        return self.GetProposedNewFileLocation(filepath, key)

    def DownloadFile(self, filename: str, designatedFileName: str = None) -> None:
        if designatedFileName and filename in self.files:
            Path(designatedFileName).write_bytes(self.files[filename])

    def FileExists(self, filename: str) -> bool:
        return filename in self.files

    def DeleteFile(self, filename: str) -> bool:
        self.files.pop(filename, None)
        return True

    def GeneratePresignedUrl(self, filename: str, expires_in: int = 604800) -> str:
        return f"https://storage.example.com/{filename}?expires={expires_in}"


class InMemoryChannelRepo:
    """Provider-agnostic in-memory ChannelRepository for testing decoupling."""

    def __init__(self, channels: list[Channel]):
        self._channels = list(channels)

    def get_channels(self) -> list[Channel]:
        return list(self._channels)

    def put_channel(self, channel: Channel) -> None:
        self._channels.append(channel)

    def import_channels(self, channels: list[Channel]) -> int:
        self._channels.extend(channels)
        return len(channels)


def _make_config(cloud_provider: str = "aws", **overrides) -> AppConfig:
    data = dict(
        project_root=Path("/tmp"),
        config_file=Path("/tmp/config.yaml"),
        days_back=7,
        included_font=Path("/tmp/font.ttf"),
        save_location="/tmp/podtube",
        save_dir=Path("/tmp/podtube"),
        spreadsheet_url="https://example.com/sheet.csv",
        api_key="test-key",
        last_run_timestamp=datetime(2026, 11, 10, tzinfo=timezone.utc),
        aws_bucket_name="test-bucket",
        aws_bucket_location="https://s3-{0}.amazonaws.com/{1}/{2}",
        cloud_provider=cloud_provider,
    )
    data.update(overrides)
    return AppConfig(**data)


class TestProviderDecoupling(unittest.TestCase):
    def test_adapters_satisfy_runtime_protocols(self):
        mem_storage = InMemoryStorage()
        mem_repo = InMemoryChannelRepo([])
        sheet_repo = GoogleSheetChannelRepository("https://example.com/sheet.csv")
        sns_notifier = SNSNotificationProvider(
            topic_arn="arn:aws:sns:us-east-1:123:alerts", region_name="us-east-1"
        )

        self.assertIsInstance(mem_storage, StorageProvider)
        self.assertIsInstance(mem_repo, ChannelRepository)
        self.assertIsInstance(sheet_repo, ChannelRepository)
        self.assertIsInstance(sns_notifier, NotificationProvider)

    def test_factory_creates_aws_and_sheet_providers(self):
        cfg = _make_config(
            dynamodb_table_name="podtube-channels",
            sns_topic_arn="arn:aws:sns:us-east-1:123:alerts",
            aws_region="us-east-1",
        )
        with patch("podtube.services.storage.boto3.resource"), patch(
            "podtube.services.channel_store.boto3.resource"
        ):
            storage = create_storage_provider(cfg)
            repo = create_channel_repository(cfg)
            notifier = create_notification_provider(cfg)

            self.assertIsInstance(storage, AWSStorage)
            self.assertIsInstance(repo, DynamoDBChannelStore)
            self.assertIsInstance(notifier, SNSNotificationProvider)

    def test_factory_raises_for_unsupported_cloud_provider(self):
        cfg = _make_config(cloud_provider="unsupported_cloud")
        with self.assertRaises(ValueError):
            create_storage_provider(cfg)

    def test_run_sync_operates_with_injected_non_aws_providers(self):
        cfg = _make_config(cloud_provider="custom")
        ch = Channel(
            {
                "channel_id": "UC_CUSTOM",
                "channel_name": "Custom Cloud Channel",
                "active": True,
                "minute_limit": 0,
                "include_keywords": "",
                "exclude_keywords": "",
            }
        )
        custom_storage = InMemoryStorage()
        custom_repo = InMemoryChannelRepo([ch])

        with patch("podtube.pipeline.VideoQuery") as mock_vq_cls, patch(
            "podtube.pipeline.AWSStorage"
        ) as mock_aws_storage:
            mock_vq_cls.return_value.GetVideosFromChannel.return_value = []

            stats = run_sync(
                cfg,
                dry_run=True,
                update_timestamp=False,
                storage=custom_storage,
                channel_repo=custom_repo,
            )

            self.assertEqual(stats.channels_checked, 1)
            # AWSStorage should never be instantiated when a custom storage provider is injected
            mock_aws_storage.assert_not_called()

    def test_aws_storage_private_upload_and_presigned_url(self):
        with patch("podtube.services.storage.boto3.resource") as mock_res:
            mock_client = mock_res.return_value.meta.client
            mock_client.get_bucket_location.return_value = {
                "LocationConstraint": "us-east-1"
            }
            mock_client.generate_presigned_url.return_value = (
                "https://signed.example.com/UC123/ep1.mp3?sig=1"
            )

            storage = AWSStorage(
                "my-bucket",
                "https://s3-{0}.amazonaws.com/{1}/{2}",
                public_read=False,
            )
            storage.UploadFile("/tmp/ep1.mp3", designatedFileName="UC123/ep1.mp3")

            mock_client.upload_file.assert_called_once_with(
                "/tmp/ep1.mp3",
                "my-bucket",
                "UC123/ep1.mp3",
                ExtraArgs=None,
            )

            signed = storage.GeneratePresignedUrl("UC123/ep1.mp3", expires_in=7200)
            self.assertEqual(signed, "https://signed.example.com/UC123/ep1.mp3?sig=1")
            mock_client.generate_presigned_url.assert_called_once_with(
                "get_object",
                Params={"Bucket": "my-bucket", "Key": "UC123/ep1.mp3"},
                ExpiresIn=7200,
            )


if __name__ == "__main__":
    unittest.main()

