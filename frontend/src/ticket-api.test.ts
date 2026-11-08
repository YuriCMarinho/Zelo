import { afterEach, describe, expect, it, vi } from 'vitest'
import { approveQuote, startTicketResolution } from './api/client'

afterEach(() => { vi.unstubAllGlobals() })

describe.each([
  { operation: 'aprovação', request: () => approveQuote('t-1', 'p-1') },
  { operation: 'início da resolução', request: () => startTicketResolution('t-1') },
])('$operation sem sucesso fictício', ({ request }) => {
  it('rejeita falha de rede', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(request()).rejects.toThrow('Não foi possível conectar')
  })

  it.each([400, 500])('preserva o erro HTTP %s do backend', async (status) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(
      { detail: 'O chamado não está aguardando aprovação.' }, { status },
    )))
    await expect(request()).rejects.toThrow('O chamado não está aguardando aprovação.')
  })

  it('rejeita resposta inválida sem fabricar estado ou data', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({})))
    await expect(request()).rejects.toThrow('resposta inválida')
  })

  it('devolve apenas o estado confirmado pela API', async () => {
    const ticket = { id: 't-1', status: 'waiting_date_confirmation', scheduled_date: null }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(ticket)))
    await expect(request()).resolves.toEqual(ticket)
  })
})
