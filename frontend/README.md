# SmartRepair Frontend

Shell React + TypeScript + Vite da plataforma de imóveis. Usa dados locais de demonstração enquanto os contratos e endpoints do backend são concluídos. O cabeçalho mostra o orçamento simulado de US$ 25,00 (US$ 7,50 reservados para a S3); as mensagens não são enviadas ao backend.

```bash
npm ci
npm run dev
```

Validação: `npm run lint`, `npm run typecheck`, `npm run test` e `npm run build`.

Rotas: `/` lista os imóveis; `/imoveis/:id` mostra detalhes e calendário; `?aba=chat` e `?aba=adm` abrem canais separados. Os formatos de dados usados pela UI estão em `src/contracts.ts` e podem ser mapeados aos schemas do backend na integração S2-T7.
