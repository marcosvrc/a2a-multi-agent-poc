# Revisão de segurança — a2a-multi-agent-poc

Data: 2026-08-16. Escopo: código versionado + histórico git + configuração
Docker/compose. Contexto avaliado: **POC de desenvolvimento local** — a
severidade abaixo considera esse contexto; vários pontos seriam críticos em
produção mas são risco aceito (e documentado) numa POC que roda em
`localhost`.

## O que já está correto (verificado, não assumido)

- **Nenhum segredo real no repositório nem no histórico completo do git**
  (varrido: padrões de chave OpenAI/AWS/GitHub/Slack e blocos de chave
  privada, em todos os commits de todos os branches). `.env` está no
  `.gitignore` e nunca foi commitado.
- **Nenhum `eval`/`exec`** — o MCP Calculator expõe só quatro operações
  binárias fixas, cumprindo a restrição explícita do spec (§33).
- **JWT com algoritmo fixado** (`algorithms=["HS256"]` no decode) — sem
  vulnerabilidade de *algorithm confusion* (`alg: none`).
- **Agent Registry é somente leitura** (só rotas `GET`) — não existe
  endpoint de registro aberto que permitisse a um atacante injetar um
  agente falso na descoberta dinâmica.
- **web-ui escapa a saída** (`esc()`) em todos os pontos de interpolação —
  um ponto faltante (fallback de `money()`) foi encontrado nesta revisão e
  já corrigido.
- **Loop de dias do Activity Agent é limitado** (`max_days`) — um range de
  datas absurdo (`end_date: 9999-12-31`) não gera DoS por iteração.
- **Resposta do LLM validada antes de propagar** (fix recente do
  `status: "OK"`) — saída de modelo não é mais confiada cegamente.
- **Validação de payload via Pydantic** com `additionalProperties`
  controlado nos schemas de contrato.

## Achados — ordenados por relevância prática

### 1. `POST /v1/travel-requests` aberto + CORS `*` + caminho LLM pago ativo — MÉDIO (o mais concreto)

A rota pública do Planner não tem autenticação nem rate limiting, e o CORS
`allow_origins=["*"]` permite que **qualquer página web** que você visitar
dispare requisições a `localhost:8001` pelo seu navegador. Antes isso era
inofensivo (tudo mock); agora que `OPENAI_API_KEY` está ativa, **cada
requisição gasta crédito real da sua conta OpenAI** — um site malicioso
poderia drenar créditos em loop enquanto a stack estiver de pé.

Mitigação sugerida (mantendo a conveniência do web-ui):
- Trocar `allow_origins=["*"]` por uma lista explícita
  (`["http://localhost:8010", "null"]` — a origem do seu static server e a
  origem `file://`).
- Opcional: um rate limit simples (ex.: `slowapi`, N req/min por IP).
- Hábito: derrubar a stack (`docker compose down`) quando não estiver
  testando com a chave ativa.

### 2. Portas de todos os serviços internos publicadas no host — MÉDIO

Todos os 18 serviços publicam porta no host (`ports:`), incluindo os seis
MCP servers (9001–9006, **sem nenhuma autenticação por design**), o
Registry (8080) e o OTLP collector (4317/4318). Qualquer dispositivo na
mesma rede local alcança tudo isso. Só o Planner (8001) e o Jaeger UI
(16686) precisam de porta no host para o uso normal.

Mitigação: remover `ports:` dos serviços internos (a rede interna do
compose já resolve a comunicação entre containers), ou prefixar com
loopback: `"127.0.0.1:9001:9001"`.

### 3. Containers rodam como root — MÉDIO

Nenhum Dockerfile define `USER` — todos os 18 containers rodam como root.
Numa POC local o impacto é contido, mas é o hardening de melhor
custo-benefício: criar um usuário sem privilégio em cada Dockerfile
(`RUN adduser --system app && USER app`) limita o estrago de qualquer RCE
futura em dependência.

### 4. Modo `jwt`: claims não obrigatórias e segredo compartilhado — MÉDIO (documentado no ADR-015)

Dois pontos no `verify_request`:
- `jwt.decode` não exige claims: um JWT **sem `exp`** é aceito para sempre,
  e `sub` ausente vira identidade `None`. Fix de uma linha:
  `options={"require": ["exp", "sub"]}`.
- O segredo HS256 é compartilhado por todos os agentes — qualquer agente
  pode forjar um token com o `sub` de outro (identidade auto-declarada).
  Isso já está honestamente documentado no ADR-015 como limitação do spike;
  a evolução seria chave assimétrica (RS256) ou segredo por agente.

### 5. Comparação de token em modo `dev` não é constant-time — BAIXO

`token != dev_token` (7 arquivos `auth.py` + `auth.ts`) é vulnerável em
teoria a timing attack. O próprio código documenta a escolha como aceitável
para dev. Fix trivial se quiser fechar: `hmac.compare_digest(token,
dev_token)` em Python e `crypto.timingSafeEqual` no TypeScript.

### 6. Strings do `TravelRequest` sem limite de tamanho — BAIXO

`origin`, `destination`, `currency` e `preferences` não têm `max_length` —
um payload de megabytes passa pela validação e se propaga para todos os
agentes e logs. Sugestão: `Field(max_length=100)` nos campos de texto e
`max_length=20` na lista de preferências.

### 7. Detalhe de erro de JWT vazado na resposta 401 — INFO

`detail=f"invalid JWT: {exc}"` devolve ao chamador o motivo exato da
rejeição (expirado vs. assinatura inválida), o que ajuda um atacante a
calibrar tentativas. Em produção, responder um 401 genérico e logar o
motivo só do lado servidor.

### 8. Higiene contínua de dependências — INFO

Versões estão pinadas (bom para reprodutibilidade), mas não há verificação
automática de CVE. Sugestão: rodar `pip-audit` (Python) e `npm audit`
(hotel-langgraph) periodicamente ou num job de CI.

## Correção já aplicada nesta revisão

`web-ui/index.html::money()` — o ramo de fallback (executado justamente
quando `currency` não é um código ISO válido, ou seja, quando o valor é
imprevisível) concatenava `currency` no `innerHTML` sem escapar: um agente
comprometido/mal-comportado que devolvesse uma string maliciosa no campo
`currency` executaria script no navegador. Corrigido com `esc(currency)`.

## Prioridade sugerida

Para o seu uso atual (testes locais com chave OpenAI ativa), a ordem de
valor é: **1** (protege seu dinheiro) → **2** (tira os serviços sem auth da
rede local) → **4** (`options={"require": [...]}` é uma linha) → **3/5/6**
quando houver tempo. Os itens INFO são hábito, não urgência.
