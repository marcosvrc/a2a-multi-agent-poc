# ADR-012 — Budget Agent: caminho determinístico por padrão, CrewAI opcional

## Status
Aceito

## Contexto
PROJECT_SPEC.md §5.5 exige o Budget Agent em CrewAI. RNF-03 exige que o
modo padrão não exija nenhuma API paga. A mesma tensão já resolvida em
ADR-009 (Flight/OpenAI Agents SDK) e ADR-011 (Activity/BeeAI) se repete
aqui para o terceiro e último framework de especialista desta POC.

## Decisão
`agents/budget-crewai` implementa dois caminhos:

- **Determinístico (padrão, sem `CREWAI_LLM_MODEL`)**: extrai
  `flight_cost`/`hotel_cost`/`activity_cost` dos resultados já obtidos
  pelo Planner, soma `food_estimate`/`transport_estimate` heurísticos, e
  combina tudo exclusivamente via chamadas a `mcp-calculator`
  (`sum`/`subtract`/`multiply`) — nunca uma expressão livre avaliada
  localmente (§33: "Não permitir expressão arbitrária executada via
  eval"). Quando a moeda do viajante difere de BRL, cada componente passa
  por `mcp-currency` antes da soma. É o caminho testado automaticamente
  e o que roda em `docker compose up` sem custo.
- **Guiado por CrewAI (`CREWAI_LLM_MODEL` setada)**: rodaria um `Crew`
  com um único `Agent`/`Task`, usando os mesmos MCPs de Currency/
  Calculator encapsulados como tools do CrewAI. Qualquer falha nesse
  caminho cai automaticamente para o determinístico — mesmo padrão de
  fallback do Flight e do Activity Agent.

## Por que o Budget Agent é delegado separadamente (não no fan-out genérico)
Diferente de flight/hotel/activity — que recebem o `TravelRequest` bruto
e fazem sua própria busca —, o Budget Agent não busca nada: ele só soma o
que os outros três já encontraram (§5.5: "Receber: voo; hotel;
atividades; orçamento máximo."). Por isso `planner-adk/app/agent.py`
delega o Budget Agent numa etapa própria (`_delegate_budget`), *depois*
de `flight`/`hotel`/`activities` já terem sido parseados — é o único
especialista cuja delegação é sequenciada em vez de disparada junto com
o resto no laço `DELEGATING`. O payload enviado a ele inclui os três
`*Result` já serializados, mais `budget_limit`, `currency`, `travelers` e
`nights` (calculado a partir de `start_date`/`end_date`).

## `activity_cost` não é um preço real
O `ActivityResult` não carrega preço (`mcp-places` é um catálogo de
pontos de interesse, não uma API de preços), então `activity_cost` usa
uma tabela fixa de custo por categoria, documentada em
`agents/budget-crewai/app/agent.py::_ACTIVITY_COST_TABLE` — análoga à
tabela de duração usada em `mcp/places/app/mock_data.py`. Isso não viola
§31 (nunca inventar dados): a tabela é uma estimativa heurística
declarada como tal, nunca apresentada como um preço de mercado real —
exatamente como `food_estimate`/`transport_estimate`, cujos próprios
nomes no schema já dizem "estimate", não "cost".

## Consequências
- Com os quatro especialistas centrais (flight/hotel/activity/budget)
  reais, `planner-adk/app/agent.py::handle_travel_request` agora pode
  retornar `status: COMPLETED` (antes sempre `PARTIAL`, já que
  `budget_status` nunca saía de `UNKNOWN`) — a lógica de consolidação foi
  atualizada para `COMPLETED` apenas quando os quatro `SUCCESS`,
  ignorando `enrichment` (opcional, §5.6, nunca bloqueia `COMPLETED`).
- O caminho guiado por CrewAI não é exercitado pelos testes automatizados
  desta milestone (nenhum backend de chat configurado no ambiente de
  desenvolvimento). Antes de depender dele, validar manualmente com um
  backend real.
- `crewai` é declarado apenas como dependência opcional
  (`[project.optional-dependencies].crewai`) e não é instalado na imagem
  Docker padrão — mesma escolha do BeeAI em ADR-011.
- `contracts/schemas/budget-result.schema.json` ganhou um campo `notes`
  (ausente até aqui, diferente de `flight-result`/`hotel-result`/
  `activity-result`, que já tinham) para poder registrar quais
  componentes foram tratados como zero por indisponibilidade — sem essa
  adição, `additionalProperties: false` rejeitaria a resposta.

## Addendum — bug encontrado ao validar manualmente (exatamente o alerta acima)

Ao configurar o caminho guiado pela primeira vez com um backend real, foi
encontrado um bug: `CREWAI_LLM_MODEL` só controlava **se** o caminho
guiado rodava (`build_budget_result`), mas o valor nunca era passado para
o `Agent()` do CrewAI em `_build_via_crewai` — toda execução guiada usava
o LLM default do CrewAI (OpenAI), ignorando silenciosamente o modelo
configurado pelo operador. Corrigido construindo um `crewai.LLM(model=...,
base_url=...)` explícito e passando-o como `Agent(..., llm=budget_llm)`;
`base_url` só é setado quando o modelo começa com `"ollama/"` (convenção
LiteLLM), lido de `OLLAMA_API_BASE` (`config.py::crewai_llm_base_url`,
mesmo nome de variável que o adapter Ollama do BeeAI já lê por convenção
própria — ver ADR-011).

Dockerfile também não instalava `crewai` em nenhuma circunstância —
`INSTALL_CREWAI` era só um `ARG` sem eco em `docker-compose.yml`. Agora
`docker-compose.yml` propaga `INSTALL_CREWAI` do `.env` para o build arg;
o valor precisa ser `true` **e a imagem rebuildada**
(`docker compose build budget-agent`) para o caminho guiado sair do
fallback silencioso.

Dois testes novos (`agents/budget-crewai/tests/test_agent.py`) travam
essa regressão: um stub de `crewai` em `sys.modules` verifica que
`Agent()` recebe o `LLM` correto (`test_crewai_llm_model_is_wired_into_the_agent`)
e que o `base_url` só é setado para modelos Ollama
(`test_crewai_ollama_model_passes_base_url`).
