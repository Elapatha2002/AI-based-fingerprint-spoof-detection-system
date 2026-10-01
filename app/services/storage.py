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

try:
    import boto3
    from botocore.config import Config as BotocoreConfig
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:  # Offline mode deliberately has no AWS dependency.
    boto3 = None
    BotocoreConfig = None

    class ClientError(Exception):
        pass

    class NoCredentialsError(Exception):
        pass
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / '.env.supabase')
load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class S3Config:
    access_key: str
    secret_key: str
    region: str
    bucket: str
    endpoint_url: str = ""
    addressing_style: str = "auto"
    server_side_encryption: str = "AES256"

    @classmethod
    def from_env(cls) -> "S3Config":
        if os.environ.get('FSDXAI_STORAGE_BACKEND', '').lower() == 'supabase':
            endpoint = os.environ.get('SUPABASE_S3_ENDPOINT', '').strip()
            if not endpoint.startswith('https://'):
                raise ValueError('SUPABASE_S3_ENDPOINT must be an HTTPS endpoint copied from Supabase.')
            return cls(
                access_key=os.environ.get('SUPABASE_S3_ACCESS_KEY_ID', ''),
                secret_key=os.environ.get('SUPABASE_S3_SECRET_ACCESS_KEY', ''),
                region=os.environ.get('SUPABASE_S3_REGION', ''),
                bucket=os.environ.get('SUPABASE_STORAGE_BUCKET', 'fingerprint-evidence'),
                endpoint_url=endpoint, addressing_style='path', server_side_encryption='none')
        return cls(
            access_key=os.environ.get("AWS_ACCESS_KEY_ID", ""),
            secret_key=os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
            region=os.environ.get("AWS_REGION", "ap-south-1"),
            bucket=os.environ.get("S3_BUCKET_NAME", ""),
            endpoint_url=os.environ.get("S3_ENDPOINT_URL", "").strip(),
            addressing_style=os.environ.get("S3_ADDRESSING_STYLE", "auto").strip(),
            server_side_encryption=os.environ.get(
                "S3_SERVER_SIDE_ENCRYPTION", "AES256"
            ).strip(),
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
            if boto3 is None:
                raise RuntimeError(
                    "The AWS SDK is not installed. Use local offline mode or "
                    "install boto3 to use S3."
                )
            client_args = {
                "service_name": "s3",
                "aws_access_key_id": self.config.access_key,
                "aws_secret_access_key": self.config.secret_key,
                "region_name": self.config.region,
            }
            if self.config.endpoint_url:
                client_args["endpoint_url"] = self.config.endpoint_url
                # OCI Object Storage's S3 Compatibility API supports path-style
                # addressing. Keep this configurable for AWS and other providers.
                if BotocoreConfig is not None:
                    client_args["config"] = BotocoreConfig(
                        s3={"addressing_style": self.config.addressing_style},
                        signature_version='s3v4',
                        request_checksum_calculation='when_required',
                        response_checksum_validation='when_required',
                    )
            self._client = boto3.client(**client_args)
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
        put_args = dict(
            Bucket=self.config.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        # AWS S3 uses AES256 by default in the existing deployment. OCI
        # buckets use their bucket-level encryption instead, so its server
        # secret file sets this value to "none" and omits the AWS-only header.
        if self.config.server_side_encryption.lower() not in {"", "none", "off"}:
            put_args["ServerSideEncryption"] = self.config.server_side_encryption
        self.client.put_object(**put_args)
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


class LocalStorageService:
    """Filesystem storage used when AWS is unavailable or local mode is requested.

    It preserves the same logical keys as S3 but writes beneath the gitignored
    ``storage_local`` folder. No cloud account, network access, or credentials
    are needed.
    """

    backend_name = "local disk"

    def __init__(self, root: Optional[Path] = None):
        configured = os.environ.get("FSDXAI_LOCAL_STORAGE_DIR", "").strip()
        selected = root or (Path(configured) if configured else
                            PROJECT_ROOT / "storage_local")
        self.root = selected.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        """Resolve a logical object key safely beneath the local root."""
        relative = Path(key.replace("\\", "/"))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Storage keys must be relative and cannot contain '..'")
        candidate = (self.root / relative).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("Storage key resolves outside the local storage root")
        return candidate

    def health_check(self) -> tuple[bool, str]:
        return True, f"OK - local storage: {self.root}"

    def upload_bytes(self, key: str, data: bytes,
                     content_type: Optional[str] = None) -> str:
        del content_type  # Retained for StorageService API compatibility.
        destination = self._path_for(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        return key

    def upload_file(self, key: str, local_path: str) -> str:
        return self.upload_bytes(key, Path(local_path).read_bytes())

    def download_bytes(self, key: str) -> bytes:
        return self._path_for(key).read_bytes()

    def presigned_url(self, key: str, expires_seconds: int = 3600) -> str:
        """Return a local URI; normal application reads use download_bytes."""
        del expires_seconds
        return self._path_for(key).as_uri()

    def delete(self, key: str) -> None:
        path = self._path_for(key)
        if path.exists():
            path.unlink()

    def object_exists(self, key: str) -> bool:
        return self._path_for(key).is_file()


# ── Key builders (single source of truth for bucket layout) ─────────

def upload_key(case_id: str, analysis_id: str, extension: str = "png") -> str:
    return f"uploads/{case_id}/{analysis_id}.{extension.lstrip('.')}"


def heatmap_key(analysis_id: str, method: str) -> str:
    return f"heatmaps/{analysis_id}/{method}.png"


def report_key(case_id: str, report_id: str) -> str:
    return f"reports/{case_id}/{report_id}.pdf"


# ── Module-level singleton (lazy) ────────────────────────────────────

_service: Optional[StorageService | LocalStorageService] = None


def offline_mode_enabled() -> bool:
    """Return true when the dedicated local recovery launcher is in use."""
    return os.environ.get("FSDXAI_OFFLINE_MODE", "").strip().lower() in {
        "1", "true", "yes", "on"
    }


def get_storage() -> StorageService | LocalStorageService:
    global _service
    if _service is None:
        backend = os.environ.get('FSDXAI_STORAGE_BACKEND', 'auto').lower()
        if backend not in ('auto', 'local', 'supabase', 's3'):
            raise ValueError('Unknown FSDXAI_STORAGE_BACKEND.')
        if backend == 'local':
            _service = LocalStorageService()
            return _service
        config = S3Config.from_env()
        if backend in ('supabase', 's3'):
            if not config.is_configured():
                raise RuntimeError('Selected cloud storage is not configured. No local fallback was used.')
            _service = StorageService(config)
            return _service
        # If configuration is absent or recovery mode is explicit, do not
        # attempt a cloud connection: use the local disk backend instead.
        _service = (LocalStorageService() if offline_mode_enabled() or
                    not config.is_configured() else StorageService(config))
    return _service
