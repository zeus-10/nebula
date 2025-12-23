"""
Benchmark command - integrates the benchmark script into the CLI
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional
from rich.console import Console

console = Console()


def run_benchmark(
    file_path: str,
    server_url: Optional[str] = None,
    output: Optional[str] = None,
    verbose: bool = False,
    skip_transcode: bool = False
):
    """
    Run the Nebula performance benchmark

    Args:
        file_path: Path to video file to benchmark
        server_url: Nebula server URL (optional, uses env var)
        output: Path to save JSON results (optional)
        verbose: Enable verbose logging
        skip_transcode: Skip transcoding benchmark (faster)
    """
    # Get the benchmark script path (from nebula root directory)
    benchmark_script = Path(__file__).parent.parent.parent.parent.parent / "benchmark.py"

    if not benchmark_script.exists():
        console.print(f"[red]❌ Benchmark script not found: {benchmark_script}[/red]")
        console.print("[yellow]💡 Make sure benchmark.py is in the nebula root directory[/yellow]")
        sys.exit(1)

    # Build command arguments
    cmd = [sys.executable, str(benchmark_script), file_path]

    # Add server URL if provided
    if server_url:
        cmd.extend(["--server", server_url])

    # Add output file if provided
    if output:
        cmd.extend(["--output", output])

    # Add verbose flag if requested
    if verbose:
        cmd.append("--verbose")

    # Add skip-transcode flag if requested
    if skip_transcode:
        cmd.append("--skip-transcode")

    console.print(f"[blue]🚀 Running benchmark on: {file_path}[/blue]")
    if server_url:
        console.print(f"[blue]🔗 Server: {server_url}[/blue]")
    else:
        console.print(f"[blue]🔗 Server: {os.getenv('NEBULA_SERVER_URL', 'http://localhost:8000')} (from env)[/blue]")

    if output:
        console.print(f"[blue]💾 Results will be saved to: {output}[/blue]")

    console.print()

    try:
        # Run the benchmark script
        result = subprocess.run(cmd, cwd=benchmark_script.parent)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Benchmark interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]❌ Failed to run benchmark: {e}[/red]")
        sys.exit(1)
