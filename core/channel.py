from abc import ABC, abstractmethod
from typing import Optional

from .agent import Agent


class Channel(ABC):
    """Channel base interface."""

    def __init__(self, channel_id: str, agent_id: str = "", **kwargs):
        self.channel_id = channel_id
        self.agent_id = agent_id
        self.agent: Optional[Agent] = None

    def bind(self, agent: Agent) -> None:
        self.agent = agent

    @abstractmethod
    async def open(self) -> None:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...

    @abstractmethod
    async def on_client_data(self, data: bytes) -> None:
        ...

    @abstractmethod
    async def on_agent_data(self, data: bytes) -> None:
        ...
