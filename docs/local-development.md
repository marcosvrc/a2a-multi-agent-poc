# Desenvolvimento local

## Pré-requisitos

- Docker + Docker Compose
- Para rodar um agente Python fora do Docker: Python 3.11+

## Subindo a stack

```bash
cp .env.example .env
make local
# ou: docker compose up --build
```

Serviços expostos:

- Planner: http://localhost:8001
- Flight Agent: http://localhost:8002
- Mock Specialist Agent: http://localhost:8099
- MCP Flight Search: http://localhost:9001
- Agent Registry: http://localhost:8080
- Jaeger UI: http://localhost:16686

## Rodando um agente fora do Docker

```bash
cd agents/planner-adk
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
AGENT_REGISTRY_URL=http://localhost:8080 uvicorn app.main:app --reload --port 8001
```

## Testes

Cada agente tem sua própria suíte (`agents/<agente>/tests`), pois cada um
é deployável e testável independentemente (RNF-06):

```bash
cd agents/planner-adk && pip install -e . pytest && pytest -q
cd agents/mock-specialist && pip install -e . pytest && pytest -q
cd agents/flight-openai && pip install -e . pytest && pytest -q
```

Testes de contrato e E2E (raiz do repo, exigem serviços rodando):

```bash
pip install -r tests/requirements.txt
AGENT_URLS="http://localhost:8001,http://localhost:8099,http://localhost:8002" pytest tests/contract -q
PLANNER_URL=http://localhost:8001 pytest tests/e2e -q
```

Smoke test:

```bash
./scripts/smoke-test.sh
```
