# System commands - logs, restart, container status

import os
import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from typing import Optional

console = Console()
SERVER_URL = os.getenv("NEBULA_SERVER_URL")

VALID_SERVICES = ["api", "worker", "db", "s3", "queue"]


def show_logs(service: Optional[str] = None, lines: int = 100):
    """
    Show logs for a service or all services.
    
    Args:
        service: Service name (api, worker, db, s3, queue) or None for all
        lines: Number of log lines to fetch
    """
    if not SERVER_URL:
        console.print("[red]Error: NEBULA_SERVER_URL environment variable not set[/red]")
        return

    try:
        if service:
            # Single service logs
            if service not in VALID_SERVICES:
                console.print(f"[red]Invalid service: {service}[/red]")
                console.print(f"[dim]Valid services: {', '.join(VALID_SERVICES)}[/dim]")
                return
            
            console.print(f"[cyan]Fetching logs for {service}...[/cyan]")
            response = requests.get(
                f"{SERVER_URL}/api/system/logs/{service}",
                params={"lines": lines},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                console.print(Panel(
                    data["logs"] if data["logs"] else "[dim]No logs available[/dim]",
                    title=f"[bold]{service}[/bold] ({data['container']}) - Last {lines} lines",
                    border_style="blue"
                ))
            else:
                console.print(f"[red]Error: {response.json().get('detail', 'Unknown error')}[/red]")
        else:
            # All services logs
            console.print(f"[cyan]Fetching logs for all services...[/cyan]")
            response = requests.get(
                f"{SERVER_URL}/api/system/logs",
                params={"lines": min(lines, 50)},  # Limit per service when fetching all
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                for svc, logs in data["logs"].items():
                    console.print(Panel(
                        logs if logs else "[dim]No logs available[/dim]",
                        title=f"[bold]{svc}[/bold]",
                        border_style="blue"
                    ))
                    console.print()
            else:
                console.print(f"[red]Error: {response.json().get('detail', 'Unknown error')}[/red]")

    except requests.exceptions.Timeout:
        console.print("[red]Error: Request timed out[/red]")
    except requests.exceptions.ConnectionError:
        console.print(f"[red]Error: Cannot connect to server at {SERVER_URL}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def restart_service(service: Optional[str] = None, force: bool = False):
    """
    Restart a service or all services.
    
    Args:
        service: Service name (api, worker, db, s3, queue) or None for all
        force: Skip confirmation prompt
    """
    if not SERVER_URL:
        console.print("[red]Error: NEBULA_SERVER_URL environment variable not set[/red]")
        return

    try:
        if service:
            # Single service restart
            if service not in VALID_SERVICES:
                console.print(f"[red]Invalid service: {service}[/red]")
                console.print(f"[dim]Valid services: {', '.join(VALID_SERVICES)}[/dim]")
                return
            
            if service == "api" and not force:
                console.print("[yellow]Warning: Restarting API will disconnect you temporarily![/yellow]")
            
            if service == "db" and not force:
                console.print("[yellow]Warning: Restarting database may cause data loss if transactions are in progress![/yellow]")
            
            console.print(f"[cyan]Restarting {service}...[/cyan]")
            response = requests.post(
                f"{SERVER_URL}/api/system/restart/{service}",
                timeout=120
            )
            
            if response.status_code == 200:
                data = response.json()
                console.print(f"[green]{data['message']}[/green]")
            else:
                console.print(f"[red]Error: {response.json().get('detail', 'Unknown error')}[/red]")
        else:
            # All services restart
            if not force:
                console.print("[yellow]Warning: This will restart ALL services and cause a brief outage![/yellow]")
                console.print("[dim]Use --force to skip this warning[/dim]")
                return
            
            console.print("[cyan]Restarting all services...[/cyan]")
            response = requests.post(
                f"{SERVER_URL}/api/system/restart",
                timeout=300
            )
            
            if response.status_code == 200:
                data = response.json()
                
                table = Table(title="Restart Results")
                table.add_column("Service", style="cyan")
                table.add_column("Status", style="bold")
                
                for svc, status in data["results"].items():
                    status_style = "[green]" if status == "restarted" else "[red]"
                    table.add_row(svc, f"{status_style}{status}[/]")
                
                console.print(table)
                
                if data.get("errors"):
                    console.print(f"[yellow]Some services had errors: {', '.join(data['errors'])}[/yellow]")
                else:
                    console.print("[green]All services restarted successfully![/green]")
            else:
                console.print(f"[red]Error: {response.json().get('detail', 'Unknown error')}[/red]")

    except requests.exceptions.Timeout:
        console.print("[yellow]Request timed out - service may still be restarting[/yellow]")
    except requests.exceptions.ConnectionError:
        if service == "api":
            console.print("[yellow]Connection lost - API is restarting. Wait a few seconds and try 'nebula ping'[/yellow]")
        else:
            console.print(f"[red]Error: Cannot connect to server at {SERVER_URL}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def show_container_status():
    """
    Show status of all Docker containers.
    """
    if not SERVER_URL:
        console.print("[red]Error: NEBULA_SERVER_URL environment variable not set[/red]")
        return

    try:
        console.print("[cyan]Checking container status...[/cyan]")
        response = requests.get(
            f"{SERVER_URL}/api/system/status",
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            
            overall = data["overall"]
            overall_style = "green" if overall == "healthy" else "yellow"
            
            table = Table(title=f"Nebula Services [{overall_style}]{overall.upper()}[/{overall_style}]")
            table.add_column("Service", style="cyan")
            table.add_column("Container", style="dim")
            table.add_column("Status", style="bold")
            
            for svc, info in data["services"].items():
                status = info["status"]
                if status == "running":
                    status_style = "[green]running[/green]"
                elif status == "exited":
                    status_style = "[red]exited[/red]"
                else:
                    status_style = f"[yellow]{status}[/yellow]"
                
                table.add_row(svc, info["container"], status_style)
            
            console.print(table)
        else:
            console.print(f"[red]Error: {response.json().get('detail', 'Unknown error')}[/red]")

    except requests.exceptions.Timeout:
        console.print("[red]Error: Request timed out[/red]")
    except requests.exceptions.ConnectionError:
        console.print(f"[red]Error: Cannot connect to server at {SERVER_URL}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

