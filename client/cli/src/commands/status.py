# Status command - show detailed system health and specs

import typer
import httpx
import psutil
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
import platform
import os
from datetime import datetime

console = Console()

def get_system_specs():
    """Get local system specifications"""
    try:
        # CPU info
        cpu_count = psutil.cpu_count()
        cpu_percent = psutil.cpu_percent(interval=1)

        # Memory info
        memory = psutil.virtual_memory()
        memory_total = memory.total
        memory_used = memory.used
        memory_percent = memory.percent

        # Disk info
        disk = psutil.disk_usage('/')
        disk_total = disk.total
        disk_used = disk.used
        disk_percent = disk.percent

        # Network info (basic)
        net = psutil.net_io_counters()
        bytes_sent = net.bytes_sent
        bytes_recv = net.bytes_recv

        return {
            "cpu": {
                "cores": cpu_count,
                "usage": cpu_percent
            },
            "memory": {
                "total": memory_total,
                "used": memory_used,
                "percent": memory_percent
            },
            "disk": {
                "total": disk_total,
                "used": disk_used,
                "percent": disk_percent
            },
            "network": {
                "sent": bytes_sent,
                "received": bytes_recv
            }
        }
    except Exception as e:
        return {"error": f"Failed to get system specs: {str(e)}"}

def format_bytes(bytes_value):
    """Format bytes to human readable format"""
    if bytes_value < 1024:
        return f"{bytes_value} B"
    elif bytes_value < 1024 * 1024:
        return f"{bytes_value / 1024:.1f} KB"
    elif bytes_value < 1024 * 1024 * 1024:
        return f"{bytes_value / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_value / (1024 * 1024 * 1024):.1f} GB"

def show_system_health(
    server_url: str = typer.Option(..., envvar="NEBULA_SERVER_URL"),
    show_local: bool = typer.Option(True, help="Show local system specs"),
    show_server: bool = typer.Option(True, help="Show server health status")
):
    """
    Display detailed system health and specifications.

    Shows both local system specs and remote server health status.
    """
    console.print("[bold blue]🔍 Nebula System Health Report[/bold blue]")
    console.print(f"[dim]Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]")
    console.print()

    # Local System Specs
    if show_local:
        console.print("[bold green]💻 Local System[/bold green]")
        specs = get_system_specs()

        if "error" in specs:
            console.print(f"[red]❌ {specs['error']}[/red]")
        else:
            # CPU Table
            cpu_table = Table(title="🎯 CPU", show_header=False, box=None)
            cpu_table.add_row("Cores", f"{specs['cpu']['cores']}")
            cpu_table.add_row("Usage", f"{specs['cpu']['usage']:.1f}%")
            console.print(cpu_table)

            # Memory Table
            mem_table = Table(title="🧠 Memory", show_header=False, box=None)
            mem_table.add_row("Total", format_bytes(specs['memory']['total']))
            mem_table.add_row("Used", format_bytes(specs['memory']['used']))
            mem_table.add_row("Usage", f"{specs['memory']['percent']:.1f}%")
            console.print(mem_table)

            # Disk Table
            disk_table = Table(title="💾 Storage", show_header=False, box=None)
            disk_table.add_row("Total", format_bytes(specs['disk']['total']))
            disk_table.add_row("Used", format_bytes(specs['disk']['used']))
            disk_table.add_row("Usage", f"{specs['disk']['percent']:.1f}%")
            console.print(disk_table)

            # Network Table
            net_table = Table(title="🌐 Network", show_header=False, box=None)
            net_table.add_row("Sent", format_bytes(specs['network']['sent']))
            net_table.add_row("Received", format_bytes(specs['network']['received']))
            console.print(net_table)

        console.print()

    # Server Health
    if show_server:
        console.print(f"[bold cyan]☁️  Server Health ({server_url})[/bold cyan]")

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{server_url}/health")
                response.raise_for_status()
                health_data = response.json()

            # Server Status Table
            server_table = Table(title="🚀 Server Status", show_header=False, box=None)

            # Status indicator
            status = health_data.get('status', 'unknown')
            if status == 'healthy':
                status_display = "[green]✅ Healthy[/green]"
            elif status == 'degraded':
                status_display = "[yellow]⚠️  Degraded[/yellow]"
            else:
                status_display = "[red]❌ Unhealthy[/red]"

            server_table.add_row("Status", status_display)

            # Database
            db_status = health_data.get('database', 'unknown')
            if db_status == 'configured':
                db_display = "[green]✅ Configured[/green]"
            else:
                db_display = "[red]❌ Missing[/red]"
            server_table.add_row("Database", db_display)

            # Battery
            battery = health_data.get('battery', 'unknown')
            if battery != 'unknown':
                try:
                    battery_pct = int(battery.rstrip('%'))
                    if battery_pct > 80:
                        battery_display = f"[green]🔋 {battery}[/green]"
                    elif battery_pct > 20:
                        battery_display = f"[yellow]🔋 {battery}[/yellow]"
                    else:
                        battery_display = f"[red]🔋 {battery}[/red]"
                except:
                    battery_display = f"🔋 {battery}"
            else:
                battery_display = "[dim]🔋 Not available[/dim]"
            server_table.add_row("Battery", battery_display)

            # Worker
            worker = health_data.get('worker', 'unknown')
            if worker == 'ready':
                worker_display = "[green]✅ Ready[/green]"
            else:
                worker_display = "[red]❌ Not ready[/red]"
            server_table.add_row("Worker", worker_display)

            console.print(server_table)

            # Additional server info if available
            if 'uptime' in health_data:
                console.print(f"Uptime: {health_data['uptime']}")

        except httpx.TimeoutException:
            console.print("[red]❌ Server timeout - may be unreachable[/red]")
        except httpx.HTTPStatusError as e:
            console.print(f"[red]❌ Server error: {e.response.status_code}[/red]")
        except Exception as e:
            console.print(f"[red]❌ Failed to get server health: {str(e)}[/red]")

    # Summary
    console.print()
    console.print("[dim]💡 Tip: Use 'nebula ping' for quick connectivity check[/dim]")
