# Upload command - uploads files to server with progress bar

import os
import typer
import shutil
import tempfile
import json
from pathlib import Path
from typing import Optional, Generator
import mimetypes
import httpx
from rich.console import Console
from rich.progress import Progress, BarColumn, TransferSpeedColumn, TimeRemainingColumn, TaskProgressColumn

console = Console()


class ProgressFileReader:
    """
    A file-like wrapper that updates a progress bar as data is read.
    Used for streaming uploads with progress tracking.
    """
    def __init__(self, file_path: str, progress: Progress, task_id):
        self.file_path = file_path
        self.file = open(file_path, 'rb')
        self.progress = progress
        self.task_id = task_id
        self.file_size = os.path.getsize(file_path)
        self.bytes_read = 0
    
    def read(self, size: int = -1) -> bytes:
        data = self.file.read(size)
        if data:
            self.bytes_read += len(data)
            self.progress.update(self.task_id, completed=self.bytes_read)
        return data
    
    def seek(self, offset: int, whence: int = 0):
        return self.file.seek(offset, whence)
    
    def tell(self) -> int:
        return self.file.tell()
    
    def close(self):
        self.file.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


def file_chunk_generator(file_path: str, progress: Progress, task_id, chunk_size: int = 1024 * 1024) -> Generator[bytes, None, None]:
    """
    Generator that yields file chunks and updates progress bar.
    """
    bytes_sent = 0
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            bytes_sent += len(chunk)
            progress.update(task_id, completed=bytes_sent)
            yield chunk


