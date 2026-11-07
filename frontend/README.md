# Zelo Frontend

Interface React + TypeScript + Vite da plataforma de imóveis, adaptada dos mockups em `frontend-referencias`. Usa dados locais de demonstração enquanto os contratos e endpoints do backend são concluídos. O cabeçalho mostra o orçamento simulado de US$ 25,00 (US$ 7,50 reservados para a S3); mensagens e escolhas de orçamento não são enviadas ao backend.

```bash
npm ci
npm run dev
```

Validação: `npm run lint`, `npm run typecheck`, `npm run test` e `npm run build`.

Rotas: `/` lista os imóveis; `/imoveis/:id` mostra detalhes e calendário; `?aba=chat` e `?aba=adm` abrem canais separados; `?aba=orcamentos` mostra um comparativo simulado. Os formatos de dados usados pela UI estão em `src/contracts.ts` e podem ser mapeados aos schemas do backend na integração S2-T7.
