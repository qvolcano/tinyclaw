from typing import Dict, Optional, Type

from .agent import Agent
from .channel import Channel


class Gateway:
    """In-memory registry for agents/channels."""

    def __init__(self):
        self._agents: Dict[str, Agent] = {}
        self._channels: Dict[str, Channel] = {}
        self._agent_types: Dict[str, Type[Agent]] = {}
        self._channel_types: Dict[str, Type[Channel]] = {}

    def register_agent_type(self, type_name: str, cls: Type[Agent]) -> None:
        self._agent_types[type_name] = cls

    def register_channel_type(self, type_name: str, cls: Type[Channel]) -> None:
        self._channel_types[type_name] = cls

    async def create_agent(self, agent_id: str, agent_type: str, **kwargs) -> Agent:
        if agent_id in self._agents:
            raise RuntimeError(f"Agent already exists: {agent_id}")
        cls = self._agent_types.get(agent_type)
        if cls is None:
            raise RuntimeError(f"Unknown agent type: {agent_type}")
        agent = cls(agent_id, **kwargs)
        await agent.start()
        self._agents[agent_id] = agent
        return agent

    async def create_channel(self, channel_id: str, channel_type: str, agent_id: str, **kwargs) -> Channel:
        if channel_id in self._channels:
            raise RuntimeError(f"Channel already exists: {channel_id}")
        cls = self._channel_types.get(channel_type)
        if cls is None:
            raise RuntimeError(f"Unknown channel type: {channel_type}")
        agent = self._agents.get(agent_id)
        if not agent:
            raise KeyError(f"Agent not found: {agent_id}")
        channel = cls(channel_id, agent_id=agent_id, **kwargs)
        channel.bind(agent)
        await channel.open()
        self._channels[channel_id] = channel
        return channel

    async def remove_channel(self, channel_id: str) -> bool:
        channel = self._channels.pop(channel_id, None)
        if not channel:
            return False
        await channel.close()
        return True

    async def remove_agent(self, agent_id: str) -> bool:
        agent = self._agents.pop(agent_id, None)
        if not agent:
            return False

        related_channels = [cid for cid, ch in self._channels.items() if ch.agent_id == agent_id]
        for channel_id in related_channels:
            await self.remove_channel(channel_id)

        await agent.stop()
        return True

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        return self._agents.get(agent_id)

    def get_channel(self, channel_id: str) -> Optional[Channel]:
        return self._channels.get(channel_id)

    async def list_agents(self) -> list[dict]:
        items: list[dict] = []
        for agent in self._agents.values():
            items.append(await agent.status())
        return items

    def list_channels(self) -> list[dict]:
        return [
            {"id": ch.channel_id, "agent_id": ch.agent_id, "type": ch.__class__.__name__}
            for ch in self._channels.values()
        ]
