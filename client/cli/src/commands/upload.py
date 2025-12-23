# Upload command - uploads files to server via curl

import os
import typer
import shutil
import tempfile
import subprocess
import json
from pathlib import Path
from typing import Optional
import mimetypes
from rich.console import Console

console = Console()


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
    console.print(f"[blue]📊 Size:[/blue] {file_size:,} bytes")
    if description:
        console.print(f"[blue]📝 Description:[/blue] {description}")

    try:
        # Test server connectivity
        console.print(f"[yellow]🔍 Testing server connectivity...[/yellow]")
        health_result = subprocess.run(
            ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', f'{server_url}/health'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if health_result.stdout != '200':
            console.print(f"[red]❌ Server not reachable (status: {health_result.stdout})[/red]")
            raise typer.Exit(1)
        console.print(f"[green]✅ Server is reachable[/green]")

        # Optional: direct-to-MinIO upload via presigned URL (bypasses API data path)
        use_direct = os.getenv("NEBULA_DIRECT_S3", "0").strip().lower() in ("1", "true", "yes", "y")
        if use_direct:
            guessed_type, _ = mimetypes.guess_type(filename)
            content_type = guessed_type or "application/octet-stream"

            console.print("[dim]⚡ Using direct MinIO upload (presigned URL)[/dim]")

            # 1) Ask API for presigned PUT URL
            presign_payload = {"filename": filename, "content_type": content_type, "description": description}
            presign_cmd = [
                "curl", "-s",
                "-X", "POST",
                f"{server_url}/api/upload/presign",
                "-H", "Content-Type: application/json",
                "-d", json.dumps(presign_payload),
            ]
            presign_result = subprocess.run(presign_cmd, capture_output=True, text=True, timeout=30)
            if presign_result.returncode != 0:
                console.print(f"[red]❌ Presign failed: {presign_result.stderr}[/red]")
                raise typer.Exit(1)
            presign_data = json.loads(presign_result.stdout)
            if not presign_data.get("success") or not presign_data.get("upload_url") or not presign_data.get("object_key"):
                console.print(f"[red]❌ Presign returned invalid response: {presign_result.stdout}[/red]")
                raise typer.Exit(1)

            upload_url = presign_data["upload_url"]
            object_key = presign_data["object_key"]

            # 2) Upload file directly to MinIO via presigned PUT
            put_cmd = [
                "curl", "-s",
                "-X", "PUT",
                "-H", f"Content-Type: {content_type}",
                "--upload-file", actual_upload_path,
                upload_url,
            ]
            put_result = subprocess.run(put_cmd, capture_output=True, text=True, timeout=3600)
            if put_result.returncode != 0:
                console.print(f"[red]❌ Direct upload failed: {put_result.stderr}[/red]")
                raise typer.Exit(1)

            # 3) Register metadata in DB
            complete_payload = {
                "object_key": object_key,
                "filename": filename,
                "content_type": content_type,
                "description": description,
            }
            complete_cmd = [
                "curl", "-s",
                "-X", "POST",
                f"{server_url}/api/upload/complete",
                "-H", "Content-Type: application/json",
                "-d", json.dumps(complete_payload),
            ]
            complete_result = subprocess.run(complete_cmd, capture_output=True, text=True, timeout=30)
            if complete_result.returncode != 0:
                console.print(f"[red]❌ Complete failed: {complete_result.stderr}[/red]")
                raise typer.Exit(1)
            result = json.loads(complete_result.stdout)
            if not result.get("success") or not result.get("file"):
                console.print(f"[red]❌ Complete returned invalid response: {complete_result.stdout}[/red]")
                raise typer.Exit(1)

            file_info = result["file"]
            console.print(f"[green]✅ Upload successful![/green]")
            console.print(f"[green]📄 File ID:[/green] {file_info['id']}")
            console.print(f"[green]📁 Path:[/green] {file_info['file_path']}")
            console.print(f"[green]🕒 Uploaded:[/green] {file_info['upload_date']}")
            return

        # Build curl command
        console.print(f"[yellow]📡 Uploading {file_size:,} bytes...[/yellow]")
        curl_cmd = [
            'curl', '--no-buffer', '-s',
            '-X', 'POST',
            f'{server_url}/api/upload',
            '-F', f'file=@{actual_upload_path};filename={filename}',
        ]
        
        if description:
            curl_cmd.extend(['-F', f'description={description}'])
        
        # Run curl and capture output
        curl_result = subprocess.run(
            curl_cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        
        if curl_result.returncode != 0:
            console.print(f"[red]❌ Upload failed: {curl_result.stderr}[/red]")
            raise typer.Exit(1)
        
        # Parse JSON response
        result = json.loads(curl_result.stdout)

        # Display success
        file_info = result['file']
        console.print(f"[green]✅ Upload successful![/green]")
        console.print(f"[green]📄 File ID:[/green] {file_info['id']}")
        console.print(f"[green]📁 Path:[/green] {file_info['file_path']}")
        console.print(f"[green]🕒 Uploaded:[/green] {file_info['upload_date']}")

    except subprocess.TimeoutExpired:
        console.print("[red]❌ Upload timeout (10 minutes exceeded)[/red]")
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
