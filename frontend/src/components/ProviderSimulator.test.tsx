import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ProviderSimulator } from './ProviderSimulator'
import { properties } from '../demo-data'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const property = properties[0]!

describe('simulador do prestador', () => {
  it('oferece resposta de orçamento só enquanto o Nó 3 espera orçamentos', () => {
    render(
      <ProviderSimulator property={property} currentTicketId="t-1" ticketStatus="waiting_quotes" onTicketUpdated={() => {}} />,
    )
    expect(screen.getByRole('button', { name: /Prestadores respondem/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /aceita a data/ })).not.toBeInTheDocument()
  })

  it('envia a devolutiva do dia ao backend e avisa a tela', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ id: 't-1', status: 'resolved' }), { status: 200 }),
    )
    const onTicketUpdated = vi.fn()
    const user = userEvent.setup()
    render(
      <ProviderSimulator
        property={property}
        currentTicketId="t-1"
        ticketStatus="waiting_date_confirmation"
        onTicketUpdated={onTicketUpdated}
      />,
    )

    await user.click(screen.getByRole('button', { name: /Prestador recusa a data/ }))

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/tickets/t-1/date-response',
      expect.objectContaining({ method: 'POST' }),
    )
    const body = JSON.parse(String(fetchMock.mock.calls[0]![1]!.body))
    expect(body.accepted).toBe(false)
    expect(await screen.findByText(/O agente vai propor a próxima janela/)).toBeInTheDocument()
    expect(onTicketUpdated).toHaveBeenCalled()
  })

  it('mostra o erro do backend quando a resposta é recusada', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Violação de segurança nos guardrails' }), { status: 400 }),
    )
    const user = userEvent.setup()
    render(
      <ProviderSimulator
        property={property}
        currentTicketId="t-1"
        ticketStatus="waiting_date_confirmation"
        onTicketUpdated={() => {}}
      />,
    )
    await user.click(screen.getByRole('button', { name: /Prestador aceita a data/ }))
    expect(await screen.findByText(/Violação de segurança/)).toBeInTheDocument()
  })
})
