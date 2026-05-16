.PHONY: backend frontend dev redis-up redis-down redis-logs redis-cli redis-status

backend:
	./scripts/run-backend.sh

frontend:
	./scripts/run-frontend.sh

dev:
	./scripts/dev.sh

# ─── compose helpers ──────────────────────────────────────────────────
# Auto-detect compose flavor: prefer the v2 plugin (`docker compose ...`)
# but fall back to standalone v1 (`docker-compose ...`). Lets the same
# Makefile work on macOS Docker Desktop, Colima, and Linux installs that
# only shipped one of the two.
DOCKER_COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")
COMPOSE := $(DOCKER_COMPOSE) --env-file backend/.env -f docker-compose.staging.yml

redis-up:
	@if [ ! -f backend/.env ]; then \
		echo "✗ backend/.env missing — copy backend/.env.example and set REDIS_PASSWORD."; \
		exit 1; \
	fi
	@grep -q '^REDIS_PASSWORD=..' backend/.env || { \
		echo "✗ REDIS_PASSWORD not set in backend/.env."; \
		echo "  generate one: openssl rand -base64 32 | tr -d '=+/' | cut -c1-32"; \
		exit 1; \
	}
	$(COMPOSE) up -d redis
	@echo "✓ redis starting; run 'make redis-status' to confirm healthy."

redis-down:
	$(COMPOSE) down

redis-logs:
	$(COMPOSE) logs -f redis

redis-status:
	@$(COMPOSE) ps redis

# Open an authed redis-cli inside the container. Reads the password
# from backend/.env so it never appears in your shell history.
redis-cli:
	@$(COMPOSE) exec redis sh -c 'redis-cli -a "$$REDIS_PASSWORD" --no-auth-warning'

