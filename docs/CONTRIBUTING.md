# Contribuição e integração

## Estrutura

`backend/` (FastAPI, Pydantic, serviços), `frontend/` (React/TypeScript), `agents/` (instruções dos três agentes de desenvolvimento), `docs/` (plano, custo, status, submissão), `tests/` (integração, segurança e E2E), `infra/` (configuração e deploy). O protótipo atual permanece em `src/` até a task de migração para `frontend/`; evitar mudanças paralelas nesses arquivos.

## Branches e dono

- `main`: protegida, somente merge aprovado após integração e validação.
- `develop`: integração de PRs aprovados; criar quando o time aceitar o plano.
- Uma task = uma branch = um dev dono e um agente Implementador/Revisor responsável pelo ciclo. Nomes: `feature/<sprint>-<task-id>-<slug>`, `fix/<sprint>-<task-id>-<slug>`, `docs/<sprint>-<task-id>-<slug>`.
- Commits atômicos em Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`). O Revisor faz o commit após o gate da task. PR pequeno para `develop`, rebase em `develop` antes do PR; merge por humano após revisão. Não fazer push direto a `main`.

## Arquivos compartilhados e conflitos

- O Planejador reserva arquivos por task no `PLAN.md`; tasks que tocam o mesmo arquivo não rodam em paralelo.
- Contratos Pydantic, schemas, migrações e configs (incluindo `pyproject.toml`, `package.json`, `vite.config.*`) exigem task dedicada e dono único. Consumidores aguardam o contrato aprovado.
- Em conflito, o dono integra a versão mais recente de `develop`, preserva ambos os comportamentos aceitos, executa testes afetados e pede nova revisão. Nunca resolver com `--ours`/`--theirs` sem inspecionar o diff. Mudança de interface retorna ao Planejador.
- `docs/STATUS.md` é atualizado serialmente pelo dono da transição; combinar o turno de escrita antes de alterar o arquivo. Cada PR informa estado e hash; o Revisor registra a aprovação.

## Definition of Ready global

Task tem objetivo, requisitos, arquivos reservados, dono, branch, dependências aprovadas, aceite testável, custo previsto em `COST.md` quando há LLM, e sprint aprovada pelo Revisor. Segredos e integrações necessárias estão disponíveis como variáveis de ambiente ou há modo simulado aprovado.

## Definition of Done global

Aceite e testes relevantes passam; cobertura ≥70% do código novo (hipótese pendente); lint e tipos limpos; traces, guardrails, `run_id` e auditoria quando aplicáveis; nenhuma credencial no código; documentação curta atualizada; chamadas LLM previstas, limitadas e contabilizadas; Revisor aprovou e criou commit atômico; PR pronto para integração.

## Verificação

Backend: `ruff check backend tests`, `mypy backend`, `pytest`. Frontend após migração: `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build`. Os scripts/configurações ainda serão criados nas tasks de setup; antes disso, executar apenas comandos disponíveis e registrar a lacuna.
