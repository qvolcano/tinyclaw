from abc import ABC, abstractmethod


class Agent(ABC):
    """Agent base interface."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id

    @abstractmethod
    async def start(self) -> None:
        ...

    @abstractmethod
    async def stop(self) -> None:
        ...

    @abstractmethod
    async def send_input(self, data: bytes) -> None:
        ...

    @abstractmethod
    async def read_output(self) -> bytes:
        ...

    @abstractmethod
    async def status(self) -> dict:
        ...
