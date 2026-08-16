# ADR-011 — Activity Agent: caminho determinístico por padrão, BeeAI opcional

## Status
Aceito

## Contexto
PROJECT_SPEC.md §5.4 exige o Activity Agent em BeeAI Framework. RNF-03
exige que o modo padrão não exija nenhuma API paga. Essas duas exigências
só coexistem se a camada de raciocínio via LLM (que o BeeAI orquestraria
através de um `ReActAgent`) for opcional — exatamente a mesma tensão já
resolvida para o Flight Agent em ADR-009, aqui generalizada para um
terceiro framework/linguagem.

## Decisão
`agents/activity-beeai` implementa dois caminhos:

- **Determinístico (padrão, sem `BEEAI_CHAT_MODEL`)**: chama
  `mcp-places` uma vez para obter o pool de pontos de interesse do
  destino, chama `mcp-weather` uma vez por dia da viagem, e monta o
  roteiro com uma heurística fixa (2 atividades por dia, em horários
  `09:00`/`14:00`, sem sobreposição, priorizando categorias que casam com
  `preferences`). É o caminho testado automaticamente (`tests/`) e o que
  roda em `docker compose up` sem custo.
- **Guiado por BeeAI (`BEEAI_CHAT_MODEL` setada)**: usaria
  `beeai_framework.agents.react.ReActAgent` com MCP Places e MCP Weather
  encapsulados como `Tool`s do BeeAI, deixando o modelo decidir a
  sequência do dia. Qualquer falha nesse caminho cai automaticamente para
  o determinístico — mesmo padrão de fallback do Flight Agent.

Em ambos os casos, nenhum lugar ou previsão é inventado (§31): toda
atividade retornada vem de uma chamada real a `search_places` via MCP, e
todo campo `weather` (quando presente) vem de uma chamada real a
`get_weather` via MCP.

## Falha do MCP Weather não bloqueia o roteiro (§5.4 / CT-R03)
Diferente do MCP Places (cuja indisponibilidade degrada o `ActivityResult`
inteiro para `UNAVAILABLE`, já que sem lugares não há roteiro possível), a
falha do MCP Weather é tratada por dia: aquele dia específico recebe
`weather: null` e o roteiro continua normalmente — implementado em
`_fetch_weather()`, que nunca propaga a exceção do MCP Weather para o
restante do fluxo. Isso implementa diretamente o requisito "permitir
execução sem informação meteorológica" (§5.4) e o cenário de resiliência
CT-R03 do §35 (a suíte de testes de resiliência formal é Fase 8; este
comportório já é coberto por
`agents/activity-beeai/tests/test_agent.py::test_weather_unavailable_still_returns_success`).

## Consequências
- O caminho guiado por BeeAI não é exercitado pelos testes automatizados
  desta milestone (nenhum backend de chat configurado no ambiente de
  desenvolvimento). Antes de depender dele, validar manualmente com um
  backend real (`ChatModel.from_name(...)`, qualquer provider suportado
  pelo BeeAI).
- O contrato A2A (skill `plan_activities`, mensagem de entrada/saída) é o
  mesmo nos dois caminhos — trocar de determinístico para BeeAI não quebra
  o Planner nem os testes de contrato.
- `beeai-framework` é declarado apenas como dependência opcional
  (`[project.optional-dependencies].beeai` em `pyproject.toml`) e não é
  instalado na imagem Docker padrão, mantendo a imagem enxuta enquanto o
  caminho determinístico for o único exercitado em CI/dev.
