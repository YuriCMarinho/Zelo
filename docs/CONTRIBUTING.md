# Guia de Contribuição e Organização do Repositório (`CONTRIBUTING.md`)

Atualizado em: `2026-11-07` (fonte da verdade: `planejamento2.md`).

Este documento define as regras de estrutura de pastas, branches, commits, PRs, resolução de conflitos e critérios de prontidão/conclusão para os **4 desenvolvedores humanos** e os **3 agentes de IA de desenvolvimento** (Planejador, Implementador e Revisor/Auditor).

---

## 1. Estrutura de Pastas do Repositório

```text
/
├── agents/         # Instruções operacionais dos 3 agentes de dev (planner.md, implementer.md, reviewer.md)
├── backend/        # Aplicação Python 3.12 (FastAPI, Pydantic v2, LangGraph, APScheduler, SQLAlchemy)
├── frontend/       # Aplicação React + TypeScript + Vite (interface estilo Airbnb + sessão Agente ⇄ ADM)
├── docs/           # Documentação viva (PLAN.md, COST.md, STATUS.md, CONTRIBUTING.md, PITCH.md, etc.)
├── infra/          # Docker Compose (PostgreSQL), Dockerfiles, seeds de demo e scripts de deploy
└── tests/          # Testes unitários, integração (caminhos alternativos), segurança (injection/LGPD) e E2E
```

---

## 2. Estratégia de Branches e Fluxo de Trabalho (4 Devs em Paralelo)

- **`main` (protegida):** Contém apenas versões estáveis e validadas. Só recebe merge vindo de `develop` após aprovação do Revisor e execução por um desenvolvedor humano responsável definido pelo time. Proibido push direto em `main`.
- **`develop` (integração):** Branch base para todas as sprints e tasks.
- **Branches de trabalho (uma task = uma branch = um dev/agente dono):**
  - `feature/<sprint>-<task-id>-<slug>` (ex.: `feature/s1-t1-db-contracts`)
  - `fix/<sprint>-<task-id>-<slug>` (ex.: `fix/s3-t9-real-llm-e2e`)
  - `docs/<sprint>-<task-id>-<slug>` (ex.: `docs/s0-t0-planejamento-v2`)

### Ciclo Obrigatório por Task
1. **Planejador** define/atualiza a task e o orçamento em `docs/PLAN.md`, `docs/COST.md` e `docs/STATUS.md`.
2. **Implementador** executa apenas a task atribuída na branch correspondente, escreve os testes junto com o código e **não faz commit** (entrega a árvore de trabalho para revisão).
3. **Revisor/Auditor** audita código, testes, segurança, LGPD e custo; se aprovado, executa o **commit atômico** na branch da task e **abre o Pull Request (PR) para `develop`**.
4. **Desenvolvedor Humano** dono da task revisa o PR aberto pelo Revisor e realiza o merge em `develop`.

---

## 3. Padrão de Commits e Pull Requests

- **Commits Atômicos:** Um commit representa exatamente uma mudança lógica coesa, criado pelo Revisor após validação completa.
- **Conventional Commits obrigatório:**
  - `feat(escopo): descrição curta`
  - `fix(escopo): descrição curta`
  - `test(escopo): descrição curta`
  - `docs(escopo): descrição curta`
  - `chore(escopo): descrição curta`
- **Pull Requests:** Devem ser pequenos, focados em uma única task e estar atualizados com `git rebase origin/develop` antes da abertura do PR.

---

## 4. Arquivos Compartilhados e Resolução de Conflitos

- **Isolamento de Arquivos:** Tasks que tocam os mesmos arquivos **não podem** ser paralelizadas entre desenvolvedores. O `docs/PLAN.md` explicita os diretórios/arquivos reservados para cada task.
- **Contratos e Configurações Compartilhadas:** Alterações em contratos Pydantic (`backend/app/schemas/`), modelos de banco (`backend/app/db/`), configurações globais (`pyproject.toml`, `package.json`, `.env.example`) só podem ocorrer por meio de **task dedicada**. Caso um Implementador identifique necessidade de alterar um contrato compartilhado fora da sua task, deve registrar o bloqueio em `docs/STATUS.md` e devolver ao Planejador.
- **Atualização do `docs/STATUS.md`:** Feita de forma atômica no início e no fim de cada transição de task para evitar conflitos de merge.
- **Procedimento em Caso de Conflito:** O dono da branch executa `git fetch origin && git rebase origin/develop`, resolve o conflito preservando os contratos aprovados, reexecuta toda a bateria de testes e submete novamente ao Revisor. Nunca usar `--ours` ou `--theirs` cegamente.

---

## 5. Definition of Ready (DoR) Global

Uma task só pode entrar em `em andamento` pelo Implementador quando:
1. O plano da sprint passou pelo **Gate de Sprint** do Revisor.
2. A task possui em `docs/PLAN.md`: objetivo claro, requisitos, arquivos reservados exclusivos, dependências concluídas, Definition of Done e critérios de aceite testáveis.
3. Toda chamada ao LLM prevista na task já está orçada em `docs/COST.md` com modelo e `max_tokens`.
4. Variáveis de ambiente necessárias (ou mocks equivalentes em `LLM_MODE=mock`) estão disponíveis.

---

## 6. Definition of Done (DoD) Global

Uma task só pode ser marcada como `aprovada` pelo Revisor quando:
1. Todos os critérios de aceite verificáveis da task foram atendidos e os testes automatizados passam.
2. **Cobertura mínima de 70% no código novo** comprovada via `pytest --cov` (backend) / `vitest` (frontend).
3. Lint e checagem estática de tipos limpos (`ruff check`, `mypy`, `eslint`, `tsc --noEmit`).
4. **Custo e LLM:** Toda chamada ao LLM define `model` e `max_tokens`, respeita os tetos configurados, opera em modo mock por padrão nos testes e consta em `docs/COST.md`.
5. **Segurança, Guardrails e LGPD:** Entradas não confiáveis (hóspede, camareira, prestador) passam por guardrail; saídas são validadas por Pydantic v2; **nenhum segredo, telefone de prestador ou dado pessoal de hóspede vaza para código, logs ou traces do Langfuse** (mascaramento obrigatório).
6. **Auditabilidade:** `run_id` propagado em todos os logs de auditoria e spans do Langfuse.
7. Documentação curta atualizada, commit atômico criado pelo Revisor na branch da task, PR aberto para `develop` e `docs/STATUS.md` atualizado.
