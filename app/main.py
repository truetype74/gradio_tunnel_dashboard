from __future__ import annotations

import psutil
import subprocess

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.tunnel_manager import TunnelManager

app = FastAPI(title="Gradio Tunnel Dashboard")
manager = TunnelManager()

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


class TunnelRequest(BaseModel):
    port: int


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


def _load_docker_names() -> dict[str, str]:
    try:
        result = subprocess.run(
            ["docker", "ps", "--no-trunc", "--format", "{{.ID}} {{.Names}}"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return {}
    containers: dict[str, str] = {}
    for line in result.stdout.splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2:
            continue
        container_id, name = parts
        containers[container_id] = name
    return containers


def _container_name_for_pid(pid: int, container_names: dict[str, str]) -> str | None:
    try:
        with open(f"/proc/{pid}/cgroup", "r", encoding="utf-8") as handle:
            content = handle.read()
    except OSError:
        return None
    for line in content.splitlines():
        if "docker" not in line:
            continue
        for part in line.split("/"):
            if len(part) >= 12 and all(ch in "0123456789abcdef" for ch in part[:12]):
                for container_id, name in container_names.items():
                    if container_id.startswith(part):
                        return name
    return None


@app.get("/api/ports")
async def list_ports() -> list[dict[str, str | int | None]]:
    connections = psutil.net_connections(kind="inet")
    results: list[dict[str, str | int | None]] = []
    seen = set()
    container_names = _load_docker_names()

    for conn in connections:
        if conn.status != psutil.CONN_LISTEN:
            continue
        if not conn.laddr:
            continue
        port = conn.laddr.port
        if port in seen:
            continue
        seen.add(port)
        process_name = "unknown"
        container_name = None
        pid = None
        if conn.pid:
            try:
                pid = conn.pid
                process = psutil.Process(conn.pid)
                process_name = process.name()
                container_name = _container_name_for_pid(conn.pid, container_names)
            except psutil.Error:
                process_name = "unknown"
        results.append(
            {
                "port": port,
                "service": process_name,
                "container": container_name,
                "pid": pid,
            }
        )

    return sorted(results, key=lambda item: item["port"])


@app.get("/api/tunnels")
async def list_tunnels() -> list[dict[str, str | int | None]]:
    tunnels = manager.list_tunnels()
    return [
        {
            "port": info.port,
            "command": info.command,
            "pid": info.pid,
            "url": info.url,
            "status": info.status,
            "exit_code": info.exit_code,
            "last_output": info.last_output,
        }
        for info in tunnels.values()
    ]


@app.get("/api/tunnels/{port}/logs")
async def tunnel_logs(port: int) -> dict[str, list[str]]:
    logs = manager.get_logs(port)
    if logs is None:
        raise HTTPException(status_code=404, detail="Tunnel not running.")
    return {"logs": logs}


@app.post("/api/tunnels")
async def start_tunnel(payload: TunnelRequest) -> dict[str, str | int | None]:
    if payload.port <= 0 or payload.port > 65535:
        raise HTTPException(status_code=400, detail="Invalid port.")
    info = manager.start_tunnel(payload.port)
    return {
        "port": info.port,
        "command": info.command,
        "pid": info.pid,
        "url": info.url,
        "status": info.status,
        "exit_code": info.exit_code,
        "last_output": info.last_output,
    }


@app.delete("/api/tunnels/{port}")
async def stop_tunnel(port: int) -> dict[str, bool]:
    stopped = manager.stop_tunnel(port)
    if not stopped:
        raise HTTPException(status_code=404, detail="Tunnel not running.")
    return {"stopped": True}


@app.on_event("shutdown")
def shutdown_event() -> None:
    manager.shutdown()
