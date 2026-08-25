from pathlib import Path

from noosfera_core.agent.governance_api import create_governance_app

app = create_governance_app(Path(__file__).with_name("service.yaml"))
