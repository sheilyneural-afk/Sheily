.PHONY: verify test test-policy test-contract lint format local-up local-down

verify:
	python3 tools/verify_repository.py

test: test-contract test-policy
	python3 -m pytest tests -q

test-policy:
	@if command -v opa >/dev/null 2>&1; then opa test policies -v; else echo "opa no instalado: prueba omitida"; fi

test-contract:
	python3 tools/validate_schemas.py

lint:
	python3 -m ruff check packages/python services tests tools

format:
	python3 -m ruff format packages/python services tests tools

local-up:
	docker compose -f deploy/local/docker-compose.yml up -d

local-down:
	docker compose -f deploy/local/docker-compose.yml down
