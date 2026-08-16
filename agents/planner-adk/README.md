# planner-agent

Orquestrador global (Google ADK, Python). Nunca executa lógica de voo,
hotel, atividade ou clima diretamente — apenas descobre especialistas via
`agent-registry`, delega via A2A e consolida a resposta.

## Escopo desta versão (Fase 5)

`flight-agent`, `hotel-agent`, `activity-agent` e `budget-agent` já
existem e são chamados de verdade via A2A. Os três primeiros usam a
mesma função genérica de parsing (`_parse_specialist_result`), provando
que o Planner não precisa saber em que linguagem ou framework um
especialista foi escrito — apenas seguir o contrato A2A. O `budget-agent`
é diferente: ele não recebe o `TravelRequest` bruto, e sim os resultados
já parseados de flight/hotel/activity mais o orçamento máximo (§5.5),
então é delegado numa etapa própria (`_delegate_budget`), depois do
laço de delegação genérico. Com os quatro `SUCCESS`, a resposta
consolidada chega a `status = COMPLETED` (antes sempre `PARTIAL`). Só o
Enrichment (AWS, §5.6, opcional) ainda não existe — continua aplicando a
regra de degradação do §11: `enrichment` fica `SKIPPED`, o que nunca
impede `COMPLETED`.

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
