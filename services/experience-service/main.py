from pathlib import Path

from noosfera_core.agent import create_agent_app

app = create_agent_app(Path(__file__).with_name("service.yaml"))
