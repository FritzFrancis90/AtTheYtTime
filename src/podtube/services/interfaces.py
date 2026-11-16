"""Provider-agnostic service interfaces (Ports) for cloud storage, channel repositories, and alerts."""

from typing import Optional, Protocol, runtime_checkable
from podtube.models import Channel


@runtime_checkable
class StorageProvider(Protocol):
    """Interface for cloud object storage (e.g., AWS S3, Google Cloud Storage, Azure Blob)."""

    def GetFilesFromBucket(self, filename: str) -> list: ...

    def GetProposedNewFileLocation(
        self, filepath: str, designatedFileName: Optional[str] = None
    ) -> str: ...

    def UploadFile(
        self, filepath: str, designatedFileName: Optional[str] = None
    ) -> Optional[str]: ...

    def DownloadFile(
        self, filename: str, designatedFileName: Optional[str] = None
    ) -> None: ...

    def FileExists(self, filename: str) -> bool: ...

    def DeleteFile(self, filename: str) -> bool: ...


@runtime_checkable
class ChannelRepository(Protocol):
    """Interface for storing and retrieving channel configurations (e.g., DynamoDB, Google Sheets, Firestore)."""

    def get_channels(self) -> list[Channel]: ...

    def put_channel(self, channel: Channel) -> None: ...

    def import_channels(self, channels: list[Channel]) -> int: ...


@runtime_checkable
class NotificationProvider(Protocol):
    """Interface for sending operational alerts (e.g., AWS SNS, Email, Webhook)."""

    def send_alert(self, subject: str, message: str) -> None: ...

