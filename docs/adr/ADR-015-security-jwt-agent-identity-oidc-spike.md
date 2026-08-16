# ADR-015 — Segurança: bearer token na rota /a2a, identidade de agente via JWT, spike de OAuth/OIDC

## Status
Aceito

## Contexto
PROJECT_SPEC.md §7 lista "Security" como marco M6 e §56 pede
explicitamente: autenticação service-to-service em toda chamada A2A,
alguma noção de "identidade do agente" (não só "algum token válido"), e
um "spike" de OAuth/OIDC — não uma integração completa contra um IdP
externo real, e sim o desenho da abordagem mais uma prova de conceito
mínima que já funcione. Até a Fase 8, qualquer processo na rede
`agent-net` conseguia enviar `POST /a2a` para qualquer agente e ser
atendido — a Fase 6/8 tratavam falhas de rede e indisponibilidade, nunca
quem estava do outro lado da chamada.

## Decisão

### 1. Três modos, controlados por `AUTH_MODE`
`app/auth.py` (mirror em `src/a2a/auth.ts` para o hotel-agent em
TypeScript) implementa três modos, com `verify_request`/`mint_outgoing_token`
como par simétrico — quem gera o token de saída usa exatamente a mesma
lógica de quem valida o token de entrada:

- `"dev"` (default, igual ao spec) — bearer token estático compartilhado
  (`DEV_AGENT_TOKEN`). Simples, adequado para desenvolvimento local e para
  a topologia fixa desta POC (todos os agentes rodam na mesma rede
  Docker/host, configurados a partir do mesmo `.env`).
- `"jwt"` — JWT assinado HS256 com segredo compartilhado (`JWT_SECRET`).
  A claim `sub` carrega o `service_name` de quem está chamando
  (`mint_outgoing_token(..., agent_id=settings.service_name)`), dando ao
  lado que recebe uma **identidade do chamador**, não só um "sim/não"
  binário — é essa claim que atende ao pedido do §56 por identidade de
  agente, indo além de um shared secret puro.
- `"none"` — sem verificação nenhuma. Existe só para testes/debug local
  isolado (ex.: rodar um único agente fora do stack, com `curl` manual,
  sem precisar montar um token). **Nunca** é o default em nenhum
  ambiente — `AUTH_MODE` sempre precisa ser setado explicitamente para
  `"none"`, o que já serve como barreira contra uso acidental em
  produção.

