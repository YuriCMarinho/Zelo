# Zelo Frontend

Interface React + TypeScript + Vite da plataforma de imóveis, adaptada dos mockups em `frontend-referencias`. Usa dados locais de demonstração enquanto os contratos e endpoints do backend são concluídos. Mensagens e escolhas de orçamento não são enviadas ao backend.

```bash
npm ci
npm run dev
```

Validação: `npm run lint`, `npm run typecheck`, `npm run test` e `npm run build`.

Rotas: `/` lista os imóveis; `/imoveis/:id` mostra detalhes e calendário; `?aba=chat` e `?aba=adm` abrem canais separados; `?aba=orcamentos` mostra um comparativo simulado. Os formatos de dados usados pela UI estão em `src/contracts.ts` e podem ser mapeados aos schemas do backend na integração S2-T7.

Telas de gestão: `/reservas` permite buscar e cadastrar estadias com validação de datas, capacidade e conflitos; `/manutencao` permite abrir chamados e acompanhar o status; `/configuracoes` salva perfil e preferências. Os dados dessas telas são persistidos no `localStorage` deste navegador, sem envio ao backend. Novas reservas aparecem no calendário do imóvel. As preferências de notificação são demonstrativas e não enviam mensagens.
