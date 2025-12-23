# Transcode command - trigger video transcoding and check status

import os
import requests
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel
from typing import List, Optional
import time

console = Console()
SERVER_URL = os.getenv("NEBULA_SERVER_URL")


def transcode_file(file_id: int, qualities: Optional[List[int]] = None):
    """
    Trigger transcoding for a video file

    Args:
        file_id: ID of the file to transcode
        qualities: List of target qualities (480, 720, 1080). Defaults to [480, 720]
    """
    if not SERVER_URL:
        console.print("[red]Error: NEBULA_SERVER_URL environment variable not set[/red]")
        return

    if qualities is None:
        qualities = [480, 720]

    console.print(f"[cyan]Requesting transcoding for file {file_id}...[/cyan]")
    console.print(f"[dim]Target qualities: {', '.join([f'{q}p' for q in qualities])}[/dim]")

    try:
        response = requests.post(
            f"{SERVER_URL}/api/transcode",
            json={"file_id": file_id, "qualities": qualities},
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()

            if "jobs" in data and data["jobs"]:
                console.print(f"\n[green]Transcoding started![/green]")
                console.print(f"[dim]{data.get('message', '')}[/dim]\n")

                table = Table(title="Queued Jobs")
                table.add_column("Job ID", style="cyan")
                table.add_column("Quality", style="magenta")
                table.add_column("Status", style="yellow")

                for job in data["jobs"]:
                    table.add_row(
                        str(job["job_id"]),
                        f"{job['quality']}p",
                        job["status"]
                    )

                console.print(table)
                console.print(f"\n[dim]Use 'nebula transcode-status {file_id}' to check progress[/dim]")
            else:
                console.print(f"\n[yellow]{data.get('message', 'No jobs created')}[/yellow]")
                if data.get("transcoded_qualities"):
                    console.print(f"[dim]Already transcoded: {', '.join([f'{q}p' for q in data['transcoded_qualities']])}[/dim]")

        elif response.status_code == 404:
            console.print(f"[red]Error: File {file_id} not found[/red]")
        elif response.status_code == 400:
            error = response.json().get("detail", "Bad request")
            console.print(f"[red]Error: {error}[/red]")
        else:
            console.print(f"[red]Error: Server returned {response.status_code}[/red]")
            console.print(f"[dim]{response.text}[/dim]")

    except requests.exceptions.Timeout:
        console.print("[red]Error: Request timed out[/red]")
    except requests.exceptions.ConnectionError:
        console.print(f"[red]Error: Cannot connect to server at {SERVER_URL}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def get_transcode_status(file_id: int, watch: bool = False):
    """
    Get transcoding status for a file

    Args:
        file_id: ID of the file to check
        watch: If True, continuously poll for updates
    """
    if not SERVER_URL:
        console.print("[red]Error: NEBULA_SERVER_URL environment variable not set[/red]")
        return

    def fetch_and_display():
        try:
            response = requests.get(
                f"{SERVER_URL}/api/transcode/{file_id}",
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()

                # File info panel
                file_info = f"""
[bold]{data['filename']}[/bold]
Original size: {format_size(data['original_size'])}
Is video: {'Yes' if data['is_video'] else 'No'}
Available qualities: {', '.join([f"{q}p" for q in data['available_qualities']]) if data['available_qualities'] else 'None'}
                """.strip()
                console.print(Panel(file_info, title=f"File #{file_id}"))

                if not data["jobs"]:
                    console.print("[dim]No transcoding jobs found for this file[/dim]")
                    return False  # No active jobs

                # Jobs table
                table = Table(title="Transcoding Jobs")
                table.add_column("Job ID", style="cyan")
                table.add_column("Quality", style="magenta")
                table.add_column("Status", style="bold")
                table.add_column("Progress", justify="right")
                table.add_column("Output Size", justify="right")
                table.add_column("Error", style="red")

                has_active_jobs = False
                for job in data["jobs"]:
                    status = job["status"]
                    if status == "completed":
                        status_style = "[green]completed[/green]"
                    elif status == "processing":
                        status_style = "[yellow]processing[/yellow]"
                        has_active_jobs = True
                    elif status == "pending":
                        status_style = "[blue]pending[/blue]"
                        has_active_jobs = True
                    elif status == "failed":
                        status_style = "[red]failed[/red]"
                    else:
                        status_style = f"[dim]{status}[/dim]"

                    progress = f"{job['progress']:.1f}%" if job['progress'] else "0%"
                    output_size = format_size(job['output_size']) if job['output_size'] else "-"
                    error = (job['error_message'][:30] + "...") if job.get('error_message') and len(job['error_message']) > 30 else (job.get('error_message') or "-")

                    table.add_row(
                        str(job["id"]),
                        f"{job['target_quality']}p",
                        status_style,
                        progress,
                        output_size,
                        error
                    )

                console.print(table)
                return has_active_jobs

            elif response.status_code == 404:
                console.print(f"[red]Error: File {file_id} not found[/red]")
                return False
            else:
                console.print(f"[red]Error: Server returned {response.status_code}[/red]")
                return False

        except requests.exceptions.Timeout:
            console.print("[red]Error: Request timed out[/red]")
            return False
        except requests.exceptions.ConnectionError:
            console.print(f"[red]Error: Cannot connect to server at {SERVER_URL}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            return False

    if watch:
        console.print("[dim]Watching for updates... Press Ctrl+C to stop[/dim]\n")
        try:
            while True:
                console.clear()
                has_active = fetch_and_display()
                if not has_active:
                    console.print("\n[green]All jobs completed![/green]")
                    break
                console.print("\n[dim]Refreshing in 5 seconds...[/dim]")
                time.sleep(5)
        except KeyboardInterrupt:
            console.print("\n[dim]Stopped watching[/dim]")
    else:
        fetch_and_display()


def list_transcode_jobs(status: Optional[str] = None, limit: int = 20):
    """
    List all transcoding jobs

    Args:
        status: Filter by status (pending, processing, completed, failed)
        limit: Maximum number of jobs to display
    """
    if not SERVER_URL:
        console.print("[red]Error: NEBULA_SERVER_URL environment variable not set[/red]")
        return

    try:
        params = {"limit": limit}
        if status:
            params["status"] = status

        response = requests.get(
            f"{SERVER_URL}/api/transcode/jobs/all",
            params=params,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()

            if not data["jobs"]:
                console.print("[dim]No transcoding jobs found[/dim]")
                return

            table = Table(title=f"Transcoding Jobs ({data['total']} total)")
            table.add_column("Job ID", style="cyan")
            table.add_column("File ID", style="dim")
            table.add_column("Filename")
            table.add_column("Quality", style="magenta")
            table.add_column("Status", style="bold")
            table.add_column("Progress", justify="right")

            for job in data["jobs"]:
                status_val = job["status"]
                if status_val == "completed":
                    status_style = "[green]completed[/green]"
                elif status_val == "processing":
                    status_style = "[yellow]processing[/yellow]"
                elif status_val == "pending":
                    status_style = "[blue]pending[/blue]"
                elif status_val == "failed":
                    status_style = "[red]failed[/red]"
                else:
                    status_style = f"[dim]{status_val}[/dim]"

                progress = f"{job['progress']:.1f}%" if job.get('progress') else "0%"
                filename = job['filename'][:25] + "..." if len(job['filename']) > 25 else job['filename']

                table.add_row(
                    str(job["job_id"]),
                    str(job["file_id"]),
                    filename,
                    f"{job['target_quality']}p",
                    status_style,
                    progress
                )

            console.print(table)

        else:
            console.print(f"[red]Error: Server returned {response.status_code}[/red]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def cancel_transcode_job(job_id: int):
    """
    Cancel a transcoding job

    Args:
        job_id: ID of the job to cancel
    """
    if not SERVER_URL:
        console.print("[red]Error: NEBULA_SERVER_URL environment variable not set[/red]")
        return

    try:
        response = requests.delete(
            f"{SERVER_URL}/api/transcode/job/{job_id}",
            timeout=10
        )

        if response.status_code == 200:
            console.print(f"[green]Job {job_id} cancelled successfully[/green]")
        elif response.status_code == 404:
            console.print(f"[red]Error: Job {job_id} not found[/red]")
        elif response.status_code == 400:
            error = response.json().get("detail", "Cannot cancel job")
            console.print(f"[yellow]{error}[/yellow]")
        else:
            console.print(f"[red]Error: Server returned {response.status_code}[/red]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def format_size(size_bytes: int) -> str:
    """Format bytes to human readable size"""
    if size_bytes is None:
        return "-"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"



