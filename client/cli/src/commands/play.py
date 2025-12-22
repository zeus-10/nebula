# Play command - stream video files to VLC/mpv

import os
import typer
import subprocess
import shutil
from typing import Optional
from rich.console import Console

console = Console()


def play_file(
    file_id: int,
    player: Optional[str] = None,
    server_url: Optional[str] = None
):
    """
    Stream a video file from Nebula Cloud to a local media player.
    
    Automatically detects VLC or mpv. Supports seeking/scrubbing.
    """
    # Load server URL from environment if not provided
    if not server_url:
        server_url = os.getenv("NEBULA_SERVER_URL")
        if not server_url:
            console.print("[red]❌ Error: NEBULA_SERVER_URL environment variable not set[/red]")
            raise typer.Exit(1)

    # Build the stream URL
    stream_url = f"{server_url}/api/files/{file_id}/stream"
    
    console.print(f"[blue]🎬 Streaming file ID {file_id}...[/blue]")
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
            console.print("[red]❌ No media player found![/red]")
            console.print("[yellow]Install VLC or mpv, or specify with --player[/yellow]")
            console.print(f"\n[dim]Manual playback: Open this URL in your browser or player:[/dim]")
            console.print(f"[cyan]{stream_url}[/cyan]")
            raise typer.Exit(1)

    console.print(f"[green]▶️  Opening in {player_cmd}...[/green]")
    
    try:
        # Launch the media player with the stream URL
        if "vlc.exe" in player_cmd:
            # Windows VLC needs special handling from WSL
            subprocess.Popen(
                [player_cmd, stream_url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            # Linux VLC/mpv
            subprocess.Popen(
                [player_cmd, stream_url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        
        console.print(f"[green]✅ Player launched! Streaming file ID {file_id}[/green]")
        console.print(f"[dim]Tip: You can seek/scrub through the video[/dim]")
        
    except FileNotFoundError:
        console.print(f"[red]❌ Player not found: {player_cmd}[/red]")
        console.print(f"\n[dim]Manual playback URL:[/dim]")
        console.print(f"[cyan]{stream_url}[/cyan]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]❌ Failed to launch player: {str(e)}[/red]")
        console.print(f"\n[dim]Manual playback URL:[/dim]")
        console.print(f"[cyan]{stream_url}[/cyan]")
        raise typer.Exit(1)

