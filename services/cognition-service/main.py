from pathlib import Path

from noosfera_core.agent.cognition_api import create_cognition_app

app = create_cognition_app(Path(__file__).with_name("service.yaml"))
