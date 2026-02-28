import asyncio
import os
import shutil
from asyncio.subprocess import Process
from typing import Optional

from core.agent import Agent

try:
    from winpty import PtyProcess
except Exception:  # pragma: no cover
    PtyProcess = None


class TerminalAgent(Agent):
    """Simple terminal-backed agent."""

    def __init__(self, agent_id: str, shell: Optional[str] = None, cwd: Optional[str] = None):
        super().__init__(agent_id)
        self.shell = shell or ("powershell" if os.name == "nt" else "bash")
        self.cwd = cwd
        self.process: Optional[Process] = None
        self.pty_process: Optional[object] = None
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._reader_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self.process is not None or self.pty_process is not None:
            return
        resolved = shutil.which(self.shell) or self.shell
        shell_name = str(self.shell).lower()

        if os.name == "nt" and "codex" in shell_name and PtyProcess is None:
            raise RuntimeError(
                "Windows + codex requires PTY support. "
                "Install in current Python env: pip install pywinpty"
            )

        try:
            if os.name == "nt" and PtyProcess is not None:
                if str(resolved).lower().endswith((".cmd", ".bat")):
                    argv = ["cmd.exe", "/c", resolved]
                else:
                    argv = [resolved]
                self.pty_process = PtyProcess.spawn(argv=argv, cwd=self.cwd)
            else:
                self.process = await asyncio.create_subprocess_exec(
                    resolved,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    cwd=self.cwd,
                )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Shell command not found: {self.shell}. "
                "Please check PATH or use absolute path in config."
            ) from exc
        self._reader_task = asyncio.create_task(self._reader())

    async def stop(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
            self._reader_task = None

        if self.pty_process:
            try:
                await asyncio.to_thread(self.pty_process.terminate)
            except Exception:
                pass
            try:
                await asyncio.to_thread(self.pty_process.close)
            except Exception:
                pass
            self.pty_process = None

        if self.process:
            if self.process.returncode is None:
                self.process.terminate()
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=2)
                except asyncio.TimeoutError:
                    self.process.kill()
                    await self.process.wait()
            self.process = None

    async def send_input(self, data: bytes) -> None:
        if self.pty_process:
            if not self.pty_process.isalive():
                raise RuntimeError("Agent process already exited")
            try:
                text = data.decode(errors="ignore")
                await asyncio.to_thread(self.pty_process.write, text)
            except Exception as exc:
                raise RuntimeError("Agent process connection lost") from exc
            return

        if not self.process or not self.process.stdin:
            return
        if self.process.returncode is not None:
            raise RuntimeError(f"Agent process already exited (code={self.process.returncode})")
        try:
            self.process.stdin.write(data)
            await self.process.stdin.drain()
        except (ConnectionResetError, BrokenPipeError) as exc:
            raise RuntimeError("Agent process connection lost") from exc

    async def read_output(self) -> bytes:
        return await self._queue.get()

    async def status(self) -> dict:
        running = bool(
            (self.pty_process and self.pty_process.isalive())
            or (self.process and self.process.returncode is None)
        )
        return {
            "id": self.agent_id,
            "type": "terminal",
            "shell": self.shell,
            "running": running,
            "pid": self.process.pid if self.process else None,
            "mode": "pty" if self.pty_process else "pipe",
        }

    async def _reader(self) -> None:
        if self.pty_process:
            while True:
                try:
                    text = await asyncio.to_thread(self.pty_process.read, 1024)
                except Exception:
                    text = ""
                if not text:
                    await self._queue.put(b"\n[agent exited]\n")
                    break
                await self._queue.put(text.encode(errors="ignore"))
            return

        if not self.process or not self.process.stdout:
            return
        while True:
            data = await self.process.stdout.read(1024)
            if not data:
                await self._queue.put(b"\n[agent exited]\n")
                break
            await self._queue.put(data)
