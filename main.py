import argparse
import asyncio
from pathlib import Path

from agents.terminal_agent import TerminalAgent
from channels.web_terminal_channel import WebTerminalChannel
from core.gateway import Gateway
from gateways.fastapi_gateway import FastAPIChannelServer


try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


def load_config(config_path: str) -> dict:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with path.open("rb") as f:
        return tomllib.load(f)


async def bootstrap(config: dict) -> tuple[Gateway, list[FastAPIChannelServer]]:
    gateway = Gateway()
    gateway.register_agent_type("terminal", TerminalAgent)
    gateway.register_channel_type("web_terminal", WebTerminalChannel)

    for item in config.get("agents", []):
        await gateway.create_agent(
            agent_id=item["id"],
            agent_type=item.get("type", "terminal"),
            shell=item.get("shell"),
            cwd=item.get("cwd"),
        )

    servers: list[FastAPIChannelServer] = []
    for item in config.get("channels", []):
        channel_id = item["id"]
        await gateway.create_channel(
            channel_id=channel_id,
            channel_type=item.get("type", "web_terminal"),
            agent_id=item["agent_id"],
        )
        server = FastAPIChannelServer(
            gateway=gateway,
            channel_id=channel_id,
            host=item.get("host", "0.0.0.0"),
            port=int(item.get("port", 8000)),
            static_dir=item.get("static_dir", "clients/web_terminal"),
        )
        servers.append(server)

    return gateway, servers


async def shutdown(gateway: Gateway) -> None:
    for channel in list(gateway.list_channels()):
        await gateway.remove_channel(channel["id"])
    for agent in list(await gateway.list_agents()):
        await gateway.remove_agent(agent["id"])


async def run(config_path: str) -> None:
    config = load_config(config_path)
    gateway, servers = await bootstrap(config)
    if not servers:
        print("No channel configured. Nothing to serve.")
        await shutdown(gateway)
        return

    try:
        await asyncio.gather(*[server.serve() for server in servers])
    finally:
        await shutdown(gateway)


def main() -> None:
    parser = argparse.ArgumentParser(description="Tinyclaw")
    parser.add_argument("--config", default="config.toml", help="Path to config file")
    args = parser.parse_args()
    asyncio.run(run(args.config))


if __name__ == "__main__":
    main()
