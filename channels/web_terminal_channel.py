import asyncio
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from core.channel import Channel


class WebTerminalChannel(Channel):
    """Bridge WebSocket client and terminal agent."""

    def __init__(self, channel_id: str, agent_id: str = "", **kwargs):
        super().__init__(channel_id, agent_id=agent_id, **kwargs)
        self.websocket: Optional[WebSocket] = None
        self._pump_task: Optional[asyncio.Task] = None
        self._history: str = ""
        self._history_limit = int(kwargs.get("history_limit", 200_000))

    async def open(self) -> None:
        if not self._pump_task:
            self._pump_task = asyncio.create_task(self._agent_to_websocket_loop())

    async def close(self) -> None:
        if self._pump_task:
            self._pump_task.cancel()
            self._pump_task = None
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass
            self.websocket = None

    async def on_client_data(self, data: bytes) -> None:
        if self.agent:
            try:
                await self.agent.send_input(data)
            except Exception as exc:
                if self.websocket:
                    await self.websocket.send_text(f"\n[channel error] {exc}\n")

    async def on_agent_data(self, data: bytes) -> None:
        text = data.decode(errors="ignore")
        self._history += self._filter_history_noise(text)
        if len(self._history) > self._history_limit:
            self._history = self._history[-self._history_limit :]
        if self.websocket:
            await self.websocket.send_text(text)

    async def handle_websocket(self, websocket: WebSocket) -> None:
        await websocket.accept()

        if self.websocket and self.websocket is not websocket:
            try:
                await self.websocket.close(code=4000, reason="Replaced by new connection")
            except Exception:
                pass

        self.websocket = websocket
        if self._history:
            await websocket.send_text(self._history)

        try:
            while True:
                message = await websocket.receive_text()
                await self.on_client_data(message.encode())
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            try:
                await websocket.send_text(f"\n[channel fatal] {exc}\n")
            except Exception:
                pass
        finally:
            if self.websocket is websocket:
                self.websocket = None

    async def _agent_to_websocket_loop(self) -> None:
        while True:
            if not self.agent:
                await asyncio.sleep(0.1)
                continue
            data = await self.agent.read_output()
            await self.on_agent_data(data)

    def _filter_history_noise(self, text: str) -> str:
        # Keep ANSI sequences for replay fidelity, but drop known DA response noise.
        return text.replace("\x1b[?1;2c", "").replace("[?1;2c", "")
