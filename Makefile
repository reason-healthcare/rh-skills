.PHONY: install test test-unit test-skills test-integration

install:
	uv tool install --editable .

test:
	uv run pytest

test-unit:
	uv run pytest tests/unit/

test-skills:
	uv run pytest tests/skills/

test-integration:
	uv run pytest tests/integration/
