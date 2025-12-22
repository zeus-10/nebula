# Download command - download files from server

import os
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
    server_url: str = typer.Option(..., envvar="NEBULA_SERVER_URL")
):
    """
    Download a file from Nebula Cloud by its ID.

    Preserves the original filename if no output path is specified.
    """
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
            default_dir = Path("/mnt/c/Users/abhin/OneDrive/Desktop/nebula")
            default_dir.mkdir(parents=True, exist_ok=True)
            output_file = default_dir / file_info['filename']

        # Check if output file already exists
        if output_file.exists():
            console.print(f"[yellow]⚠️  File '{output_file}' already exists. Overwrite? (y/N): [/yellow]", end="")
            response = input().strip().lower()
            if response != 'y' and response != 'yes':
                console.print("[yellow]Download cancelled.[/yellow]")
                return

        # Download with progress tracking
        console.print(f"[yellow]🚀 Downloading to {output_file.absolute()}...[/yellow]")

        with httpx.Client(timeout=7200.0) as client:  # 2 hour timeout for large files
            with client.stream(
                'GET',
                f"{server_url}/api/files/{file_id}/download"
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
                    with open(output_file, 'wb') as f:
                        downloaded = 0
                        for chunk in response.iter_bytes(chunk_size=8192):
                            f.write(chunk)
                            downloaded += len(chunk)
                            progress.update(task, completed=downloaded)

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
