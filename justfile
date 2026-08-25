default:
    @just --list

verify:
    python3 tools/verify_repository.py

test:
    python3 -m pytest tests -q

up:
    docker compose -f deploy/local/docker-compose.yml up -d

down:
    docker compose -f deploy/local/docker-compose.yml down
