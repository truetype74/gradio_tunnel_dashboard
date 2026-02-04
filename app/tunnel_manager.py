import os
import re
import shlex
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional

URL_REGEX = re.compile(r"https?://\S+")


@dataclass
class TunnelInfo:
    port: int
    command: str
    pid: int
    url: Optional[str] = None
    status: str = "running"
    exit_code: Optional[int] = None
    last_output: Optional[str] = None
    started_at: float = field(default_factory=time.time)
    logs: Deque[str] = field(default_factory=lambda: deque(maxlen=200))


class TunnelManager:
    def __init__(self) -> None:
        self._processes: Dict[int, subprocess.Popen[str]] = {}
        self._info: Dict[int, TunnelInfo] = {}
        self._lock = threading.Lock()

    def list_tunnels(self) -> Dict[int, TunnelInfo]:
        with self._lock:
            return dict(self._info)

    def get_logs(self, port: int) -> Optional[list[str]]:
        with self._lock:
            info = self._info.get(port)
            if not info:
                return None
            return list(info.logs)

    def start_tunnel(self, port: int) -> TunnelInfo:
        with self._lock:
            if port in self._processes and self._processes[port].poll() is None:
                return self._info[port]

            command_template = os.environ.get(
                "TUNNEL_COMMAND",
                "python -m gradio_tunneling --port {port}",
            )
            command = command_template.format(port=port)
            args = shlex.split(command)

            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env={
                    **os.environ,
                    "PYTHONUNBUFFERED": "1",
                },
            )
            info = TunnelInfo(port=port, command=command, pid=process.pid)
            self._processes[port] = process
            self._info[port] = info

            if process.stdout:
                threading.Thread(
                    target=self._capture_output,
                    args=(port, process),
                    daemon=True,
                ).start()
            threading.Thread(
                target=self._watch_process,
                args=(port, process),
                daemon=True,
            ).start()

            return info

    def stop_tunnel(self, port: int) -> bool:
        with self._lock:
            process = self._processes.get(port)
            if not process:
                return False
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
            self._processes.pop(port, None)
            self._info.pop(port, None)
            return True

    def shutdown(self) -> None:
        with self._lock:
            ports = list(self._processes.keys())
        for port in ports:
            self.stop_tunnel(port)

    def _capture_output(self, port: int, process: subprocess.Popen[str]) -> None:
        if not process.stdout:
            return
        for line in process.stdout:
            match = URL_REGEX.search(line)
            if match:
                with self._lock:
                    info = self._info.get(port)
                    if info:
                        info.url = match.group(0).rstrip(".")
            with self._lock:
                info = self._info.get(port)
                if info:
                    info.last_output = line.rstrip()
                    info.logs.append(line.rstrip())

    def _watch_process(self, port: int, process: subprocess.Popen[str]) -> None:
        exit_code = process.wait()
        with self._lock:
            info = self._info.get(port)
            if info:
                info.exit_code = exit_code
                if info.status == "running":
                    info.status = "stopped"
