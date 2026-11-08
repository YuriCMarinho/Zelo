# Plano B — respostas gravadas

## O que muda

`LLM_MODE=recorded_demo` reproduz as respostas de `backend/app/demo/recordings.json`. São oito gravações reais feitas na Featherless em 2026-11-08, usando apenas prompts fictícios. O arquivo registra origem, modelo, data, tokens, custo de captura e hash do prompt. Os textos de orientação são deliberadamente genéricos: os preços, prestadores e datas continuam vindo dos registros e eventos do chamado.

O modo não chama Featherless, Google Places nem envia traces ao Langfuse. A coleta usa fixtures mesmo se `PROVIDER_SOURCE=google_places` estiver configurado. Banco de dados e interface continuam funcionando normalmente. O ledger registra as reproduções com `cost_usd=0` e `is_mock=true`; esses tokens não representam nova inferência paga.

O roteiro suporta saudação comercial, consulta determinística de check-in e o ciclo de manutenção. Perguntas comerciais fora desse roteiro recebem uma resposta gravada para confirmar a informação com o anfitrião, sem inventar comodidades. Nós/modelos sem gravação falham explicitamente: **não existe fallback automático para API paga**. `response_format` continua passando por validação Pydantic.

No aviso ao hóspede, os marcadores gravados `{{service}}` e `{{scheduled_date}}` recebem o serviço e a data confirmada do chamado. Preços e decisões não são produzidos pela gravação. O sistema ainda espera respostas explícitas do prestador/simulador e aprovação do anfitrião.

## Ativar e verificar

Na pasta `backend`, encerre a instância anterior e inicie com a variável de ambiente abaixo. Não execute duas instâncias na mesma porta.

```bash
LLM_MODE=recorded_demo PROVIDER_SOURCE=fixture .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Em outro terminal:

```bash
curl --fail http://127.0.0.1:8000/health
```

Confirme `llm_mode: recorded_demo`. Para voltar à inferência real, reinicie o mesmo serviço com `LLM_MODE=featherless` e a chave já configurada. A configuração só muda para o processo iniciado; não há endpoint público para trocar o modo de IA.

No Render, a variável já está no `render.yaml`; a alteração da configuração exige reinício/redeploy da plataforma. **A medição local abaixo não garante uma troca em menos de 10 segundos em hospedagem gratuita ou com cold start.** Para apresentação, mantenha uma instância local já iniciada como contingência.

## Smoke test completo, sem alterar seus dados

```bash
cd backend
.venv/bin/python scripts/check_recorded_demo.py
```

O comando sobe outra instância numa porta livre e SQLite temporário, sem chaves de API. Faz saudação, abre chamado, recebe dois orçamentos simulados, aprova um deles, recusa a primeira data, aceita a seguinte e verifica aviso ao hóspede, auditoria e custo zero. Encerra a instância e limpa apenas o banco temporário ao terminar. Falha se o ciclo desde o início do processo exceder 10 segundos.

Medição inicial em 2026-11-08: **2,995 s para o healthcheck e 3,787 s para todo o ciclo HTTP**, com duas cotações e custo de inferência zero. O frontend não entra nesse limite: a pausa de 4–8 segundos e a digitação configuradas no chat são intencionais e independentes da ativação do servidor.

## Latência, custos e novas gravações

`RECORDED_DEMO_LATENCY_MS` controla uma espera assíncrona por resposta, entre 0 e 1000 ms (padrão: 80 ms). Não bloqueia a event loop nem elimina os tempos de interação do frontend.

Captura adicional é uma ação paga explícita, separada da reprodução:

```bash
cd backend
LLM_MODE=featherless .venv/bin/python scripts/record_demo.py --capture
```

O script requer chave configurada, usa o cliente com controles de orçamento e ledger, limita a estimativa do lote a US$ 0,003 e preserva gravações válidas com o mesmo prompt. Revisar e versionar o JSON antes de publicar. Não usar dados reais de hóspedes ou segredos nos prompts. O custo das oito gravações preservadas foi US$ 0,00009266; tentativas descartadas também ficam contabilizadas no ledger, sem custo novo na reprodução.

## Limites conhecidos

- O modo gravado demonstra cenários definidos; não oferece conversação aberta equivalente ao modelo ao vivo.
- Não envia mensagens reais a prestadores. As respostas são ações explícitas no painel de demonstração.
- Timers do APScheduler não são restaurados após reinício. Retomar um cenário novo para ensaio; não resetar dados de outras pessoas.
- O PostgreSQL continua necessário no deploy habitual; a ausência de inferência externa não elimina a dependência do banco.
- Imagens remotas do frontend ainda podem depender de internet. A garantia verificada aqui cobre o fluxo HTTP/backend, não todos os recursos visuais offline.
- Vídeo e slides continuam pendentes da T11. O Plano B não substitui esses entregáveis.