### 2. Por que HS256 com segredo compartilhado, não um IdP externo real
Um IdP OAuth2/OIDC completo (client credentials grant, JWKS, rotação de
chave assimétrica, `iss`/`aud` validados contra um servidor de
autorização real) é a solução correta para um sistema multi-tenant em
produção, mas está fora do escopo de uma POC de 6 agentes rodando na
mesma máquina/rede Docker: não há um IdP já disponível no stack, subir um
(Keycloak, Auth0 local, etc.) só para esta fase adicionaria uma peça de
infraestrutura inteira sem mudar nenhuma das propriedades de segurança
que o §56 pede provar (autenticação por chamada + identidade do
chamador). HS256 com segredo compartilhado entrega as duas com uma
fração da complexidade, e o "spike" pedido pelo §56 é justamente isso:
desenho da abordagem completa (documentado aqui) + a menor prova de
conceito que já funciona de ponta a ponta — mesmo padrão de
escopo-deliberadamente-reduzido já usado em ADR-005 ("AWS Agent
Optional") e ADR-013 ("AgentCore — fase futura"). Migrar para RS256 +
JWKS + um IdP real é o caminho natural caso este sistema saia de POC,
mas não muda nenhuma das interfaces (`verify_request`/
`mint_outgoing_token`) — só a implementação de como o segredo/chave é
obtido.

### 3. Só a rota `/a2a` é protegida
`/health`, `/ready` e `/.well-known/agent-card.json` continuam **abertos**,
em todos os agentes, deliberadamente:

- Agent Card discovery (§9) precisa funcionar antes de qualquer chamador
  ter um token — é o próprio mecanismo pelo qual o Planner descobre a URL
  e as skills de um especialista antes de falar com ele.
- Health/readiness checks (usados por `docker-compose`'s
  `condition: service_healthy` no `agent-registry`, e por qualquer
  orquestrador real) não devem depender de credenciais — um check de
  liveness que exige auth é um risco operacional clássico (não dá para
  diagnosticar "o serviço está de pé?" se a checagem em si pode falhar
  por token expirado).
- Nenhuma das duas rotas expõe dado de negócio ou executa uma ação — só
  metadados públicos do próprio agente.

### 4. `agent-registry` continua sem autenticação
O Registry (`infrastructure/registry`) não ganhou nenhum gate nesta fase.
Decisão implícita até agora, explicitada aqui: o Registry só armazena e
devolve Agent Cards (mesma natureza pública que `/.well-known/agent-card.json`
já tem em cada agente individualmente) — não há chamada ao Registry que
delegue trabalho ou custe dinheiro (diferente de `/a2a`, que aciona um
LLM/MCP real). Proteger o Registry fica fora do escopo desta fase; se
viesse a ser necessário, o mesmo par `verify_request`/`mint_outgoing_token`
se aplicaria sem mudança de desenho.

### 5. Retry/circuit breaker (Fase 8) compostos com auth (Fase 9)
Um 401 do `/a2a` é um `HTTPStatusError` com status `< 500` — pela regra já
estabelecida na ADR-014, **nunca é retryable** (o outro lado rejeitou a
requisição deliberadamente). Um agente mal configurado (token errado)
ou de fato sem credencial válida degrada exatamente como qualquer outro
4xx: vira `UNAVAILABLE` (ou `UNKNOWN` para budget, CT-R06) depois da
primeira tentativa, e passa a contar como falha para o circuit breaker
daquele `agent_id` como qualquer outra indisponibilidade real. Nenhuma
mudança foi necessária no cliente A2A para isso — o desenho da Fase 8 já
cobria esse caso.

## Consequências
- `pyjwt==2.10.1` (Python, todos os 6 agentes) e `jsonwebtoken@^9.0.2`
  (`hotel-langgraph`, TypeScript) são novas dependências.
- Novos testes: `agents/planner-adk/tests/test_auth.py` (15 testes,
  unitários, cobrindo os três modos) e
  `agents/planner-adk/tests/test_a2a_route_auth.py` (5 testes de
  integração contra o FastAPI `app` real, provando que `/health`/`/ready`/
  agent-card continuam abertos e que `/a2a` rejeita/aceita de acordo com
  o token) — implementados uma vez em `planner-adk` como referência
  canônica, mesmo padrão já usado na ADR-014 para `test_mcp_client.py`.
  Os outros 5 agentes Python tiveram suas suítes de teste existentes
  atualizadas para autenticar (`TestClient(app, headers={...})`), sem
  suítes de auth dedicadas próprias. `hotel-langgraph` ganhou
  `test/auth.test.ts` (11 testes) por ser a única implementação em outra
  linguagem, sem um par Python para servir de referência.
- Todo `uvicorn --reload`/`npx tsx` manual fora do Docker (ver
  `docs/local-development.md`) agora precisa de
  `Authorization: Bearer <DEV_AGENT_TOKEN>` em qualquer `curl` direto a
  `/a2a` — `/health`/`/ready`/agent-card continuam acessíveis sem header.
- `docker-compose.yml` passa `AUTH_MODE`/`DEV_AGENT_TOKEN`/`JWT_SECRET`
  (com os mesmos defaults de desenvolvimento de `config.py`/`config.ts`)
  para os 7 serviços de agente (6 Python + hotel-agent); os serviços MCP,
  o Registry, o collector OTel e o Jaeger não recebem essas variáveis por
  não exporem `/a2a`.
- `JWT_SECRET=local-development-only-change-me` e
  `DEV_AGENT_TOKEN=local-development-only` em `.env.example` são valores
  claramente fake, nunca segredos reais — nenhum outro valor de segredo
  real é ou deve ser commitado neste repositório.
- Rotação de token/segredo, revogação, `AUTH_MODE=jwt` com chave
  assimétrica e um IdP externo real permanecem fora de escopo desta POC,
  documentados aqui como o caminho de evolução natural caso o sistema
  deixe de ser uma POC.
