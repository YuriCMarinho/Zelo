# SmartRepair Backend

O Nó S procura prestadores por categoria e região. A fonte padrão é `agent_browser`:
o Agent Browser da Vercel abre o Google Maps e extrai nome, telefone público e avaliação
dos resultados exibidos. Não precisa de chave da Google Places API. Só prestadores
que confirmam o contato entram na tabela `providers` com `is_validated=true`.
Cada coleta grava eventos de auditoria com `run_id` próprio. O job APScheduler roda
a cada 12 horas por padrão; o fallback do Nó 3 pode chamar
`collect_on_demand(db, category, region)`.

Instale o navegador a partir da raiz do projeto:

```bash
npm ci --prefix backend/browser
backend/browser/node_modules/.bin/agent-browser install
```

O Dockerfile já inclui o Agent Browser e o Chromium. Para usar um Chrome instalado
localmente, configure `AGENT_BROWSER_EXECUTABLE_PATH` no `backend/.env`.
`AGENT_BROWSER_COMMAND` permite apontar para outro executável do Agent Browser.

Para demonstrar a busca real, sem enviar mensagens nem cadastrar prestadores:

```bash
cd backend
uv run python scripts/search_providers.py --category plumber --region "Fortaleza, CE" --limit 3
```

O comando mostra nome, avaliação, telefone mascarado e link público de origem.
Usa o banco para registrar a tentativa e respeitar `MAX_BROWSER_SEARCHES` (50 tentativas
acumuladas por padrão, inclusive após reiniciar). A busca lê até os primeiros 50 cards
carregados na página, sem paginação; resultados sem telefone são descartados.
Cada busca tem uma sessão isolada, encerrada no final. Timeouts, CAPTCHA e consentimento
pendente geram erro explícito; nunca são substituídos por prestadores inventados.

Para testes sem internet, configure `PROVIDER_SOURCE=fixture`: dois candidatos artificiais
por busca, um confirma e outro recusa. `LLM_MODE=recorded_demo` também força fixture.

```bash
uv sync --dev
uv run uvicorn app.main:app --reload
```

O Nó 3 guarda as pausas (espera de orçamentos, do ADM e do prestador) no Postgres via `AsyncPostgresSaver`. **No Windows**, o psycopg assíncrono não funciona no loop padrão do uvicorn; rode com:

```bash
uv run uvicorn app.main:app --reload --loop asyncio:SelectorEventLoop
```

Sem isso o backend sobe, mas avisa no log e usa memória: uma aprovação pendente se perde ao reiniciar. Se houver um Postgres instalado no Windows ocupando a porta 5432, o backend conecta nele e não no container; pare o serviço local ou aponte `DATABASE_URL` para outra porta.

`GET /api/providers` lista somente prestadores validados e mascara o telefone. `POST /api/providers/collect` aciona o fallback manual em `development` e `testing`; em produção o Nó 3 usa a função de serviço.

O envio de validação continua **simulado**: configure `PROVIDER_CONTACT_ALLOWLIST` com
números no formato `+5585988881234`, separados por vírgula, e `PROVIDER_SIMULATED_REPLIES`
como JSON do ID retornado na busca para a resposta, por exemplo
`{"maps:0xabc:0x123":"Sim, confirmo."}`. Sem número na allowlist ou sem resposta
afirmativa, o candidato não é ativado. Nenhum SMS ou WhatsApp real é enviado.

O adaptador legado da Places API continua disponível opcionalmente com
`PROVIDER_SOURCE=google_places` e `GOOGLE_PLACES_API_KEY`, mas não é necessário para
a coleta pelo navegador. Referência: [Agent Browser da Vercel](https://github.com/vercel-labs/agent-browser).
