# MinIO client initialization and S3-compatible storage operations wrapper

from minio import Minio
from minio.error import S3Error
from typing import BinaryIO, Optional, Dict, Any
import io
import os
from datetime import timedelta

import urllib3
from urllib.parse import urlparse
from .config import settings


class MinIOClient:
    """MinIO S3-compatible storage client wrapper"""

    def __init__(self):
        # Remove protocol prefix for endpoint
        endpoint = settings.s3_endpoint.replace("http://", "").replace("https://", "")

        # Tune underlying HTTP connection pool.
        # This prevents urllib3 "Connection pool is full" warnings under parallel
        # downloads/streams and reduces connection churn.
        pool_maxsize = int(os.getenv("S3_HTTP_POOL_MAXSIZE", "32"))
        connect_timeout = float(os.getenv("S3_HTTP_CONNECT_TIMEOUT", "5"))
        read_timeout = float(os.getenv("S3_HTTP_READ_TIMEOUT", "60"))
        total_retries = int(os.getenv("S3_HTTP_TOTAL_RETRIES", "3"))
        backoff = float(os.getenv("S3_HTTP_BACKOFF_FACTOR", "0.2"))

        http_client = urllib3.PoolManager(
            maxsize=pool_maxsize,
            timeout=urllib3.Timeout(connect=connect_timeout, read=read_timeout),
            retries=urllib3.Retry(
                total=total_retries,
                backoff_factor=backoff,
                status_forcelist=[500, 502, 503, 504],
                allowed_methods={"GET", "PUT", "POST", "HEAD", "DELETE"},
            ),
        )

        self.client = Minio(
            endpoint=endpoint,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            secure=False,  # HTTP for local development
            region="",  # No region for local MinIO
            http_client=http_client,
        )
        self.bucket_name = settings.s3_bucket
        self._ensure_bucket_exists()

        # Presign clients: presigned URLs must be signed with a hostname that the CLIENT can reach.
        # We support two public endpoints (local + tailscale/remote) and choose based on a hint.
        self._presign_clients: Dict[str, Minio] = {}

    @staticmethod
    def _parse_public_endpoint(url_or_hostport: str) -> tuple[str, bool]:
        """
        Accepts either:
        - full URL: http://1.2.3.4:9000
        - host:port: 1.2.3.4:9000

        Returns: (endpoint_without_scheme, secure)
        """
        raw = (url_or_hostport or "").strip()
        if not raw:
            raise ValueError("Empty endpoint")

        if "://" not in raw:
            return raw, False

        parsed = urlparse(raw)
        if not parsed.netloc:
            raise ValueError(f"Invalid endpoint URL: {raw}")
        secure = parsed.scheme.lower() == "https"
        return parsed.netloc, secure

    def _get_presign_client(self, network: Optional[str] = None) -> Minio:
        """
        network:
          - "local": sign URLs against S3_PRESIGN_ENDPOINT_LOCAL
          - "remote": sign URLs against S3_PRESIGN_ENDPOINT_REMOTE
          - None/"auto": prefer local if set, else remote if set, else internal endpoint
        """
        net = (network or "auto").strip().lower()
        if net not in ("auto", "local", "remote"):
            net = "auto"

        env_local = os.getenv("S3_PRESIGN_ENDPOINT_LOCAL", "").strip()
        env_remote = os.getenv("S3_PRESIGN_ENDPOINT_REMOTE", "").strip()
        env_single = os.getenv("S3_PRESIGN_ENDPOINT", "").strip()

        chosen = ""
        chosen_key = ""

        if env_single:
            chosen = env_single
            chosen_key = "single"
        elif net == "local" and env_local:
            chosen = env_local
            chosen_key = "local"
        elif net == "remote" and env_remote:
            chosen = env_remote
            chosen_key = "remote"
        else:
            # auto
            if env_local:
                chosen = env_local
                chosen_key = "local"
            elif env_remote:
                chosen = env_remote
                chosen_key = "remote"

        if not chosen:
            # Fallback: internal docker hostname (only works inside docker network)
            chosen_key = "internal"
            endpoint = settings.s3_endpoint.replace("http://", "").replace("https://", "")
            secure = False
        else:
            endpoint, secure = self._parse_public_endpoint(chosen)

        cache_key = f"{chosen_key}:{endpoint}:{'https' if secure else 'http'}"
        if cache_key in self._presign_clients:
            return self._presign_clients[cache_key]

        # Important: set a concrete region to avoid MinIO client doing a bucket-location
        # network call on presign (which can emit urllib3 MaxRetryError if the public
        # endpoint isn't reachable from inside Docker).
        presign_region = os.getenv("S3_PRESIGN_REGION", "us-east-1").strip() or "us-east-1"

        client = Minio(
            endpoint=endpoint,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            secure=secure,
            region=presign_region,
        )
        self._presign_clients[cache_key] = client
        return client

    def _ensure_bucket_exists(self) -> None:
        """Create bucket if it doesn't exist"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
        except S3Error as e:
            raise Exception(f"Failed to create/access bucket '{self.bucket_name}': {e}")

    def upload_file(
        self,
        file_obj: BinaryIO,
        object_name: str,
        file_size: int,
        content_type: str = "application/octet-stream"
    ) -> str:
        """
        Upload file to MinIO

        Args:
            file_obj: File-like object to upload
            object_name: S3 object key/path
            file_size: Size of file in bytes
            content_type: MIME type

        Returns:
            str: Object name/key
        """
        try:
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=file_obj,
                length=file_size,
                content_type=content_type
            )
            return object_name
        except S3Error as e:
            raise Exception(f"Failed to upload file '{object_name}': {e}")

    def download_file(self, object_name: str, file_path: str) -> None:
        """
        Download file from MinIO to local path

        Args:
            object_name: S3 object key
            file_path: Local file path to save to
        """
        try:
            self.client.fget_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                file_path=file_path
            )
        except S3Error as e:
            raise Exception(f"Failed to download file '{object_name}': {e}")

    def get_file_stream(self, object_name: str, chunk_size: int = 8 * 1024 * 1024):
        """
        Get file as stream from MinIO with efficient chunking

        Args:
            object_name: S3 object key
            chunk_size: Size of chunks to yield (default 8MB for optimal throughput)

        Yields:
            bytes: Chunks of file data
        """
        try:
            response = self.client.get_object(
                bucket_name=self.bucket_name,
                object_name=object_name
            )
            try:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
            finally:
                response.close()
                response.release_conn()
        except S3Error as e:
            raise Exception(f"Failed to get file stream '{object_name}': {e}")

    def get_file_stream_range(self, object_name: str, offset: int = 0, length: int = 0, chunk_size: int = 8 * 1024 * 1024):
        """
        Get partial file as stream from MinIO (for byte-range requests)

        Args:
            object_name: S3 object key
            offset: Start byte position
            length: Number of bytes to read
            chunk_size: Size of chunks to yield (default 8MB for optimal throughput)

        Yields:
            bytes: Chunks of file data
        """
        try:
            response = self.client.get_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                offset=offset,
                length=length
            )
            try:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
            finally:
                response.close()
                response.release_conn()
        except S3Error as e:
            raise Exception(f"Failed to get file stream range '{object_name}': {e}")

    def get_presigned_get_url(
        self,
        object_name: str,
        expires_seconds: Optional[int] = None,
        download_filename: Optional[str] = None,
        response_content_type: Optional[str] = None,
        network: Optional[str] = None,
    ) -> str:
        """
        Generate a presigned GET URL for direct download/streaming from MinIO.

        Args:
            object_name: S3 object key
            expires_seconds: Expiry in seconds (default from env S3_PRESIGN_EXPIRES_SECONDS or 900)
            download_filename: If set, adds Content-Disposition attachment filename
            response_content_type: If set, forces response Content-Type
        """
        try:
            expires_seconds = int(expires_seconds or os.getenv("S3_PRESIGN_EXPIRES_SECONDS", "900"))
            response_headers: Dict[str, str] = {}
            if download_filename:
                response_headers["response-content-disposition"] = f'attachment; filename="{download_filename}"'
            if response_content_type:
                response_headers["response-content-type"] = response_content_type

            presign_client = self._get_presign_client(network=network)
            return presign_client.presigned_get_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                expires=timedelta(seconds=expires_seconds),
                response_headers=response_headers or None,
            )
        except S3Error as e:
            raise Exception(f"Failed to create presigned GET url for '{object_name}': {e}")

    def get_presigned_put_url(
        self,
        object_name: str,
        expires_seconds: Optional[int] = None,
        network: Optional[str] = None,
    ) -> str:
        """
        Generate a presigned PUT URL for direct upload to MinIO.

        Args:
            object_name: S3 object key
            expires_seconds: Expiry in seconds (default from env S3_PRESIGN_EXPIRES_SECONDS or 900)
        """
        try:
            expires_seconds = int(expires_seconds or os.getenv("S3_PRESIGN_EXPIRES_SECONDS", "900"))
            presign_client = self._get_presign_client(network=network)
            return presign_client.presigned_put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                expires=timedelta(seconds=expires_seconds),
            )
        except S3Error as e:
            raise Exception(f"Failed to create presigned PUT url for '{object_name}': {e}")

    def file_exists(self, object_name: str) -> bool:
        """
        Check if file exists in MinIO

        Args:
            object_name: S3 object key

        Returns:
            bool: True if exists
        """
        try:
            self.client.stat_object(
                bucket_name=self.bucket_name,
                object_name=object_name
            )
            return True
        except S3Error:
            return False

    def get_file_info(self, object_name: str) -> Optional[Dict[str, Any]]:
        """
        Get file metadata from MinIO

        Args:
            object_name: S3 object key

        Returns:
            Dict with file info or None if not found
        """
        try:
            stat = self.client.stat_object(
                bucket_name=self.bucket_name,
                object_name=object_name
            )
            return {
                "size": stat.size,
                "last_modified": stat.last_modified,
                "content_type": stat.content_type,
                "etag": stat.etag
            }
        except S3Error:
            return None

    def delete_file(self, object_name: str) -> bool:
        """
        Delete file from MinIO

        Args:
            object_name: S3 object key

        Returns:
            bool: True if deleted successfully
        """
        try:
            self.client.remove_object(
                bucket_name=self.bucket_name,
                object_name=object_name
            )
            return True
        except S3Error as e:
            raise Exception(f"Failed to delete file '{object_name}': {e}")

    def list_files(self, prefix: str = "", recursive: bool = True) -> list:
        """
        List files in bucket with optional prefix

        Args:
            prefix: Filter by prefix (like a directory)
            recursive: Whether to list recursively

        Returns:
            List of file info dicts
        """
        try:
            objects = self.client.list_objects(
                bucket_name=self.bucket_name,
                prefix=prefix,
                recursive=recursive
            )
            return [
                {
                    "object_name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified,
                    "etag": obj.etag
                }
                for obj in objects
            ]
        except S3Error as e:
            raise Exception(f"Failed to list files: {e}")


# Global MinIO client instance
minio_client = MinIOClient()