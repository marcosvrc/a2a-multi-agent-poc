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

Com o AWS Enrichment Agent ligado (opcional, `--profile aws`):

```bash
make aws-local   # AWS_AGENT_ENABLED=true MODEL_PROVIDER=ollama
make aws-lite    # AWS_AGENT_ENABLED=true MODEL_PROVIDER=bedrock (requer credenciais AWS)
```

Serviços expostos:

- Planner: http://localhost:8001
- Flight Agent: http://localhost:8002
- Hotel Agent: http://localhost:8003
- Activity Agent: http://localhost:8004
- Budget Agent: http://localhost:8005
- AWS Enrichment Agent (perfil `aws`): http://localhost:8006
- Mock Specialist Agent: http://localhost:8099
- MCP Flight Search: http://localhost:9001
- MCP Hotel Search: http://localhost:9002
- MCP Places: http://localhost:9003
- MCP Weather: http://localhost:9004
- MCP Currency: http://localhost:9005
- MCP Calculator: http://localhost:9006
- Agent Registry: http://localhost:8080
- Ollama (perfil `aws`): http://localhost:11434
- Jaeger UI: http://localhost:16686

## Ligando os caminhos guiados por LLM (opcional)

Por padrão todo especialista roda no caminho determinístico (grátis, sem
LLM). Três agentes têm um caminho alternativo opcional que usa um LLM de
verdade sobre os mesmos dados mock (ver ADR-009/011/012):

| Agente | Variável(is) | Backend | Precisa rebuildar imagem? |
|---|---|---|---|
| Flight Agent | `OPENAI_API_KEY` | OpenAI | Não — `openai-agents` já vem instalado |
| Activity Agent | `INSTALL_BEEAI=true` + `BEEAI_CHAT_MODEL` | BeeAI Framework | Sim |
| Budget Agent | `INSTALL_CREWAI=true` + `CREWAI_LLM_MODEL` | CrewAI | Sim |

**Flight Agent** — só precisa da chave no `.env` (nunca commitada) e
reiniciar o container:

```bash
# .env
OPENAI_API_KEY=sk-...
```
```bash
docker compose up -d flight-agent
```

**Activity Agent (BeeAI) e Budget Agent (CrewAI)** — além da variável de
modelo, a dependência (`beeai-framework`/`crewai`) só entra na imagem se
o build arg correspondente for `true` — ela é pesada e fica de fora do
build padrão de propósito (mesma lógica do AWS Enrichment Agent/Strands).
Sem o rebuild, a variável de modelo fica setada mas o agente cai
silenciosamente no caminho determinístico (o `ImportError` é capturado —
nunca quebra o fluxo, só não faz o que foi pedido).

```bash
# .env
INSTALL_BEEAI=true
BEEAI_CHAT_MODEL=ollama:llama3.1
INSTALL_CREWAI=true
CREWAI_LLM_MODEL=ollama/llama3.1
# Se o Ollama estiver rodando direto na sua máquina (não no container
# `ollama` do profile "aws") e você usa Docker Desktop no Mac/Windows:
OLLAMA_API_BASE=http://host.docker.internal:11434
```
```bash
docker compose build activity-agent budget-agent
docker compose up -d activity-agent budget-agent
```

Sem Ollama, os mesmos `BEEAI_CHAT_MODEL`/`CREWAI_LLM_MODEL` também aceitam
um modelo OpenAI (ex.: `openai:gpt-4o-mini` para o BeeAI,
`gpt-4o-mini` para o CrewAI) — nesse caso a chamada real é para a OpenAI,
usando a mesma `OPENAI_API_KEY` do Flight Agent, com custo por uso.

Nenhum desses caminhos é exercitado pelos testes automatizados desta
milestone (nenhum backend de chat real disponível em CI/dev) — a lógica
de *wiring* (qual variável vira qual parâmetro do SDK) é testada com
stubs (`agents/{activity-beeai,budget-crewai}/tests/test_agent.py`), mas
o comportamento fim-a-fim contra um LLM de verdade precisa ser validado
manualmente, como os próprios ADR-011/012 alertam.

## Autenticação (Fase 9)

Todo `POST /a2a` exige um bearer token a partir desta fase —
`/health`, `/ready` e `/.well-known/agent-card.json` continuam abertos.
Com `AUTH_MODE=dev` (padrão, também o de `.env.example`), qualquer
`curl` manual contra `/a2a` precisa do header:

```bash
curl -s http://localhost:8002/a2a \
  -H "Authorization: Bearer local-development-only" \
  -H "content-type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"parts":[{"text":"..."}]}}}'
```

Sem o header (ou com o token errado), a resposta é `401`. Ver
`docs/adr/ADR-015-security-jwt-agent-identity-oidc-spike.md` para os
três modos (`dev`/`jwt`/`none`) e por que só `/a2a` é protegido.

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

Para o aws-enrichment-agent, fora do Docker (caminho determinístico, sem
Strands/Ollama/Bedrock):

```bash
cd agents/aws-strands
pip install -e .
MCP_WEATHER_URL=http://localhost:9004/mcp uvicorn app.main:app --reload --port 8006
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
cd agents/aws-strands && pip install -e . pytest && pytest -q
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
