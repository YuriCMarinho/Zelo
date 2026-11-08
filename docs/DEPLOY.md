# Guia de Deploy e Verificação do Link Testável (`DEPLOY.md`)

> **Projeto:** Zelo — Plataforma Autônoma de Gestão e Manutenção para Imóveis de Temporada  
> **Versão:** 1.0 (Hackathon Edition)  
> **Arquitetura de Deploy:** Container Unificado Multi-stage (FastAPI + React SPA) com PostgreSQL Gerenciado  
> **URL anterior da demonstração:** `https://zelo-smartrepair-ai.onrender.com`. O healthcheck retornou HTTP 404 em 2026-11-08; confirmar o endereço ativo antes da submissão. Consulte [`SUBMISSION.md`](SUBMISSION.md).

---

## 1. Visão Geral da Arquitetura de Produção

Para simplificar a avaliação dos jurados e eliminar completamente qualquer problema de CORS, latência de rede entre camadas ou dependência de múltiplos domínios, o Zelo opera com uma **topologia de container único**:

```mermaid
flowchart LR
    Browser["Navegador do Jurado / Avaliador"] -->|HTTPS Porta 443 / 80| Unified["Container Docker Unificado (Render / Railway)<br/>• Node 20 build: React SPA estático<br/>• Python 3.12: FastAPI / Uvicorn na porta $PORT"]
    Unified -->|Rotas /api/* e /health| API["FastAPI Endpoints<br/>(Chat, Tickets, Demo Reset, Custos)"]
    Unified -->|Rotas / e /*| SPA["React + Vite Zelo Design System<br/>(dist/index.html)"]
    API -->|DATABASE_URL| Postgres[("PostgreSQL 16 Gerenciado<br/>(Render / Neon / Supabase)")]
    API -.->|Telemetria e Spans| Langfuse["Langfuse Cloud"]
    API -.->|Inferência| Featherless["Featherless AI (Qwen 3.5)"]
```

---

## 2. Opções de Hospedagem em Nuvem (1-Click Deploy)

### Opção A: Render (Recomendada via Blueprint `render.yaml`)

O repositório possui o arquivo [`render.yaml`](../render.yaml) para provisionar a aplicação web e o banco PostgreSQL. Disponibilidade e condições do serviço devem ser confirmadas na conta usada pelo time:

1. Acesse [dashboard.render.com](https://dashboard.render.com) e conecte sua conta do GitHub.
2. Clique em **New +** → **Blueprint**.
3. Selecione o repositório `converge-challange` (branch `develop` ou `main`).
4. O Render detectará automaticamente o serviço `zelo-smartrepair-ai` e o banco `zelo-postgres`.
5. Clique em **Apply**. O deploy compilará o frontend e backend em ~3 minutos e gerará a URL pública HTTPS (ex.: `https://zelo-smartrepair-ai.onrender.com`).

### Opção B: Railway

1. Acesse [railway.app](https://railway.app) e clique em **New Project** → **Deploy from GitHub repo**.
2. Adicione um plugin de **PostgreSQL** no mesmo projeto.
3. No serviço da aplicação, defina a variável `DATABASE_URL` vinculada ao Postgres e `ENVIRONMENT=production`.
4. Em **Settings** → **Networking**, clique em **Generate Domain** para obter a URL pública instantânea.

### Opção C: Neon / Supabase + VPS ou Docker Host

Caso utilize uma VPS (Ubuntu/Debian) com Docker:

```bash
git clone https://github.com/YuriCMarinho/converge-challange.git
cd converge-challange
docker compose -f infra/docker-compose.prod.yml up -d --build
```

---

## 3. Matriz de Variáveis de Ambiente de Produção

| Variável | Valor Padrão / Exemplo | Obrigatória? | Descrição |
| --- | --- | :---: | --- |
| `DATABASE_URL` | `postgresql://user:pass@host:5432/db` | **Sim** | String de conexão com o PostgreSQL |
| `ENVIRONMENT` | `production` | **Sim** | Define o ambiente em modo produção |
| `PORT` | `8000` (ou atribuída pela nuvem) | Não | Porta HTTP escutada pelo Uvicorn |
| `LLM_MODE` | `recorded_demo` (ou `featherless`) | Não | Modo de IA: `recorded_demo` (offline estável) ou `featherless` (chamadas de rede pagas) |
| `FEATHERLESS_API_KEY` | `sk-...` | Condicional | Chave da Featherless (obrigatória apenas se `LLM_MODE=featherless`) |
| `LANGFUSE_PUBLIC_KEY` | `pk-lf-...` | Não | Chave pública do Langfuse para rastreamento de custos e spans |
| `LANGFUSE_SECRET_KEY` | `sk-lf-...` | Não | Chave secreta do Langfuse |
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` | Não | Endpoint do Langfuse Cloud |

---

## 4. Roteiro de Testes para o Avaliador (3 Minutos)

Para que qualquer membro da banca examinadora valide a solução do zero:

1. **Acessar a URL da Aplicação:**  
   Abra o link público no navegador (ex.: `https://zelo-smartrepair-ai.onrender.com`).
2. **Garantir Ambiente Limpo (1-Click Reset):**  
   No cabeçalho superior direito, clique em **↻ Resetar Demo** e confirme no modal. Em menos de 1 segundo o banco recria os 3 imóveis canônicos e limpa chamados anteriores.
3. **Testar Atendimento Comercial (Fluxo A):**  
   Clique no imóvel *Apartamento Vista Mar - Copacabana*, acesse a aba **Chat do imóvel**, selecione o papel de Hóspede e pergunte:  
   *"Olá! Qual a velocidade do Wi-Fi e tem berço disponível?"*  
   *Resultado:* O agente responde cordialmente destacando as comodidades com base nas regras do imóvel.
4. **Testar Relato de Manutenção (Fluxo C):**  
   No mesmo chat, mude o seletor para **Camareira** e envie:  
   *"A torneira da pia da cozinha quebrou e está vazando bastante água no chão."*  
   *Resultado:* O Roteador de custo zero identifica o problema e o Nó 2 Validador abre imediatamente o ticket com status `open` e urgência URGENTE.
5. **Decisão do Anfitrião (Sessão Agente ⇄ Anfitrião):**  
   Acesse a aba **Agente ⇄ Anfitrião**. Abra **Ações do prestador (demonstração)** e clique em **Prestadores respondem**. Confira os orçamentos realmente recebidos e aprove um prestador como anfitrião.
6. **Agendamento Inteligente e Conclusão:**  
   O sistema propõe uma data pela regra `urgência × agenda`. No painel do prestador, recuse ou aceite a data. Somente o aceite confirma a visita no calendário; o aviso ao inquilino é registrado na auditoria quando houver ocupação na data.
7. **Auditoria e Ledger de Custos:**  
   Clique em **Auditoria** para inspecionar o ledger e os eventos. No modo `recorded_demo`, o custo de reprodução é zero e o Langfuse externo não é acionado. O [Plano B](RECORDED_DEMO.md) detalha ativação e smoke test.

---

## 5. Comandos de Smoke Test Automatizado (CLI)

Após o deploy, você pode validar o status dos serviços via terminal:

```bash
# 1. Healthcheck Geral da Aplicação
curl -s -f https://zelo-smartrepair-ai.onrender.com/health | jq .

# 2. Conectividade e Integridade do Banco PostgreSQL
curl -s -f https://zelo-smartrepair-ai.onrender.com/health/db | jq .

# 3. Teste do Endpoint de 1-Click Reset
curl -s -X POST https://zelo-smartrepair-ai.onrender.com/api/demo/reset | jq .
```
