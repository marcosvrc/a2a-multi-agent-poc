# ADR-010 — Hotel Agent em TypeScript: adapter A2A espelhado, não compartilhado

## Status
Aceito

## Contexto
PROJECT_SPEC.md §5.3 exige o Hotel Agent em LangGraph/TypeScript — o
primeiro agente não-Python da POC. A regra 3 do enunciado (reforçada em
ADR-008) proíbe extrair uma biblioteca A2A compartilhada entre as
linguagens: a interoperabilidade tem que ser demonstrada pelo protocolo na
rede (JSON-RPC 2.0 sobre HTTP), nunca por código Python importado em
Node.js (impossível) nem por um pacote npm espelhando implicitamente as
regras internas do adapter Python.

## Decisão
`agents/hotel-langgraph/src/a2a/` reimplementa, em TypeScript puro
(Express + tipos manuais, sem SDK oficial `a2a-sdk`), exatamente o mesmo
contrato de wire do adapter Python usado por `planner-adk` e
`flight-openai`:

- Mesmo endpoint de Agent Card (`/.well-known/agent-card.json`) e mesmo
  formato de `AgentCard`/`AgentSkill`/`AgentCapabilities`.
- Mesmo roteador JSON-RPC 2.0 (`message/send`, `tasks/get`,
  `tasks/cancel`) e os mesmos códigos de erro (`-32602`, `-32001`,
  `-32601`, `-32000`).
- Mesmo modelo de dados (`Message`/`Part`/`Task`/`TaskStatus`/`Artifact`),
  incluindo o formato snake_case na serialização JSON.
- Mesmo `InMemoryTaskStore` simplificado (adequado à POC; substituível por
  persistência real sem alterar o protocolo).

O código em `src/a2a/models.ts` e `src/a2a/server.ts` é uma tradução
linha-a-linha das mesmas decisões documentadas em ADR-008, mantida como
arquivo próprio (não importado de lugar nenhum) precisamente para provar
que dois times, em duas linguagens, podem implementar o protocolo de
forma independente e ainda assim interoperar — o teste real dessa
independência é `tests/e2e/test_fase3_hotel.py`, que passa pelo Planner
(Python) chamando o Hotel Agent (TypeScript) sem nenhum código
compartilhado entre eles além do schema JSON do contrato de domínio
(`contracts/schemas/hotel-result.schema.json`).

## Consequências
- Qualquer mudança de protocolo (novo método JSON-RPC, novo campo em
  `TaskStatus`, etc.) precisa ser replicada manualmente nos dois adapters
  (Python em `agents/*/app/a2a/`, TypeScript em
  `agents/hotel-langgraph/src/a2a/`). Isso é uma escolha deliberada da POC
  (provar interoperabilidade por protocolo), não algo a "corrigir" com
  uma lib compartilhada.
- Futuros agentes em outras linguagens (ex.: Fase 7, AWS Strands) devem
  seguir o mesmo padrão: reimplementar o adapter A2A na linguagem nativa,
  nunca depender de um pacote publicado internamente.
- O cliente MCP TypeScript (`src/mcpClient.ts`) precisou fechar
  explicitamente a conexão SSE por chamada (`client.close()` em `finally`)
  — diferença de runtime em relação ao cliente Python (que usa um
  `async with` equivalente por baixo do SDK oficial `mcp`), documentada
  aqui para não ser reintroduzida como bug em agentes futuros.
