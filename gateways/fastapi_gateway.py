from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from channels.web_terminal_channel import WebTerminalChannel
from core.gateway import Gateway


class CreateAgentReq(BaseModel):
    id: str
    type: str = "terminal"
    shell: Optional[str] = None
    cwd: Optional[str] = None


class CreateChannelReq(BaseModel):
    id: str
    type: str = "web_terminal"
    agent_id: str


class FastAPIChannelServer:
    def __init__(
        self,
        gateway: Gateway,
        channel_id: str,
        host: str = "0.0.0.0",
        port: int = 8000,
        static_dir: Optional[str] = None,
    ):
        self.gateway = gateway
        self.channel_id = channel_id
        self.host = host
        self.port = port
        self.app = FastAPI(title=f"Tinyclaw Terminal - {channel_id}")
        self._register_routes()

        if static_dir:
            static_path = Path(static_dir)
        else:
            static_path = Path(__file__).resolve().parents[1] / "clients" / "web_terminal"
        self.app.mount("/", StaticFiles(directory=str(static_path), html=True), name="static")

    def _register_routes(self) -> None:
        @self.app.get("/api/agents")
        async def list_agents():
            return {"agents": await self.gateway.list_agents()}

        @self.app.get("/api/channels")
        async def list_channels():
            return {"channels": self.gateway.list_channels()}

        @self.app.post("/api/agents")
        async def create_agent(req: CreateAgentReq):
            try:
                agent = await self.gateway.create_agent(
                    agent_id=req.id,
                    agent_type=req.type,
                    shell=req.shell,
                    cwd=req.cwd,
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return {"agent": await agent.status()}

        @self.app.delete("/api/agents/{agent_id}")
        async def delete_agent(agent_id: str):
            ok = await self.gateway.remove_agent(agent_id)
            if not ok:
                raise HTTPException(status_code=404, detail="Agent not found")
            return {"deleted": agent_id}

        @self.app.post("/api/channels")
        async def create_channel(req: CreateChannelReq):
            try:
                channel = await self.gateway.create_channel(
                    channel_id=req.id,
                    channel_type=req.type,
                    agent_id=req.agent_id,
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return {"channel": {"id": channel.channel_id, "agent_id": channel.agent_id}}

        @self.app.delete("/api/channels/{channel_id}")
        async def delete_channel(channel_id: str):
            ok = await self.gateway.remove_channel(channel_id)
            if not ok:
                raise HTTPException(status_code=404, detail="Channel not found")
            return {"deleted": channel_id}

        @self.app.websocket("/ws/terminal")
        async def terminal_ws_default(websocket: WebSocket):
            channel = self.gateway.get_channel(self.channel_id)
            if not channel or not isinstance(channel, WebTerminalChannel):
                await websocket.close(code=4004, reason="Channel not found")
                return
            await channel.handle_websocket(websocket)

        @self.app.websocket("/ws/terminal/{channel_id}")
        async def terminal_ws(websocket: WebSocket, channel_id: str):
            channel = self.gateway.get_channel(channel_id)
            if not channel or not isinstance(channel, WebTerminalChannel):
                await websocket.close(code=4004, reason="Channel not found")
                return
            await channel.handle_websocket(websocket)

    async def serve(self) -> None:
        import uvicorn

        config = uvicorn.Config(self.app, host=self.host, port=self.port)
        server = uvicorn.Server(config)
        await server.serve()
