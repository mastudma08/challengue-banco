.PHONY: test run token podman-up podman-down logs

test:
	python -m pytest -q

run:
	uvicorn app.infrastructure.api.main:app --reload --port 8080

token:
	python scripts/create_dev_token.py

podman-up:
	podman compose up --build -d

podman-down:
	podman compose down

logs:
	podman logs -f onboarding-agent-phase2
