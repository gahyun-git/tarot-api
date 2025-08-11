SHELL := /bin/zsh
PATH := $(HOME)/Library/Python/3.13/bin:$(HOME)/.local/bin:$(PATH)
export PATH
POETRY ?= $(shell command -v poetry 2>/dev/null || echo $(HOME)/Library/Python/3.13/bin/poetry)
APP=app.main:app

.PHONY: install dev run lint fmt test docker-build docker-up docker-down podman-build podman-up podman-down data-update data-validate env-example fetch-commons cache-images cache-commons cache-archive

install:
	$(POETRY) install

# ensure .env exists from example if missing
env-example:
	@[ -f .env ] || (cp .env.example .env && echo "Created .env from .env.example")

dev: env-example
	$(POETRY) run uvicorn $(APP) --reload --host 0.0.0.0 --port 8008 --log-level debug --access-log

run: env-example
	$(POETRY) run uvicorn $(APP) --host 0.0.0.0 --port 8008 --access-log

lint:
	$(POETRY) run ruff check .

fmt:
	$(POETRY) run black . && $(POETRY) run ruff check . --fix

test:
	$(POETRY) run pytest

# Docker
docker-build:
	docker build -t tarot-api:latest .

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

# Podman
podman-build:
	podman build -f Containerfile -t tarot-api:latest .

podman-up:
	podman-compose up --build -d || podman compose up --build -d

podman-down:
	podman-compose down || podman compose down

# Data
data-update:
	$(POETRY) run python scripts/fetch_tarot_images.py

data-validate:
	$(POETRY) run python scripts/fetch_tarot_images.py --validate-only

fetch-commons:
	$(POETRY) run python scripts/fetch_commons_cards.py

cache-images:
	$(POETRY) run python scripts/cache_card_images.py --data data/tarot-images.json --out static/cards

cache-commons:
	$(POETRY) run python scripts/map_commons_and_cache.py --data data/tarot-images.json --out static/cards

cache-archive:
	$(POETRY) run python scripts/cache_archive_images.py --out static/cards
