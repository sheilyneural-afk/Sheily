from pathlib import Path

from noosfera_core.agent.identity_api import create_identity_app

app = create_identity_app(Path(__file__).with_name("service.yaml"))
