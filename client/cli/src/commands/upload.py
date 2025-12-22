# Upload command - streams files to server with progress tracking

import os
import typer
from pathlib import Path
from typing import Optional
import httpx
from rich.console import Console
from rich.progress import Progress, BarColumn, FileSizeColumn, TimeRemainingColumn, TransferSpeedColumn

console = Console()

def upload_file(
    file_path: str,
    server_url: str = typer.Option(..., envvar="NEBULA_SERVER_URL"),
    description: Optional[str] = None
):
    """
    Upload a file to Nebula Cloud

    FILE_PATH: Path to the file to upload
    """

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

    console.print(f"[blue]📤 Uploading:[/blue] {filename}")
    console.print(f"[blue]📊 Size:[/blue] {file_size:,} bytes")
    if description:
        console.print(f"[blue]📝 Description:[/blue] {description}")

    try:
        # Upload with progress tracking
        with Progress(
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.0f}%",
            FileSizeColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console
        ) as progress:

            task = progress.add_task("Uploading...", total=file_size)

            with open(file_path, 'rb') as f:
                # Prepare multipart form data
                files = {'file': (filename, f, 'application/octet-stream')}
                data = {}
                if description:
                    data['description'] = description

                # Upload using httpx for better streaming
                with httpx.Client(timeout=300.0) as client:  # 5 minute timeout
                    with client.stream(
                        'POST',
                        f"{server_url}/api/upload",
                        files=files,
                        data=data
                    ) as response:
                        response.raise_for_status()

                        # Read response (though we don't need to track upload progress
                        # since we're streaming from file)
                        result = response.json()

                        # Mark progress as complete
                        progress.update(task, completed=file_size)

        # Display success
        file_info = result['file']
        console.print(f"[green]✅ Upload successful![/green]")
        console.print(f"[green]📄 File ID:[/green] {file_info['id']}")
        console.print(f"[green]📁 Path:[/green] {file_info['file_path']}")
        console.print(f"[green]🕒 Uploaded:[/green] {file_info['upload_date']}")

    except httpx.TimeoutException:
        console.print("[red]❌ Upload timeout - file too large or network slow[/red]")
        raise typer.Exit(1)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 413:
            console.print("[red]❌ File too large for server[/red]")
        else:
            console.print(f"[red]❌ Upload failed: {e.response.status_code} {e.response.text}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]❌ Upload failed: {str(e)}[/red]")
        raise typer.Exit(1)
