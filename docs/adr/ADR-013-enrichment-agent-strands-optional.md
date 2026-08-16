# ADR-013 — AWS Enrichment Agent: caminho determinístico por padrão, Strands opcional

## Status
Aceito

## Contexto
PROJECT_SPEC.md §5.6 exige o AWS Enrichment Agent em AWS Strands Agents
SDK, com responsabilidade reduzida (weather commentary, destination tips,
short recommendations) e explicitamente `OPTIONAL` — "O sistema deverá
funcionar sem este agente" — e nunca no caminho crítico (§11: "AWS
Enrichment indisponível: Ignorar. Não marcar o fluxo como falha."). A
mesma tensão entre "framework obrigatório pelo spec" e RNF-03 ("modo
padrão não exige API paga") já resolvida em ADR-009 (Flight/OpenAI Agents
SDK), ADR-011 (Activity/BeeAI) e ADR-012 (Budget/CrewAI) se repete aqui
para o quarto e último especialista real desta POC.

## Decisão
`agents/aws-strands` implementa dois caminhos, dentro do próprio agente:

- **Determinístico (padrão, sem `MODEL_PROVIDER` ou valor
  desconhecido)**: `weather_summary` vem de uma chamada real ao
  `mcp-weather` (mesma ferramenta e mesmo padrão de degradação que o
  Activity Agent já usa — nunca inventa previsão, §31);
  `destination_tips` vem de uma tabela fixa de dicas por tag de
  preferência do viajante (`app/agent.py::_TIP_TABLE`), mais uma dica
  genérica com o destino no template quando nenhuma preferência combina.
  É o caminho testado automaticamente e o que roda em `docker compose
  up`/`AWS_AGENT_ENABLED=false` sem custo.
- **Guiado por Strands (`MODEL_PROVIDER=ollama` ou
  `MODEL_PROVIDER=bedrock`)**: usa `strands.Agent` com `OllamaModel`
  (local) ou `BedrockModel`, para transformar o forecast real (ainda via
  MCP Weather — o modelo nunca inventa o clima) em comentário e dicas
  mais elaboradas. Qualquer falha nesse caminho cai automaticamente para
  o determinístico — mesmo padrão de fallback do Flight/Activity/Budget
  Agent, e reforça a regra do próprio §5.6/§11 de que este agente nunca
  pode bloquear o Planner.

Isso mapeia diretamente para os três modos descritos no §5.6:

```text
Local:    Strands -> Ollama              (AWS_AGENT_ENABLED=true, MODEL_PROVIDER=ollama)
AWS Lite: Strands -> Amazon Bedrock      (AWS_AGENT_ENABLED=true, MODEL_PROVIDER=bedrock)
AWS Full: AgentCore Runtime -> Strands -> Bedrock   (fase futura, fora desta milestone)
```

## Dois níveis de "opcional"
Diferente de Flight/Activity/Budget (sempre chamados pelo Planner, cada
um com seu próprio caminho determinístico-vs-LLM interno), o Enrichment
Agent tem opcionalidade em dois níveis:

1. **Se o Planner chama o agente, ponto**: controlado por
   `AWS_AGENT_ENABLED` (lido pelo Planner). `false` (padrão) → o Planner
   nem tenta descobrir o skill `enrich_destination` — resposta sempre
   `enrichment.status: SKIPPED`, nunca afeta `overall_status`
   (`planner-adk/app/agent.py::handle_travel_request` já excluía
   `enrichment` do cálculo de `COMPLETED`/`PARTIAL`/`FAILED` desde a
   Fase 5). Isso satisfaz o critério de aceite §37 "agente AWS puder
   ficar desligado" e §38 "pode ser removido sem quebrar sistema".
2. **Se o agente é chamado, qual motor gera as dicas**: controlado pelo
   `MODEL_PROVIDER` deste próprio agente (determinístico vs. Strands),
   igual ao padrão dos outros três.

Ativar o profile AWS (`make aws-local` / `make aws-lite`, ambos já
declarados no `Makefile` antes desta fase) não exige nenhuma mudança no
código do Planner (§37: "ativar o profile AWS não exigir alteração no
código do Planner") — a descoberta já é dinâmica por skill via Agent Card
(§9, desde a revisão da Fase 5), então bastou registrar
`aws-enrichment-agent` em `infrastructure/registry/agents.json` e
adicionar o serviço (+ `ollama`) ao `docker-compose.yml` atrás de
`profiles: ["aws"]`.

## Por que `destination_tips` não viola §31 ("nunca fabricar dado")
As dicas do caminho determinístico são conselhos de viagem genéricos e
template-based (ex.: "leve protetor solar"), nunca uma alegação
específica e factual sobre o destino apresentada como se fosse real — a
mesma lógica já aplicada a `budget-agent`'s `_ACTIVITY_COST_TABLE` (ADR-012)
e aos nomes de lugares mock do Activity Agent. O `weather_summary`, esse
sim uma alegação factual, vem sempre do MCP Weather real (mock
determinístico, mas nunca inventado pelo próprio agente) em ambos os
caminhos.

## Consequências
- `contracts/schemas/enrichment-result.schema.json` já tinha
  `weather_summary`/`destination_tips`, mas o modelo Pydantic
  `EnrichmentResult` em `agents/planner-adk/app/schemas.py` só tinha
  `status`/`provider` — foi ampliado para incluir os dois campos,
  senão `_parse_specialist_result` os descartaria silenciosamente
  (`model_validate` ignora campos não declarados por padrão no Pydantic
  v2) mesmo numa resposta `SUCCESS` real do agente.
- `strands-agents` é declarado apenas como dependência opcional
  (`[project.optional-dependencies].strands`) e só é instalado na imagem
  Docker via `ARG INSTALL_STRANDS=true` — mesma escolha do CrewAI em
  ADR-012.
- O caminho guiado por Strands não é exercitado pelos testes
  automatizados desta milestone (nenhum Ollama/Bedrock real no ambiente
  de desenvolvimento/CI — §39 "Não executar Bedrock por padrão na CI").
  Antes de depender dele, validar manualmente com um provider real.
- `AgentCore` (§5.6 "AWS Full") permanece fora de escopo desta milestone,
  como já indicado em §38 "AgentCore — fase futura".
