from pathlib import Path

from noosfera_core.agent.audit_api import create_audit_app

app = create_audit_app(Path(__file__).with_name("service.yaml"))
