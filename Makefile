.PHONY: verify generate test test-policy test-contract lint format local-up local-down local-e2e model-pull model-eval

generate:
	python3 tools/generate_runtime_schemas.py
	python3 tools/generate_openapi.py
	python3 tools/generate_module_maturity.py
	python3 tools/generate_file_manifest.py

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

local-e2e:
	NOOSFERA_MODEL_PROVIDER=deterministic docker compose -f deploy/local/docker-compose.yml up -d --build experience-service audit-service
	docker compose -f deploy/local/docker-compose.yml exec -T \
		-e NOOSFERA_E2E_API_URL=http://127.0.0.1:8080 \
		-e NOOSFERA_E2E_AUDIT_URL=http://audit-service:8080 \
		experience-service python - < tools/run_local_e2e.py

model-pull:
	bash tools/pull_local_model.sh "$${MODEL:-qwen3:8b}"

model-eval:
	python3 tools/run_model_evals.py --provider ollama
