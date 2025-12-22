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
    server_url: Optional[str] = None,
    description: Optional[str] = None
):
    """
    Upload a file to Nebula Cloud

    FILE_PATH: Path to the file to upload
    """
    # #region agent log - Function entry with parameters
    import json
    import time
    log_data = {
        "sessionId": "debug-upload-issue",
        "runId": "hypothesis-test",
        "hypothesisId": "A",
        "location": "upload.py:upload_file_entry",
        "message": "Upload function called",
        "data": {
            "file_path": file_path,
            "server_url_provided": server_url is not None,
            "description_provided": description is not None,
            "file_exists": os.path.exists(file_path) if file_path else False,
            "file_size": os.path.getsize(file_path) if file_path and os.path.exists(file_path) else 0
        },
        "timestamp": int(time.time() * 1000)
    }
    with open("/home/abhinav/nebula/.cursor/debug.log", "a") as f:
        f.write(json.dumps(log_data) + "\n")
    # #endregion

    # Load server URL from environment if not provided
    if not server_url:
        server_url = os.getenv("NEBULA_SERVER_URL")

        # #region agent log - Environment variable loading
        log_data = {
            "sessionId": "debug-upload-issue",
            "runId": "hypothesis-test",
            "hypothesisId": "B",
            "location": "upload.py:env_loading",
            "message": "Environment variable loading",
            "data": {
                "server_url_loaded": server_url is not None,
                "server_url_value": server_url[:50] + "..." if server_url and len(server_url) > 50 else server_url
            },
            "timestamp": int(time.time() * 1000)
        }
        with open("/home/abhinav/nebula/.cursor/debug.log", "a") as f:
            f.write(json.dumps(log_data) + "\n")
        # #endregion

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

    # #region agent log - Before HTTP request
    log_data = {
        "sessionId": "debug-upload-issue",
        "runId": "hypothesis-test",
        "hypothesisId": "C",
        "location": "upload.py:before_http",
        "message": "About to make HTTP request",
        "data": {
            "server_url": server_url,
            "file_size": file_size,
            "filename": filename,
            "content_type": files['file'][2] if len(files['file']) > 2 else None,
            "description_in_data": 'description' in data
        },
        "timestamp": int(time.time() * 1000)
    }
    with open("/home/abhinav/nebula/.cursor/debug.log", "a") as f:
        f.write(json.dumps(log_data) + "\n")
    # #endregion

    with httpx.Client(timeout=600.0) as client:  # 10 minute timeout for large files
        # Use explicit headers to avoid streaming issues
        headers = {"Accept": "application/json"}
        response = client.post(
            f"{server_url}/api/upload",
            files=files,
            data=data,
            headers=headers
        )

        # #region agent log - After HTTP request
        log_data = {
            "sessionId": "debug-upload-issue",
            "runId": "hypothesis-test",
            "hypothesisId": "D",
            "location": "upload.py:after_http",
            "message": "HTTP request completed",
            "data": {
                "status_code": response.status_code,
                "response_headers": dict(response.headers),
                "response_size": len(response.text) if response.text else 0
            },
            "timestamp": int(time.time() * 1000)
        }
        with open("/home/abhinav/nebula/.cursor/debug.log", "a") as f:
            f.write(json.dumps(log_data) + "\n")
        # #endregion

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

    except httpx.TimeoutException as e:
        # #region agent log - Timeout exception
        log_data = {
            "sessionId": "debug-upload-issue",
            "runId": "hypothesis-test",
            "hypothesisId": "E",
            "location": "upload.py:timeout_exception",
            "message": "Timeout exception occurred",
            "data": {
                "exception_type": "TimeoutException",
                "exception_message": str(e),
                "timeout_seconds": 600
            },
            "timestamp": int(time.time() * 1000)
        }
        with open("/home/abhinav/nebula/.cursor/debug.log", "a") as f:
            f.write(json.dumps(log_data) + "\n")
        # #endregion

        console.print("[red]❌ Upload timeout - file too large or network slow[/red]")
        console.print(f"[red]🔍 Timeout after 600 seconds (10 minutes)[/red]")
        raise typer.Exit(1)
    except httpx.HTTPStatusError as e:
        # #region agent log - HTTP status error
        log_data = {
            "sessionId": "debug-upload-issue",
            "runId": "hypothesis-test",
            "hypothesisId": "F",
            "location": "upload.py:http_status_error",
            "message": "HTTP status error occurred",
            "data": {
                "status_code": e.response.status_code,
                "response_text": e.response.text[:200] if e.response.text else None,
                "response_headers": dict(e.response.headers) if e.response else None
            },
            "timestamp": int(time.time() * 1000)
        }
        with open("/home/abhinav/nebula/.cursor/debug.log", "a") as f:
            f.write(json.dumps(log_data) + "\n")
        # #endregion

        if e.response.status_code == 413:
            console.print("[red]❌ File too large for server[/red]")
        else:
            console.print(f"[red]❌ Upload failed: {e.response.status_code} {e.response.text}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        # #region agent log - General exception
        log_data = {
            "sessionId": "debug-upload-issue",
            "runId": "hypothesis-test",
            "hypothesisId": "G",
            "location": "upload.py:general_exception",
            "message": "General exception occurred",
            "data": {
                "exception_type": type(e).__name__,
                "exception_message": str(e)
            },
            "timestamp": int(time.time() * 1000)
        }
        with open("/home/abhinav/nebula/.cursor/debug.log", "a") as f:
            f.write(json.dumps(log_data) + "\n")
        # #endregion

        console.print(f"[red]❌ Upload failed: {str(e)}[/red]")
        raise typer.Exit(1)
