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
- Hotel Agent: http://localhost:8003
- Activity Agent: http://localhost:8004
- Budget Agent: http://localhost:8005
- Mock Specialist Agent: http://localhost:8099
- MCP Flight Search: http://localhost:9001
- MCP Hotel Search: http://localhost:9002
- MCP Places: http://localhost:9003
- MCP Weather: http://localhost:9004
- MCP Currency: http://localhost:9005
- MCP Calculator: http://localhost:9006
- Agent Registry: http://localhost:8080
- Jaeger UI: http://localhost:16686

## Rodando um agente fora do Docker

```bash
cd agents/planner-adk
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
AGENT_REGISTRY_URL=http://localhost:8080 uvicorn app.main:app --reload --port 8001
```

Para o hotel-agent (TypeScript), fora do Docker:

```bash
cd agents/hotel-langgraph
npm install
MCP_HOTEL_URL=http://localhost:9002/mcp PORT=8003 npm start
```

Para o activity-agent, fora do Docker:

```bash
cd agents/activity-beeai
pip install -e .
MCP_PLACES_URL=http://localhost:9003/mcp MCP_WEATHER_URL=http://localhost:9004/mcp \
  uvicorn app.main:app --reload --port 8004
```

Para o budget-agent, fora do Docker:

```bash
cd agents/budget-crewai
pip install -e .
MCP_CURRENCY_URL=http://localhost:9005/mcp MCP_CALCULATOR_URL=http://localhost:9006/mcp \
  uvicorn app.main:app --reload --port 8005
```

## Testes

Cada agente tem sua própria suíte (`agents/<agente>/tests` em Python, ou
`agents/hotel-langgraph/test` em TypeScript), pois cada um é deployável e
testável independentemente (RNF-06):

```bash
cd agents/planner-adk && pip install -e . pytest && pytest -q
cd agents/mock-specialist && pip install -e . pytest && pytest -q
cd agents/flight-openai && pip install -e . pytest && pytest -q
cd agents/hotel-langgraph && npm install && npm test
cd agents/activity-beeai && pip install -e . pytest && pytest -q
cd agents/budget-crewai && pip install -e . pytest && pytest -q
```

Testes de contrato e E2E (raiz do repo, exigem serviços rodando):

```bash
pip install -r tests/requirements.txt
AGENT_URLS="http://localhost:8001,http://localhost:8099,http://localhost:8002,http://localhost:8003,http://localhost:8004,http://localhost:8005" pytest tests/contract -q
PLANNER_URL=http://localhost:8001 pytest tests/e2e -q
```

Smoke test:

```bash
./scripts/smoke-test.sh
```
