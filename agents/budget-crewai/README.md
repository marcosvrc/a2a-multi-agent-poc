# budget-agent

Especialista em orçamento (CrewAI, Python), conforme `PROJECT_SPEC.md`
§5.5. Diferente dos outros especialistas, não busca nada: o Planner
delega a ele os *resultados* de voo/hotel/atividade já obtidos, mais o
orçamento máximo do viajante, e este agente só combina números.

## Cálculo

```text
flight_cost      = opção de voo recomendada (ou mais barata), 0 se indisponível
hotel_cost       = hotel mais barato × noites, 0 se indisponível
activity_cost    = soma de um custo fixo por categoria de atividade
food_estimate    = BUDGET_FOOD_PER_TRAVELER_PER_NIGHT × viajantes × noites
transport_estimate = BUDGET_TRANSPORT_PER_TRAVELER_PER_NIGHT × viajantes × noites
total            = soma dos cinco acima
remaining        = limite - total
budget_status     = WITHIN_BUDGET (≤80% do limite) | NEAR_LIMIT (≤100%) | OVER_BUDGET (>100%) | UNKNOWN (sem limite)
```

Toda combinação passa pelo `mcp-calculator` (`sum`/`subtract`/
`multiply`) — nunca uma expressão livre avaliada localmente (§33 "Não
permitir expressão arbitrária executada via eval"). Quando a moeda do
viajante difere de BRL (moeda em que os mocks de voo/hotel são
gerados), cada componente é convertido via `mcp-currency` antes da soma.

`activity_cost` usa uma tabela fixa de custo por categoria (o
`ActivityResult` não carrega preço — `mcp-places` é um catálogo de
pontos de interesse, não uma API de preços) e `food_estimate`/
`transport_estimate` são heurísticas explícitas (os nomes dos campos no
schema já dizem "estimate", não "cost") — nada aqui finge ser um preço
real de mercado.

## Dois caminhos de execução

- **Determinístico (padrão, sem `CREWAI_LLM_MODEL`)**: só usa os MCPs
  Currency/Calculator e a lógica acima. É o caminho testado
  automaticamente e o que roda em `docker compose up` sem custo.
- **Guiado por CrewAI (`CREWAI_LLM_MODEL` setada)**: rodaria um `Crew`
  com um `Agent`/`Task` usando os mesmos MCPs como tools. Ver ADR-012.
  Não é exercitado pelos testes automatizados desta milestone; qualquer
  falha cai automaticamente para o determinístico.

Se um componente (voo/hotel/atividade) estiver indisponível, seu custo
vira zero e é anotado em `notes` — nunca bloqueia o restante do cálculo.
Sem `budget_limit`, `status`/`budget_status` ficam `UNKNOWN`.

## Skills

```text
calculate_budget
optimize_budget
```

`optimize_budget` está declarada no Agent Card (skill opcional do §5.5),
mas sem lógica própria ainda nesta milestone.

## Endpoints

- `GET /health`, `GET /ready`
- `GET /.well-known/agent-card.json`
- `POST /a2a` (A2A JSON-RPC, mesmo adapter dos outros agentes Python)

## Rodando localmente

```bash
pip install -e .
uvicorn app.main:app --reload --port 8005
```

## Testes

```bash
pip install -e . pytest
pytest -q
```
