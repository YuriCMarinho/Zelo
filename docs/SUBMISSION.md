# Submissão — Zelo

Atualizado em 2026-11-08. Pacote preparado pela S3-T12; **a submissão final ainda depende dos links da T11 e de um deploy acessível**. Não enviar o formulário enquanto os cinco itens abaixo não estiverem conferidos.

## 1. Descrição pronta para o formulário

Zelo reúne atendimento e manutenção de imóveis de temporada em um só lugar. Hóspedes e camareiras relatam dúvidas ou problemas no chat do imóvel. O sistema separa atendimento comercial de manutenção, registra os chamados e solicita orçamentos a prestadores validados da região.

O anfitrião compara as propostas e decide quem contratar. Depois dessa aprovação, o sistema propõe uma data considerando a urgência e a ocupação do imóvel, aguarda a confirmação do prestador e registra a visita no calendário. Se houver hóspede na data, o fluxo registra o aviso correspondente. Recusas e falta de resposta têm tratamento explícito, com escalonamento ao anfitrião.

O protótipo usa FastAPI, PostgreSQL, React e LangGraph, com modelos Qwen via Featherless, controles de custo, guardrails e auditoria por execução. Na demonstração, os contatos e respostas dos prestadores são simulados de forma explícita. O Plano B reproduz respostas reais previamente gravadas dos modelos, mantendo as decisões do anfitrião, os preços e a confirmação de datas como eventos separados e verificáveis.

## 2. Cinco entregáveis obrigatórios

| Entregável | Referência | Situação verificada |
| --- | --- | --- |
| Descrição do projeto | Seção 1 deste arquivo | Pronta. |
| Vídeo de demonstração | `video_url` em [submission.json](submission.json) | Pendente da S3-T11; nenhum link fornecido. |
| Link testável | Endereço anterior: `https://zelo-smartrepair-ai.onrender.com` | `/health` retornou HTTP 404 em 2026-11-08. Substituir pelo deploy ativo e testar o ciclo completo. |
| Material do Demo Day/pitch | `pitch_url` em [submission.json](submission.json) | Pendente da S3-T11; nenhum link fornecido. |
| Ferramentas e modelos | [TOOLS.md](TOOLS.md) | Lista preparada com distinção entre implementado, opcional e simulado. |

Repositório: `https://github.com/YuriCMarinho/converge-challange`. A URL retornou HTTP 404 em acesso anônimo em 2026-11-08, embora o acesso Git autenticado funcione. Confirmar visibilidade ou conceder acesso aos avaliadores conforme as regras do evento. Não afirmar que o código está público antes dessa checagem.

Os links ficam centralizados em [submission.json](submission.json). Preencher `video_url`, `pitch_url` e o `app_url` correto; o validador não aceita campos vazios como entrega concluída.

## 3. Conferência final

Na raiz do repositório:

```bash
python3 scripts/check_submission.py --check-links
```

O comando retorna código 1 enquanto houver item ausente, arquivo inexistente ou URL inacessível. A checagem do repositório também precisa passar no acesso sem as credenciais locais. Um HTTP 200 não substitui assistir ao vídeo, abrir os slides e testar a aplicação como avaliador.

- [ ] Vídeo abre em janela anônima e mostra o fluxo completo, sem segredos ou dados pessoais reais.
- [ ] Link testável abre em janela anônima; `/health` e `/health/db` respondem.
- [ ] Pitch está acessível, com permissões de leitura para a banca.
- [ ] Ferramentas e modelos correspondem ao que foi efetivamente usado.
- [ ] Código está acessível para quem avaliará o projeto.
- [ ] Responsável pelo time conferiu regras, prazo e campos do formulário oficial.

## 4. Roteiro testável e contingência

1. Abra o imóvel de Copacabana e o chat. Pergunte “qual o horário de check-in?”; o horário vem das regras cadastradas.
2. Como camareira, envie “A torneira da pia da cozinha quebrou e está vazando água no chão.”
3. Na sessão “Agente ⇄ Anfitrião”, abra “Ações do prestador (demonstração)” e use “Prestadores respondem”. Os valores são exemplos explícitos de respostas do prestador.
4. Como anfitrião, aprove um orçamento. O atendimento deve aguardar a confirmação da data.
5. No painel do prestador, recuse uma vez para demonstrar a nova proposta; depois aceite.
6. Confira o chamado, a visita no calendário e os eventos da auditoria. O aviso ao hóspede é registrado quando há ocupação na data; sua apresentação como mensagem persistente do chat é uma pendência separada.

Plano B, limites dos cenários, comandos e medição de ativação: [RECORDED_DEMO.md](RECORDED_DEMO.md). Vídeo e slides continuam sendo entregáveis da S3-T11; este pacote não os substitui.
