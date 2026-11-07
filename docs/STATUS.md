# Status — fonte da verdade

Atualizado em 2026-11-07. Estados permitidos: **não iniciada**, **em andamento**, **em revisão**, **aprovada**, **bloqueada**. Todo agente lê este arquivo antes de agir e atualiza a própria transição ao iniciar e terminar. `Dev 1` a `Dev 4` são papéis temporários até os humanos confirmarem nomes.

## Fases

| Fase | Estado | Responsável | Branch | Último commit | Bloqueios / decisões |
| --- | --- | --- | --- | --- | --- |
| Planejamento | em revisão | Orquestrador → Planejador/Revisor | atual `main` (documentos ainda sem commit) | — | Prazo relativo confirmado: 22h41m até submissão; confirmar hora absoluta, Tako, banco, autonomia e cobertura; gate S0 pendente |
| Implementação | não iniciada | Dev 1–4 + Implementador | — | — | Aguardar gate de sprint e `develop` |
| Validação | não iniciada | Dev 4 + Revisor | — | — | Reservar US$ 7,50 e preparar demo |

## Sprints e tasks

| Sprint / task | Fase | Estado | Responsável (dev + agente) | Branch prevista | Último commit | Bloqueios / decisões |
| --- | --- | --- | --- | --- | --- | --- |
| S0 / P0 plano e custo | Planejamento | em revisão | Dev 1 + Planejador/Revisor | `docs/s0-p0-plano-custo` | — | Hipóteses a confirmar; gate S0 |
| S1 / T1 contratos e setup backend | Implementação | não iniciada | Dev 1 + Implementador/Revisor | `feature/s1-t1-contratos` | — | S0 aprovado |
| S1 / T2 frontend TS e shell | Implementação | não iniciada | Dev 2 + Implementador/Revisor | `feature/s1-t2-frontend` | — | S0 aprovado; arquivos atuais de `src/` reservados |
| S1 / T3 orçamento, auditoria e tracing | Implementação | não iniciada | Dev 3 + Implementador/Revisor | `feature/s1-t3-controle` | — | T1 contratos |
| S1 / T4 dados de demo e pesquisa de prestadores | Implementação | não iniciada | Dev 4 + Implementador/Revisor | `feature/s1-t4-prestadores` | — | T1 contratos |
| S2 / T5 atendimento e triagem | Implementação | não iniciada | Dev 1 + Implementador/Revisor | `feature/s2-t5-triagem` | — | T1, T3 |
| S2 / T6 orçamento, aprovação e agenda | Implementação | não iniciada | Dev 3 + Implementador/Revisor | `feature/s2-t6-resolucao` | — | T1, T3, T4 |
| S2 / T7 painel conectado e API de aprovação | Implementação | não iniciada | Dev 2 + Implementador/Revisor | `feature/s2-t7-painel` | — | T1, T2; contrato aprovado |
| S2 / T8 segurança e testes integrados | Validação | não iniciada | Dev 4 + Implementador/Revisor | `feature/s2-t8-seguranca` | — | T5, T6 |
| S3 / T9 E2E, custos reais e correções | Validação | não iniciada | Dev 1 + Implementador/Revisor | `fix/s3-t9-e2e` | — | S2 aprovada; não alterar arquivos de T10–T12 |
| S3 / T10 deploy e link testável | Validação | não iniciada | Dev 2 + Implementador/Revisor | `feature/s3-t10-deploy` | — | S2 aprovada; credenciais/hosting |
| S3 / T11 vídeo, pitch e Demo Day | Validação | não iniciada | Dev 3 + Implementador/Revisor | `docs/s3-t11-pitch` | — | Fluxo demonstrável |
| S3 / T12 submissão e plano B | Validação | não iniciada | Dev 4 + Implementador/Revisor | `docs/s3-t12-submissao` | — | Link e vídeo de T10/T11 |

## Decisões e bloqueios ativos

1. Prazo confirmado: 22h41m restantes até submissão do MVP no momento da mensagem do time. Hipóteses restantes: sem Desafio Tako, SQLite, ADM sempre aprova contratação, cobertura 70%; confirmar antes do gate S1.
2. O protótipo React/Vite já está na raiz (`src/`, `package.json`), usa `localStorage` e dados simulados; T2 faz migração controlada.
3. Coleta de prestadores: usar dados simulados/allowlist na demo; avaliar Google Places API como integração opcional. Nenhuma mensagem real a terceiros sem aprovação explícita.
4. A conta Featherless deve ter créditos de API utilizáveis; verificar acesso e preço por modelo antes da primeira chamada paga.
