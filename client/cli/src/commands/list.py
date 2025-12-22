# List command - display all uploaded files

import typer
from typing import Optional
import httpx
from rich.console import Console
from rich.table import Table

console = Console()

def list_files(
    server_url: str = typer.Option(..., envvar="NEBULA_SERVER_URL"),
    limit: int = typer.Option(50, help="Maximum number of files to display"),
    skip: int = typer.Option(0, help="Number of files to skip")
):
    """
    List all uploaded files with metadata.
    """
    console.print(f"[yellow]📋 Fetching file list from {server_url}...[/yellow]")

    try:
        # Fetch file list from server
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                f"{server_url}/api/files",
                params={"limit": limit, "skip": skip}
            )
            response.raise_for_status()

        result = response.json()
        files = result.get('files', [])

        if not files:
            console.print("[yellow]📂 No files found.[/yellow]")
            return

        # Create a rich table to display files
        table = Table(title="📁 Uploaded Files")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Filename", style="green")
        table.add_column("Size", style="magenta", justify="right")
        table.add_column("Type", style="blue")
        table.add_column("Uploaded", style="yellow")
        table.add_column("Description", style="white")

        for file in files:
            # Format file size
            size_bytes = file['size']
            if size_bytes < 1024:
                size_str = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            elif size_bytes < 1024 * 1024 * 1024:
                size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

            # Format upload date (remove time part for display)
            upload_date = file['upload_date'][:10] if file['upload_date'] else "Unknown"

            # Get file extension/type info
            mime_type = file['mime_type']
            if mime_type.startswith('video/'):
                type_icon = "🎬"
            elif mime_type.startswith('image/'):
                type_icon = "🖼️"
            elif mime_type.startswith('audio/'):
                type_icon = "🎵"
            else:
                type_icon = "📄"

            table.add_row(
                str(file['id']),
                file['filename'],
                size_str,
                f"{type_icon} {mime_type}",
                upload_date,
                file['description'] or ""
            )

        console.print(table)
        total_count = result.get('count', len(files))
        console.print(f"[green]✅ Found {len(files)} files (total: {total_count})[/green]")

    except httpx.TimeoutException:
        console.print("[red]❌ Request timeout - server may be slow or unreachable[/red]")
        raise typer.Exit(1)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            console.print("[red]❌ Files API not found - server may not support file listing[/red]")
        else:
            console.print(f"[red]❌ Server error: {e.response.status_code} {e.response.text}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]❌ Failed to list files: {str(e)}[/red]")
        raise typer.Exit(1)
