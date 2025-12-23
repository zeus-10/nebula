# Download command - download files from server

import os
import shutil
import tempfile
import typer
from pathlib import Path
from typing import Optional
import httpx
from rich.console import Console
from rich.progress import Progress, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn

console = Console()

def download_file(
    file_id: int = typer.Argument(..., help="ID of the file to download"),
    output_path: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path (defaults to original filename)"),
    server_url: Optional[str] = None
):
    """
    Download a file from Nebula Cloud by its ID.

    Preserves the original filename if no output path is specified.
    """
    # Load server URL from environment if not provided
    if not server_url:
        server_url = os.getenv("NEBULA_SERVER_URL")
        if not server_url:
            console.print("[red]❌ Error: NEBULA_SERVER_URL environment variable not set[/red]")
            raise typer.Exit(1)

    console.print(f"[yellow]📥 Downloading file ID {file_id}...[/yellow]")

    try:
        # First, get file info to show metadata before download
        with httpx.Client(timeout=30.0) as client:
            # Get file metadata
            info_response = client.get(f"{server_url}/api/files/{file_id}")
            info_response.raise_for_status()
            result = info_response.json()
            file_info = result['file']

        console.print(f"[blue]📄 File:[/blue] {file_info['filename']}")
        console.print(f"[blue]📊 Size:[/blue] {file_info['size']:,} bytes")
        console.print(f"[blue]🏷️  Type:[/blue] {file_info['mime_type']}")
        if file_info.get('description'):
            console.print(f"[blue]📝 Description:[/blue] {file_info['description']}")

        # Determine output path
        if output_path:
            output_file = Path(output_path)
        else:
            # Default download location
            default_dir = Path("/mnt/c/Users/abhin/Desktop/nebula")
            default_dir.mkdir(parents=True, exist_ok=True)
            output_file = default_dir / file_info['filename']

        # Check if output file already exists
        if output_file.exists():
            console.print(f"[yellow]⚠️  File '{output_file}' already exists. Overwrite? (y/N): [/yellow]", end="")
            response = input().strip().lower()
            if response != 'y' and response != 'yes':
                console.print("[yellow]Download cancelled.[/yellow]")
                return

        # WSL optimization: Download to Linux temp first, then copy to Windows filesystem
        # This avoids slow I/O when writing directly to /mnt/c/
        use_temp = str(output_file).startswith('/mnt/')
        temp_file = None
        
        if use_temp:
            temp_dir = tempfile.gettempdir()
            temp_file = Path(temp_dir) / f"nebula_download_{os.getpid()}_{file_info['filename']}"
            download_target = temp_file
            console.print(f"[dim]WSL optimization: Downloading to Linux temp first...[/dim]")
        else:
            download_target = output_file

        console.print(f"[yellow]🚀 Downloading to {output_file.absolute()}...[/yellow]")

        try:
            # Prefer presigned download URL (bypass API for data path). Fallback to /download.
            download_url = f"{server_url}/api/files/{file_id}/download"
            try:
                with httpx.Client(timeout=10.0) as client:
                    presign_resp = client.get(f"{server_url}/api/files/{file_id}/download-url")
                    if presign_resp.status_code == 200:
                        presign_data = presign_resp.json()
                        if presign_data.get("success") and presign_data.get("url"):
                            download_url = presign_data["url"]
                            console.print("[dim]⚡ Using direct MinIO download (presigned URL)[/dim]")
            except Exception:
                # Silent fallback
                pass

            with httpx.Client(timeout=7200.0) as client:  # 2 hour timeout for large files
                with client.stream(
                    'GET',
                    download_url
                ) as response:
                    response.raise_for_status()

                    # Get total size from response headers
                    total_size = int(response.headers.get('content-length', file_info['size']))

                    # Create progress bar
                    with Progress(
                        BarColumn(),
                        "[progress.percentage]{task.percentage:>3.0f}%",
                        DownloadColumn(),
                        TransferSpeedColumn(),
                        TimeRemainingColumn(),
                        console=console
                    ) as progress:
                        task = progress.add_task("Downloading...", total=total_size)

                        # Download and save file
                        with open(download_target, 'wb') as f:
                            downloaded = 0
                            for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                                f.write(chunk)
                                downloaded += len(chunk)
                                progress.update(task, completed=downloaded)

            # If we used temp file, copy to final destination
            if use_temp and temp_file and temp_file.exists():
                console.print(f"[dim]Copying to Windows filesystem...[/dim]")
                shutil.copy2(temp_file, output_file)
        finally:
            # Clean up temp file
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass

        # Verify download
        if output_file.exists():
            actual_size = output_file.stat().st_size
            if actual_size == file_info['size']:
                console.print(f"[green]✅ Download complete![/green] Saved to {output_file.absolute()}")
                console.print(f"[green]📁 File size:[/green] {actual_size:,} bytes")
            else:
                console.print(f"[red]❌ Download incomplete! Expected {file_info['size']:,} bytes, got {actual_size:,} bytes[/red]")
                raise typer.Exit(1)
        else:
            console.print("[red]❌ Download failed - file not saved[/red]")
            raise typer.Exit(1)

    except httpx.TimeoutException:
        console.print("[red]❌ Download timeout (2 hour limit reached)[/red]")
        console.print("[yellow]💡 Check network connection or try again[/yellow]")
        raise typer.Exit(1)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            console.print(f"[red]❌ File with ID {file_id} not found[/red]")
        else:
            console.print(f"[red]❌ Server error: {e.response.status_code} {e.response.text}[/red]")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Download interrupted by user.[/yellow]")
        # Clean up partial file if it exists
        if 'output_file' in locals() and output_file.exists():
            output_file.unlink()
            console.print(f"[yellow]Cleaned up partial file: {output_file}[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]❌ Download failed: {str(e)}[/red]")
        raise typer.Exit(1)
