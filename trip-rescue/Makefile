.PHONY: \
	test \
	test-hardening \
	test-whatif \
	smoke \
	smoke-rescue \
	smoke-fallback \
	smoke-preferences \
	smoke-whatif \
	smoke-prod \
	up \
	down \
	build \
	rebuild \
	logs \
	ps \
	health \
	mcp \
	openapi


test:
	python -m pytest -q


test-hardening:
	python -m pytest tests/test_parser_hardening.py -q


test-whatif:
	python -m pytest tests/test_whatif.py tests/test_whatif_api.py -q


smoke: smoke-rescue smoke-fallback smoke-preferences smoke-whatif


smoke-rescue:
	python -m scripts.smoke_rescue


smoke-fallback:
	python -m scripts.smoke_fallback


smoke-preferences:
	python -m scripts.smoke_preferences


smoke-whatif:
	python -m scripts.smoke_whatif


smoke-prod:
	python -m scripts.prod_smoke


build:
	docker compose build


up:
	docker compose up -d


down:
	docker compose down


rebuild:
	docker compose up -d --build


logs:
	docker compose logs --tail=100 trip-rescue


ps:
	docker compose ps


health:
	curl -fsS http://127.0.0.1:8020/health


mcp:
	curl -fsS 'http://127.0.0.1:8020/api/v1/system/mcp?refresh=true'


openapi:
	curl -fsS \
		http://127.0.0.1:8020/openapi.json \
		-o openapi.json