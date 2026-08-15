.PHONY: local aws-local aws-lite down test smoke logs

local:
	docker compose up --build

aws-local:
	AWS_AGENT_ENABLED=true MODEL_PROVIDER=ollama docker compose --profile aws up --build

aws-lite:
	AWS_AGENT_ENABLED=true MODEL_PROVIDER=bedrock docker compose --profile aws up --build

down:
	docker compose --profile aws down

test:
	pytest -q

smoke:
	./scripts/smoke-test.sh

logs:
	docker compose logs -f
