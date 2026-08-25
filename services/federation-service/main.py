from pathlib import Path

from noosfera_core.service import create_app

app = create_app(Path(__file__).with_name("service.yaml"))
