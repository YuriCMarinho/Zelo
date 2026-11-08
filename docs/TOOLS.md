# Ferramentas e modelos — Zelo

Inventário da implementação em 2026-11-08. Versões exatas das dependências estão em `backend/uv.lock` e `frontend/package-lock.json`.

## Produto

| Ferramenta | Uso no projeto | Situação |
| --- | --- | --- |
| Python 3.12, FastAPI e Uvicorn | API HTTP, chat, chamados, aprovação e respostas do prestador | Implementado. |
| Pydantic v2 / pydantic-settings | Contratos, validação e configuração por ambiente | Implementado. |
| SQLAlchemy e psycopg | Persistência e acesso ao PostgreSQL | Implementado; SQLite temporário é usado em testes e smoke da contingência. |
| PostgreSQL | Imóveis, reservas, prestadores, chamados, orçamentos, auditoria, custos e checkpoints | Implementado. |
| LangGraph / langgraph-checkpoint-postgres | Fluxo de manutenção, pausas e retomadas por decisões externas | Implementado; fallback de checkpoint em memória quando o PostgreSQL não está disponível. |
| APScheduler | Coleta periódica e timers de espera/lembretes | Implementado; timers atuais não são restaurados após reinício. |
| HTTPX | Cliente de inferência Featherless e adaptador de busca | Implementado. |
| React 19, TypeScript 5 e Vite 7 | Interface por imóvel, chat, sessão do anfitrião, calendário e gestão | Implementado. |
| CSS e SVG | Identidade visual Zelo, componentes e logotipo | Implementado; referências locais em `frontend-referencias/`. |
| Featherless | Inferência dos modelos Qwen no modo `featherless` | Integrado; requer chave e créditos. |
| Google Places API | Busca de candidatos a prestadores | Adaptador implementado; depende de configuração. A demo usa `fixture`. |
| Langfuse | Traces e custo de geração | Wrapper implementado; envio externo depende de SDK e credenciais. Sem isso, opera localmente. Não há envio externo em `recorded_demo`. |

## Modelos de IA

| Modelo | Aplicação | Observação |
| --- | --- | --- |
| `Qwen/Qwen3.5-4B` | Roteamento ambíguo, triagem, validação de contato e aviso ao hóspede | Modelo usado em chamadas reais e nas gravações versionadas. |
| `Qwen/Qwen3.5-9B` | Atendimento comercial e orientação comparativa ao anfitrião | Modelo usado em chamadas reais e nas gravações versionadas. |
| `Qwen/Qwen3.5-27B` | Modelo homologado no cliente e na tabela de custos | Permitido, mas não é escolhido automaticamente pelo fluxo atual nem usado nas gravações desta task. |

`mock` gera respostas determinísticas de teste. `recorded_demo` reproduz oito cenários capturados dos modelos, com custo novo de inferência zero. Não é um terceiro modelo nem substitui a resposta do prestador ou a decisão do anfitrião. A captura contém prompts fictícios, origem, modelo, data, tokens, custo e hash do prompt.

## Desenvolvimento, qualidade e entrega

| Ferramenta | Uso |
| --- | --- |
| Git / GitHub | Histórico, branches, integração e hospedagem do código; confirmar acesso da banca. |
| Codex | Assistência de desenvolvimento, revisão de código, documentação e testes nesta implementação. |
| pytest, pytest-asyncio e pytest-cov | Testes de backend, integração, segurança e cobertura. |
| Ruff e mypy | Lint e análise estática do backend. |
| Vitest, Testing Library, user-event e jsdom | Testes da interface e suas interações. |
| ESLint e TypeScript | Lint e checagem de tipos do frontend. |
| uv / npm | Dependências e execução das ferramentas de backend/frontend. |
| Docker / Docker Compose | Empacotamento da aplicação e banco local. |
| Render | Blueprint de deploy preparado; a URL anterior retornou 404 nesta checagem. Não representa um deploy ativo validado. |
| Unsplash | URLs de imagens de demonstração referenciadas no frontend; requerem rede no navegador. |

Os nomes acima descrevem o que está no repositório ou foi usado nesta sessão. Caso o restante do time tenha usado outras ferramentas de IA, design, vídeo ou apresentação, adicionar os nomes antes da submissão final. Não há integração operacional com Airbnb, WhatsApp, pagamento ou envio de mensagens a prestadores reais nesta demo.
