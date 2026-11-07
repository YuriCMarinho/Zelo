# SmartRepair Backend

O Nó S procura prestadores por categoria e região. Por padrão, usa dois candidatos artificiais por busca: um confirma o contato e outro recusa. Só o confirmado entra na tabela `providers` com `is_validated=true`. Cada coleta grava eventos de auditoria com `run_id` próprio. O job APScheduler roda a cada 12 horas por padrão; o fallback do Nó 3 pode chamar `collect_on_demand(db, category, region)`.

```bash
uv sync --dev
uv run uvicorn app.main:app --reload
```

`GET /api/providers` lista somente prestadores validados e mascara o telefone. `POST /api/providers/collect` aciona o fallback manual em `development` e `testing`; em produção o Nó 3 usa a função de serviço.

Para usar a Places API (New), configure `PROVIDER_SOURCE=google_places` e `GOOGLE_PLACES_API_KEY`. O adaptador solicita apenas ID, nome, telefone e avaliação. O envio de validação continua **simulado**: configure `PROVIDER_CONTACT_ALLOWLIST` com números separados por vírgula e `PROVIDER_SIMULATED_REPLIES` como JSON de `place_id` para resposta, por exemplo `{"places-123":"Sim, confirmo."}`. Sem número na allowlist ou sem resposta afirmativa, o candidato não é ativado. Nenhum SMS ou WhatsApp real é enviado.
