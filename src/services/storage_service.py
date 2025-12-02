"""
Storage Service - MinIO Object Storage Integration

Provides persistent storage for contract documents with:
- PDF file storage and retrieval
- Streaming support for large files
- Presigned URLs for direct access
- Real-time analysis pipeline integration
"""

import io
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import AsyncIterator, BinaryIO

from minio import Minio
from minio.error import S3Error

from src.config import settings
from src.observability.logger import get_logger
from src.observability.tracer import trace_operation

logger = get_logger(__name__, service="storage")

# Default bucket for contracts
CONTRACTS_BUCKET = "contracts"


@dataclass
class StoredDocument:
    """Represents a stored document."""

    object_name: str
    bucket: str
    size: int
    content_type: str
    etag: str
    metadata: dict[str, str]


class StorageService:
    """
    MinIO-based object storage service for contract documents.

    Features:
    - Async-compatible file upload/download
    - Streaming for large files
    - Presigned URLs for direct client access
    - Automatic bucket creation
    - Metadata storage with documents

    Usage:
        storage = StorageService()

        # Upload a document
        doc = await storage.upload_document(
            file_data=pdf_bytes,
            filename="contract.pdf",
            document_id="doc-123"
        )

        # Get document for analysis
        content = await storage.get_document("doc-123")

        # Stream large document
        async for chunk in storage.stream_document("doc-123"):
            process(chunk)
    """

    def __init__(
        self,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        secure: bool = False,
    ):
        """
        Initialize MinIO client.

        Args:
            endpoint: MinIO server endpoint (default: localhost:9000)
            access_key: Access key (default: minioadmin)
            secret_key: Secret key (default: minioadmin)
            secure: Use HTTPS (default: False for local dev)
        """
        self.endpoint = endpoint or getattr(settings, "minio_endpoint", "localhost:9000")
        self.access_key = access_key or getattr(settings, "minio_access_key", "minioadmin")
        self.secret_key = secret_key or getattr(settings, "minio_secret_key", "minioadmin")
        self.secure = secure

        self._client: Minio | None = None
        logger.info("StorageService initialized", endpoint=self.endpoint)

    @property
    def client(self) -> Minio:
        """Lazy initialization of MinIO client."""
        if self._client is None:
            self._client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
            )
            logger.info("MinIO client connected")
        return self._client

    async def ensure_bucket(self, bucket_name: str = CONTRACTS_BUCKET) -> bool:
        """
        Ensure bucket exists, create if not.

        Args:
            bucket_name: Name of the bucket

        Returns:
            True if bucket exists or was created
        """
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
                logger.info("Bucket created", bucket=bucket_name)
            return True
        except S3Error as e:
            logger.error("Failed to ensure bucket", error=str(e))
            return False

    async def upload_document(
        self,
        file_data: bytes | BinaryIO,
        filename: str,
        document_id: str | None = None,
        bucket: str = CONTRACTS_BUCKET,
        metadata: dict[str, str] | None = None,
    ) -> StoredDocument:
        """
        Upload a document to MinIO.

        Args:
            file_data: File content as bytes or file-like object
            filename: Original filename
            document_id: Optional document ID (generated if not provided)
            bucket: Target bucket
            metadata: Optional metadata to store with document

        Returns:
            StoredDocument with storage details
        """
        with trace_operation("upload_document", {"filename": filename}):
            # Ensure bucket exists
            await self.ensure_bucket(bucket)

            # Generate document ID if not provided
            doc_id = document_id or str(uuid.uuid4())

            # Determine content type
            content_type = "application/pdf" if filename.lower().endswith(".pdf") else "application/octet-stream"

            # Build object name with document ID
            extension = filename.split(".")[-1] if "." in filename else "pdf"
            object_name = f"{doc_id}.{extension}"

            # Prepare metadata
            doc_metadata = {
                "document_id": doc_id,
                "original_filename": filename,
                **(metadata or {}),
            }

            try:
                # Convert bytes to file-like object if needed
                if isinstance(file_data, bytes):
                    file_obj = io.BytesIO(file_data)
                    file_size = len(file_data)
                else:
                    file_obj = file_data
                    file_obj.seek(0, 2)  # Seek to end
                    file_size = file_obj.tell()
                    file_obj.seek(0)  # Reset to start

                # Upload to MinIO
                result = self.client.put_object(
                    bucket_name=bucket,
                    object_name=object_name,
                    data=file_obj,
                    length=file_size,
                    content_type=content_type,
                    metadata=doc_metadata,
                )

                logger.info(
                    "Document uploaded",
                    document_id=doc_id,
                    object_name=object_name,
                    size=file_size,
                )

                return StoredDocument(
                    object_name=object_name,
                    bucket=bucket,
                    size=file_size,
                    content_type=content_type,
                    etag=result.etag,
                    metadata=doc_metadata,
                )

            except S3Error as e:
                logger.error("Upload failed", error=str(e))
                raise

    async def get_document(
        self,
        document_id: str,
        bucket: str = CONTRACTS_BUCKET,
    ) -> bytes:
        """
        Get document content by ID.

        Args:
            document_id: Document identifier
            bucket: Source bucket

        Returns:
            Document content as bytes
        """
        with trace_operation("get_document", {"document_id": document_id}):
            # Find the object (try common extensions)
            object_name = await self._find_object(document_id, bucket)

            if not object_name:
                raise FileNotFoundError(f"Document not found: {document_id}")

            try:
                response = self.client.get_object(bucket, object_name)
                content = response.read()
                response.close()
                response.release_conn()

                logger.debug("Document retrieved", document_id=document_id, size=len(content))
                return content

            except S3Error as e:
                logger.error("Get document failed", error=str(e))
                raise

    async def stream_document(
        self,
        document_id: str,
        bucket: str = CONTRACTS_BUCKET,
        chunk_size: int = 1024 * 1024,  # 1MB chunks
    ) -> AsyncIterator[bytes]:
        """
        Stream document content for large file processing.

        Args:
            document_id: Document identifier
            bucket: Source bucket
            chunk_size: Size of each chunk in bytes

        Yields:
            Document content in chunks
        """
        with trace_operation("stream_document", {"document_id": document_id}):
            object_name = await self._find_object(document_id, bucket)

            if not object_name:
                raise FileNotFoundError(f"Document not found: {document_id}")

            try:
                response = self.client.get_object(bucket, object_name)

                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk

                response.close()
                response.release_conn()

            except S3Error as e:
                logger.error("Stream failed", error=str(e))
                raise

    async def get_presigned_url(
        self,
        document_id: str,
        bucket: str = CONTRACTS_BUCKET,
        expires: timedelta = timedelta(hours=1),
    ) -> str:
        """
        Get a presigned URL for direct document access.

        Useful for:
        - Direct client downloads
        - Sharing documents temporarily
        - Bypassing API for large files

        Args:
            document_id: Document identifier
            bucket: Source bucket
            expires: URL expiration time

        Returns:
            Presigned URL string
        """
        object_name = await self._find_object(document_id, bucket)

        if not object_name:
            raise FileNotFoundError(f"Document not found: {document_id}")

        try:
            url = self.client.presigned_get_object(
                bucket_name=bucket,
                object_name=object_name,
                expires=expires,
            )

            logger.debug("Presigned URL generated", document_id=document_id)
            return url

        except S3Error as e:
            logger.error("Presigned URL generation failed", error=str(e))
            raise

    async def delete_document(
        self,
        document_id: str,
        bucket: str = CONTRACTS_BUCKET,
    ) -> bool:
        """
        Delete a document from storage.

        Args:
            document_id: Document identifier
            bucket: Source bucket

        Returns:
            True if deleted successfully
        """
        with trace_operation("delete_document", {"document_id": document_id}):
            object_name = await self._find_object(document_id, bucket)

            if not object_name:
                return False

            try:
                self.client.remove_object(bucket, object_name)
                logger.info("Document deleted", document_id=document_id)
                return True

            except S3Error as e:
                logger.error("Delete failed", error=str(e))
                return False

    async def list_documents(
        self,
        bucket: str = CONTRACTS_BUCKET,
        prefix: str = "",
        limit: int = 100,
    ) -> list[StoredDocument]:
        """
        List documents in a bucket.

        Args:
            bucket: Bucket to list
            prefix: Optional prefix filter
            limit: Maximum documents to return

        Returns:
            List of StoredDocument objects
        """
        try:
            objects = self.client.list_objects(
                bucket_name=bucket,
                prefix=prefix,
            )

            documents = []
            for obj in objects:
                if len(documents) >= limit:
                    break

                # Get full object info including metadata
                stat = self.client.stat_object(bucket, obj.object_name)

                documents.append(StoredDocument(
                    object_name=obj.object_name,
                    bucket=bucket,
                    size=obj.size,
                    content_type=stat.content_type or "application/octet-stream",
                    etag=obj.etag,
                    metadata=stat.metadata or {},
                ))

            return documents

        except S3Error as e:
            logger.error("List documents failed", error=str(e))
            return []

    async def get_document_info(
        self,
        document_id: str,
        bucket: str = CONTRACTS_BUCKET,
    ) -> StoredDocument | None:
        """
        Get document metadata without downloading content.

        Args:
            document_id: Document identifier
            bucket: Source bucket

        Returns:
            StoredDocument with metadata, or None if not found
        """
        object_name = await self._find_object(document_id, bucket)

        if not object_name:
            return None

        try:
            stat = self.client.stat_object(bucket, object_name)

            return StoredDocument(
                object_name=object_name,
                bucket=bucket,
                size=stat.size,
                content_type=stat.content_type or "application/octet-stream",
                etag=stat.etag,
                metadata=stat.metadata or {},
            )

        except S3Error:
            return None

    async def _find_object(
        self,
        document_id: str,
        bucket: str,
    ) -> str | None:
        """Find object name by document ID."""
        # Try common extensions
        for ext in ["pdf", "PDF", ""]:
            object_name = f"{document_id}.{ext}" if ext else document_id
            try:
                self.client.stat_object(bucket, object_name)
                return object_name
            except S3Error:
                continue

        return None

    async def health_check(self) -> bool:
        """Check if MinIO is healthy."""
        try:
            self.client.list_buckets()
            return True
        except Exception:
            return False


# Singleton instance
_storage_service: StorageService | None = None


def get_storage_service() -> StorageService:
    """Get or create singleton StorageService instance."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
