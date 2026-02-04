from __future__ import annotations

import psutil
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


@app.get("/api/ports")
async def list_ports() -> list[dict[str, str | int]]:
    connections = psutil.net_connections(kind="inet")
    results: list[dict[str, str | int]] = []
    seen = set()

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
        if conn.pid:
            try:
                process_name = psutil.Process(conn.pid).name()
            except psutil.Error:
                process_name = "unknown"
        results.append(
            {
                "port": port,
                "service": process_name,
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
