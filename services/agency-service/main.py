from pathlib import Path

from noosfera_core.agent.agency_api import create_agency_app

app = create_agency_app(Path(__file__).with_name("service.yaml"))
