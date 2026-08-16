# planner-agent

Orquestrador global (Google ADK, Python). Nunca executa lógica de voo,
hotel, atividade ou clima diretamente — apenas descobre especialistas via
`agent-registry`, delega via A2A e consolida a resposta.

## Escopo desta versão (Fase 7)

Os cinco especialistas do spec já existem e são chamados de verdade via
A2A: `flight-agent`, `hotel-agent`, `activity-agent`, `budget-agent`
(obrigatórios) e `aws-enrichment-agent` (opcional, §5.6). Descoberta é
sempre por *skill* declarada no Agent Card de cada agente
(`_agents_by_skill`), nunca por id hard-coded (§9) — o que também prova
que o Planner não precisa saber em que linguagem ou framework um
especialista foi escrito, apenas seguir o contrato A2A.

Flight/Hotel/Activity são delegados concorrentemente
(`asyncio.gather`, Fase 6 "Paralelismo") — são independentes entre si.
Budget é diferente: não recebe o `TravelRequest` bruto, e sim os
resultados já parseados de flight/hotel/activity mais o orçamento máximo
(§5.5), então é delegado numa etapa própria (`_delegate_budget`), depois
do fan-out. Enrichment é ainda mais separado: só é tentado quando
`AWS_AGENT_ENABLED=true` (`_delegate_enrichment`), roda depois do
Budget, e fica de fora do cálculo de `overall_status` — com ele
`SKIPPED`/`UNAVAILABLE`/`SUCCESS`, o resultado nunca muda (§11: "AWS
Enrichment indisponível: Ignorar. Não marcar o fluxo como falha").

Com os quatro especialistas centrais `SUCCESS`, a resposta consolidada
chega a `status = COMPLETED`; se nenhum dos quatro tiver sucesso,
`FAILED`; caso contrário, `PARTIAL`.

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

O ADK é declarado como dependência (`google-adk`), mas a orquestração
até aqui é inteiramente determinística (descoberta por skill,
delegação A2A com fan-out concorrente onde possível, consolidação por
regras fixas) — sem nenhum uso de LLM/reasoning do ADK. Isso mantém
RNF-03 (custo zero por padrão) e evita comportamento não-determinístico
numa camada — orquestração central — onde previsibilidade importa mais
do que em qualquer especialista individual. Diferente de
flight/activity/budget/enrichment, não há um "caminho ADK opcional"
implementado nesta milestone.