def upload_file(
    file_path: str,
    server_url: Optional[str] = None,
    description: Optional[str] = None
):
    """
    Upload a file to Nebula Cloud

    FILE_PATH: Path to the file to upload
    """
    # Load server URL from environment if not provided
    if not server_url:
        server_url = os.getenv("NEBULA_SERVER_URL")
        if not server_url:
            console.print("[red]❌ Error: NEBULA_SERVER_URL environment variable not set[/red]")
            raise typer.Exit(1)

    # Validate file exists
    if not os.path.exists(file_path):
        console.print(f"[red]❌ File not found: {file_path}[/red]")
        raise typer.Exit(1)

    # Check if it's a file (not directory)
    if not os.path.isfile(file_path):
        console.print(f"[red]❌ Path is not a file: {file_path}[/red]")
        raise typer.Exit(1)

    file_path_obj = Path(file_path)
    filename = file_path_obj.name
    file_size = os.path.getsize(file_path)

    # WSL fix: Copy Windows filesystem files to Linux temp directory first
    # This avoids slow/hanging file access from /mnt/c/
    temp_file_path = None
    actual_upload_path = file_path
    
    if file_path.startswith('/mnt/'):
        console.print(f"[yellow]📋 Copying file from Windows filesystem to Linux temp...[/yellow]")
        try:
            temp_dir = tempfile.gettempdir()
            temp_file_path = os.path.join(temp_dir, f"nebula_upload_{os.getpid()}_{filename}")
            shutil.copy2(file_path, temp_file_path)
            actual_upload_path = temp_file_path
            console.print(f"[green]✅ File copied to Linux filesystem[/green]")
        except Exception as e:
            console.print(f"[yellow]⚠️  Warning: Could not copy to temp: {e}[/yellow]")
            actual_upload_path = file_path

    # Display upload info
    console.print(f"[blue]📤 Uploading:[/blue] {filename}")
    console.print(f"[blue]📊 Size:[/blue] {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
    if description:
        console.print(f"[blue]📝 Description:[/blue] {description}")

    try:
        # Test server connectivity
        console.print(f"[yellow]🔍 Testing server connectivity...[/yellow]")
        try:
            with httpx.Client(timeout=5.0) as client:
                health_response = client.get(f'{server_url}/health')
                if health_response.status_code != 200:
                    console.print(f"[red]❌ Server not reachable (status: {health_response.status_code})[/red]")
                    raise typer.Exit(1)
            console.print(f"[green]✅ Server is reachable[/green]")
        except httpx.TimeoutException:
            console.print(f"[red]❌ Connection timed out connecting to {server_url}/health[/red]")
            raise typer.Exit(1)
        except httpx.ConnectError as e:
            console.print(f"[red]❌ Cannot connect to server: {e}[/red]")
            raise typer.Exit(1)

        # Optional: direct-to-MinIO upload via presigned URL (bypasses API data path)
        use_direct = os.getenv("NEBULA_DIRECT_S3", "0").strip().lower() in ("1", "true", "yes", "y")
        if use_direct:
            _upload_direct_s3(
                actual_upload_path=actual_upload_path,
                filename=filename,
                file_size=file_size,
                server_url=server_url,
                description=description
            )
        else:
            _upload_via_api(
                actual_upload_path=actual_upload_path,
                filename=filename,
                file_size=file_size,
                server_url=server_url,
                description=description
            )

    except typer.Exit:
        raise
    except httpx.TimeoutException:
        console.print("[red]❌ Upload timeout[/red]")
        raise typer.Exit(1)
    except json.JSONDecodeError:
        console.print(f"[red]❌ Server returned invalid response[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]❌ Upload failed: {str(e)}[/red]")
        raise typer.Exit(1)
    finally:
        # Clean up temp file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass


def _upload_direct_s3(
    actual_upload_path: str,
    filename: str,
    file_size: int,
    server_url: str,
    description: Optional[str] = None
):
    """Upload directly to MinIO via presigned URL with progress bar."""
    guessed_type, _ = mimetypes.guess_type(filename)
    content_type = guessed_type or "application/octet-stream"

    console.print("[dim]⚡ Using direct MinIO upload (presigned URL)[/dim]")

    # Determine network hint
    local_url = os.getenv("NEBULA_LOCAL_URL", "").strip().rstrip("/")
    remote_url = os.getenv("NEBULA_REMOTE_URL", "").strip().rstrip("/")
    current = (server_url or "").strip().rstrip("/")
    network = None
    if local_url and current == local_url:
        network = "local"
    elif remote_url and current == remote_url:
        network = "remote"

    # 1) Ask API for presigned PUT URL
    presign_payload = {"filename": filename, "content_type": content_type, "description": description}
    presign_endpoint = f"{server_url}/api/upload/presign"
    if network:
        presign_endpoint = f"{presign_endpoint}?network={network}"

    with httpx.Client(timeout=30.0) as client:
        presign_response = client.post(
            presign_endpoint,
            json=presign_payload
        )
        presign_response.raise_for_status()
        presign_data = presign_response.json()

    if not presign_data.get("success") or not presign_data.get("upload_url") or not presign_data.get("object_key"):
        console.print(f"[red]❌ Presign returned invalid response[/red]")
        raise typer.Exit(1)

    upload_url = presign_data["upload_url"]
    object_key = presign_data["object_key"]

    # 2) Upload file directly to MinIO via presigned PUT with progress bar
    with Progress(
        BarColumn(),
        TaskProgressColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Uploading...", total=file_size)
        
        # Use chunked upload with progress tracking
        def upload_generator():
            bytes_sent = 0
            with open(actual_upload_path, 'rb') as f:
                while True:
                    chunk = f.read(1024 * 1024)  # 1MB chunks
                    if not chunk:
                        break
                    bytes_sent += len(chunk)
                    progress.update(task, completed=bytes_sent)
                    yield chunk

        # Use a longer timeout for large file uploads (1 hour)
        with httpx.Client(timeout=httpx.Timeout(3600.0, connect=30.0)) as client:
            put_response = client.put(
                upload_url,
                content=upload_generator(),
                headers={
                    "Content-Type": content_type,
                    "Content-Length": str(file_size),
                }
            )
            
            if put_response.status_code not in (200, 201, 204):
                console.print(f"[red]❌ Direct upload failed: {put_response.status_code}[/red]")
                raise typer.Exit(1)

    # 3) Register metadata in DB
    complete_payload = {
        "object_key": object_key,
        "filename": filename,
        "content_type": content_type,
        "description": description,
    }
    
    with httpx.Client(timeout=30.0) as client:
        complete_response = client.post(
            f"{server_url}/api/upload/complete",
            json=complete_payload
        )
        complete_response.raise_for_status()
        result = complete_response.json()

    if not result.get("success") or not result.get("file"):
        console.print(f"[red]❌ Complete returned invalid response[/red]")
        raise typer.Exit(1)

    file_info = result["file"]
    console.print(f"[green]✅ Upload successful![/green]")
    console.print(f"[green]📄 File ID:[/green] {file_info['id']}")
    console.print(f"[green]📁 Path:[/green] {file_info['file_path']}")
    console.print(f"[green]🕒 Uploaded:[/green] {file_info['upload_date']}")


def _upload_via_api(
    actual_upload_path: str,
    filename: str,
    file_size: int,
    server_url: str,
    description: Optional[str] = None
):
    """Upload via API endpoint with progress bar."""
    
    # For multipart uploads, we need to track progress differently
    # We'll read the file in chunks and track as we build the request
    with Progress(
        BarColumn(),
        TaskProgressColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Uploading...", total=file_size)
        
        # Read file content with progress tracking
        # For multipart, we need to read the whole file but track progress
        file_content = bytearray()
        bytes_read = 0
        
        with open(actual_upload_path, 'rb') as f:
            while True:
                chunk = f.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                file_content.extend(chunk)
                bytes_read += len(chunk)
                progress.update(task, completed=bytes_read)
        
        # Now send the multipart form
        progress.update(task, description="[cyan]Sending to server...")
        
        files = {
            'file': (filename, bytes(file_content), 'application/octet-stream')
        }
        data = {}
        if description:
            data['description'] = description
        
        # Use a longer timeout for large file uploads (10 minutes)
        with httpx.Client(timeout=httpx.Timeout(600.0, connect=30.0)) as client:
            response = client.post(
                f'{server_url}/api/upload',
                files=files,
                data=data if data else None
            )
            response.raise_for_status()
            result = response.json()

    # Display success
    file_info = result['file']
    console.print(f"[green]✅ Upload successful![/green]")
    console.print(f"[green]📄 File ID:[/green] {file_info['id']}")
    console.print(f"[green]📁 Path:[/green] {file_info['file_path']}")
    console.print(f"[green]🕒 Uploaded:[/green] {file_info['upload_date']}")
