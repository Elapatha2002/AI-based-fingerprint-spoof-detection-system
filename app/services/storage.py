"""
S3 storage service.

Thin wrapper around boto3 for uploading fingerprint images, XAI heatmaps
and forensic PDF reports to an S3 bucket. The rest of the app should never
call boto3 directly — it goes through this module so that the app can be
switched to a different backend (local disk, MinIO, etc.) later by swapping
this one file.

All uploads are private (bucket blocks public access). Downloads are served
through short-lived presigned URLs so Streamlit can render images from S3
without granting public read access.

Bucket layout:
    uploads/<case_id>/<analysis_id>.<ext>
    heatmaps/<analysis_id>/<method>.png
    reports/<case_id>/<report_id>.pdf
"""
from __future__ import annotations

import io
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class S3Config:
    access_key: str
    secret_key: str
    region: str
    bucket: str

    @classmethod
    def from_env(cls) -> "S3Config":
        return cls(
            access_key=os.environ.get("AWS_ACCESS_KEY_ID", ""),
            secret_key=os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
            region=os.environ.get("AWS_REGION", "ap-south-1"),
            bucket=os.environ.get("S3_BUCKET_NAME", ""),
        )

    def is_configured(self) -> bool:
        return (bool(self.access_key)
                and bool(self.secret_key)
                and bool(self.bucket)
                and "REPLACE" not in self.access_key
                and "REPLACE" not in self.bucket)


class StorageService:
    """Uploads and retrieves objects from the configured S3 bucket."""

    def __init__(self, config: Optional[S3Config] = None):
        self.config = config or S3Config.from_env()
        self._client = None

    @property
    def client(self):
        if self._client is None:
            if not self.config.is_configured():
                raise RuntimeError(
                    "S3 is not configured. Fill in AWS_ACCESS_KEY_ID, "
                    "AWS_SECRET_ACCESS_KEY and S3_BUCKET_NAME in .env"
                )
            self._client = boto3.client(
                "s3",
                aws_access_key_id=self.config.access_key,
                aws_secret_access_key=self.config.secret_key,
                region_name=self.config.region,
            )
        return self._client

    def health_check(self) -> tuple[bool, str]:
        """Verify credentials and bucket accessibility. Returns (ok, message)."""
        try:
            self.client.head_bucket(Bucket=self.config.bucket)
            return True, f"OK — bucket '{self.config.bucket}' reachable"
        except NoCredentialsError:
            return False, "No AWS credentials found. Check .env"
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "Unknown")
            return False, f"AWS error [{code}]: {e}"
        except Exception as e:
            return False, f"Unexpected error: {e}"

    def upload_bytes(self, key: str, data: bytes,
                     content_type: Optional[str] = None) -> str:
        """Upload raw bytes to S3 at the given key. Returns the S3 key."""
        if content_type is None:
            content_type, _ = mimetypes.guess_type(key)
            if content_type is None:
                content_type = "application/octet-stream"
        self.client.put_object(
            Bucket=self.config.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            ServerSideEncryption="AES256",
        )
        return key

    def upload_file(self, key: str, local_path: str) -> str:
        """Upload a local file. Returns the S3 key."""
        with open(local_path, "rb") as f:
            return self.upload_bytes(key, f.read())

    def download_bytes(self, key: str) -> bytes:
        """Fetch object bytes back from S3."""
        buf = io.BytesIO()
        self.client.download_fileobj(self.config.bucket, key, buf)
        return buf.getvalue()

    def presigned_url(self, key: str, expires_seconds: int = 3600) -> str:
        """Generate a short-lived signed URL that lets a browser fetch this
        object without exposing credentials. Default expiry: 1 hour."""
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.config.bucket, "Key": key},
            ExpiresIn=expires_seconds,
        )

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.config.bucket, Key=key)

    def object_exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.config.bucket, Key=key)
            return True
        except ClientError:
            return False


# ── Key builders (single source of truth for bucket layout) ─────────

def upload_key(case_id: str, analysis_id: str, extension: str = "png") -> str:
    return f"uploads/{case_id}/{analysis_id}.{extension.lstrip('.')}"


def heatmap_key(analysis_id: str, method: str) -> str:
    return f"heatmaps/{analysis_id}/{method}.png"


def report_key(case_id: str, report_id: str) -> str:
    return f"reports/{case_id}/{report_id}.pdf"


# ── Module-level singleton (lazy) ────────────────────────────────────

_service: Optional[StorageService] = None


def get_storage() -> StorageService:
    global _service
    if _service is None:
        _service = StorageService()
    return _service
