.PHONY: install test test-unit test-skills test-integration check-schemas sync-schemas

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

check-schemas:
	@diff -r schemas/ src/rh_skills/schemas/ && echo "Schemas in sync" || \
		(echo "Schema drift detected — run: make sync-schemas" && exit 1)

sync-schemas:
	cp schemas/*.yaml src/rh_skills/schemas/
	@echo "Bundled schemas updated from schemas/"
