# web-ui — tela de teste manual do Planner

Página estática (HTML + CSS + JS puro, sem build step, sem dependência)
para testar `POST /v1/travel-requests` sem precisar escrever `curl` ou ler
JSON cru. **Não faz parte do caso de uso do projeto** — é só uma
ferramenta de conveniência para QA manual e demo, pensada para não
contradizer a filosofia do resto do repositório (protocolo é a
integração, não framework): não usa React/build tooling, só abre no
browser.

## Rodando

Com a stack já no ar (`make local`, ver README raiz):

```bash
cd web-ui
python3 -m http.server 8090
# abra http://localhost:8090
```

Ou simplesmente abra `index.html` direto no browser (duplo clique /
`open index.html`) — funciona também via `file://`, já que o Planner
tem CORS liberado (`allow_origins=["*"]`, só GET/POST, sem credenciais).

## O que a tela cobre

Um formulário com os mesmos campos do `TravelRequest`
(`contracts/schemas/travel-request.schema.json`) e uma renderização da
resposta consolidada: cartões de voo/hotel, roteiro por dia com clima,
medidor de orçamento (total vs. limite) e as dicas do AWS Enrichment
Agent quando ligado — cada seção com o `status` do especialista
correspondente (`SUCCESS`/`PARTIAL`/`UNAVAILABLE`/`UNKNOWN`/`SKIPPED`).
Um `<details>` no final mostra o JSON completo, para quem quiser
inspecionar o payload bruto. Se `metadata.trace_id` vier na resposta, a
tela já monta o link direto para aquele trace no Jaeger
(`http://localhost:16686`).

## O que não cobre (por design)

Só fala com o Planner (`/v1/travel-requests`), não com os especialistas
individuais via `/a2a` — essa rota é machine-to-machine (JSON-RPC 2.0 +
bearer token, ver [ADR-015](../docs/adr/ADR-015-security-jwt-agent-identity-oidc-spike.md)),
testar cada agente isolado continua sendo trabalho de `curl` com o
header `Authorization: Bearer <token>` (ver `docs/local-development.md`)
ou do Swagger UI de cada agente (`http://localhost:<porta>/docs`, gerado
automaticamente pelo FastAPI — grátis, sem precisar desta tela).

## Por que CORS foi habilitado no Planner

`agents/planner-adk/app/main.py` ganhou `CORSMiddleware` com
`allow_origins=["*"]`, `allow_credentials=False`, restrito a
`GET`/`POST`. Isso é necessário para o browser aceitar a chamada
`fetch()` desta página (que roda numa origem diferente do Planner —
inclusive `file://`, que o browser trata como origem `null`). Não muda
nada de segurança: `/v1/travel-requests` já era uma rota pública (sem
auth) antes desta tela existir, e `/a2a` (a rota autenticada) não foi
tocada — CORS não interfere em chamada agente-a-agente, só em chamada
feita a partir de JavaScript rodando num browser.
