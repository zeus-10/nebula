# Upload command - uploads files to server

import os
import typer
from pathlib import Path
from typing import Optional
import httpx
from rich.console import Console

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

    console.print(f"[yellow]🔗 Server URL: {server_url}/api/upload[/yellow]")

    try:
            with open(file_path, 'rb') as f:
                # Prepare multipart form data
                files = {'file': (filename, f, 'application/octet-stream')}
                data = {}
                if description:
                    data['description'] = description

                # Upload using httpx (modern async HTTP client)
                console.print(f"[yellow]📡 Uploading {file_size:,} bytes to server...[/yellow]")
                console.print(f"[blue]⏳ Please wait, this may take a few minutes for large files...[/blue]")

                with httpx.Client(timeout=600.0) as client:  # 10 minute timeout for large files
                    # Use explicit headers to avoid streaming issues
                    headers = {"Accept": "application/json"}
                    response = client.post(
                        f"{server_url}/api/upload",
                        files=files,
                        data=data,
                        headers=headers
                    )

                    console.print(f"[yellow]📡 Server responded with status: {response.status_code}[/yellow]")

                    response.raise_for_status()

                    # Parse response
                    result = response.json()

        # Display success
        file_info = result['file']
        console.print(f"[green]✅ Upload successful![/green]")
        console.print(f"[green]📄 File ID:[/green] {file_info['id']}")
        console.print(f"[green]📁 Path:[/green] {file_info['file_path']}")
        console.print(f"[green]🕒 Uploaded:[/green] {file_info['upload_date']}")

    except httpx.TimeoutException:
        console.print("[red]❌ Upload timeout - file too large or network slow[/red]")
        console.print(f"[red]🔍 Timeout after 600 seconds (10 minutes)[/red]")
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
