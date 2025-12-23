# Play command - stream video files to VLC/mpv

import os
import typer
import subprocess
import shutil
import requests
from typing import Optional
from rich.console import Console

console = Console()


def play_file(
    file_id: int,
    player: Optional[str] = None,
    quality: Optional[int] = None,
    server_url: Optional[str] = None
):
    """
    Stream a video file from Nebula Cloud to a local media player.
    
    Automatically detects VLC or mpv. Supports seeking/scrubbing.
    If quality is specified, streams the transcoded version.
    """
    # Load server URL from environment if not provided
    if not server_url:
        server_url = os.getenv("NEBULA_SERVER_URL")
        if not server_url:
            console.print("[red]Error: NEBULA_SERVER_URL environment variable not set[/red]")
            raise typer.Exit(1)

    # If quality specified, check if transcoded version exists
    stream_url = f"{server_url}/api/files/{file_id}/stream"
    
    if quality:
        console.print(f"[dim]Checking for {quality}p transcoded version...[/dim]")
        try:
            # Check transcoding status
            response = requests.get(f"{server_url}/api/transcode/{file_id}", timeout=5)
            if response.status_code == 200:
                data = response.json()
                available = data.get("available_qualities", [])
                
                if quality in available:
                    # Use transcoded stream
                    stream_url = f"{server_url}/api/files/{file_id}/stream?quality={quality}"
                    console.print(f"[green]Using {quality}p transcoded version[/green]")
                else:
                    console.print(f"[yellow]Warning: {quality}p version not available[/yellow]")
                    if available:
                        console.print(f"[dim]Available qualities: {', '.join([f'{q}p' for q in available])}[/dim]")
                    else:
                        console.print(f"[dim]No transcoded versions available. Use 'nebula transcode {file_id}' first.[/dim]")
                    console.print(f"[dim]Falling back to original quality...[/dim]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not check transcoding status: {e}[/yellow]")
            console.print(f"[dim]Falling back to original quality...[/dim]")

    console.print(f"[blue]Streaming file ID {file_id}...[/blue]")
    console.print(f"[dim]URL: {stream_url}[/dim]")

    # Detect available media player
    if player:
        player_cmd = player
    else:
        # Try to find a media player
        if shutil.which("vlc"):
            player_cmd = "vlc"
        elif shutil.which("mpv"):
            player_cmd = "mpv"
        elif shutil.which("cvlc"):  # VLC command-line on Linux
            player_cmd = "cvlc"
        elif os.path.exists("/mnt/c/Program Files/VideoLAN/VLC/vlc.exe"):
            # Windows VLC via WSL
            player_cmd = "/mnt/c/Program Files/VideoLAN/VLC/vlc.exe"
        elif os.path.exists("/mnt/c/Program Files (x86)/VideoLAN/VLC/vlc.exe"):
            player_cmd = "/mnt/c/Program Files (x86)/VideoLAN/VLC/vlc.exe"
        else:
            console.print("[red]No media player found![/red]")
            console.print("[yellow]Install VLC or mpv, or specify with --player[/yellow]")
            console.print(f"\n[dim]Manual playback: Open this URL in your browser or player:[/dim]")
            console.print(f"[cyan]{stream_url}[/cyan]")
            raise typer.Exit(1)

    console.print(f"[green]Opening in {player_cmd}...[/green]")
    
    try:
        # Launch the media player with the stream URL
        subprocess.Popen(
            [player_cmd, stream_url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        console.print(f"[green]Player launched! Streaming file ID {file_id}[/green]")
        console.print(f"[dim]Tip: You can seek/scrub through the video[/dim]")
        
    except FileNotFoundError:
        console.print(f"[red]Player not found: {player_cmd}[/red]")
        console.print(f"\n[dim]Manual playback URL:[/dim]")
        console.print(f"[cyan]{stream_url}[/cyan]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Failed to launch player: {str(e)}[/red]")
        console.print(f"\n[dim]Manual playback URL:[/dim]")
        console.print(f"[cyan]{stream_url}[/cyan]")
        raise typer.Exit(1)
