# planner-agent

Orquestrador global (Google ADK, Python). Nunca executa lógica de voo,
hotel, atividade ou clima diretamente — apenas descobre especialistas via
`agent-registry`, delega via A2A e consolida a resposta.

## Escopo desta versão (Fase 3)

`flight-agent` e `hotel-agent` já existem e são chamados de verdade via
A2A: a resposta inclui `flight.status = SUCCESS` e `hotel.status =
SUCCESS`, cada um com opções reais vindas dos respectivos servidores MCP.
O parser dos dois usa a mesma função genérica
(`_parse_specialist_result`), provando que o Planner não precisa saber
em que linguagem um especialista foi escrito — apenas seguir o contrato
A2A. Activity/Budget/Enrichment ainda não existem (ver `PROJECT_SPEC.md`
§43), então continuam aplicando as regras de degradação (§11):
`activities` fica `UNAVAILABLE`, `budget` fica `UNKNOWN`, resposta geral
continua `PARTIAL` até todos os especialistas existirem.

## Endpoints

- `GET /health`, `GET /ready`
- `GET /.well-known/agent-card.json`
- `POST /a2a` (A2A JSON-RPC — permite que o Planner também seja endereçado por A2A)
- `GET /v1/foundation-check` — critério de aceite do M1: descoberta via Registry + round-trip A2A
- `POST /v1/travel-requests` — endpoint de entrada do usuário (`TravelRequest` → `TravelResponse`)

## Rodando localmente

```bash
pip install -e .
uvicorn app.main:app --reload --port 8001
```

## Nota sobre Google ADK

O ADK é declarado como dependência (`google-adk`) e será usado para a
camada de raciocínio/seleção de ferramentas a partir da Fase 6
(paralelismo real entre múltiplos especialistas). Nesta milestone a
orquestração é determinística (sem LLM), para manter RNF-03 (custo zero
por padrão) enquanto valida apenas o transporte A2A.
