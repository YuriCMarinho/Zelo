import { afterEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PropertyWorkspace } from './PropertyWorkspace'
import { properties } from '../demo-data'
import type { MaintenanceTicket, Quote } from '../contracts'

const property = properties[0]!

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

function backend() {
  const ticket: MaintenanceTicket = {
    id: 'ticket-live', property_id: property.id, run_id: 'run-live',
    reported_by_role: 'tenant', category: 'plumber', urgency: 'normal',
    location_in_property: 'Cozinha', description: 'Vazamento na cozinha',
    status: 'waiting_quotes', notify_tenant: false, created_at: '2026-11-08T12:00:00Z',
  }
  const quote: Quote = {
    id: 'quote-live', ticket_id: ticket.id, run_id: ticket.run_id,
    provider_id: 'provider-live', provider_name: 'Mario Encanador',
    amount: null, status: 'requested',
  }
  const state = { ticket, quote, approvalFails: false, dateRefusals: 0 }
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith(`/properties/${property.id}/tickets`)) return Response.json([ticket])
    if (url.endsWith(`/properties/${property.id}/bookings`)) return Response.json([])
    if (url.endsWith(`/tickets/${ticket.id}/quotes`)) return Response.json([quote])
    if (url.endsWith(`/quotes/${quote.provider_id}/response`)) {
      const body = JSON.parse(String(init?.body))
      quote.amount = body.amount
      quote.status = 'received'
      ticket.status = 'awaiting_adm_approval'
      return Response.json(ticket)
    }
    if (url.endsWith('/approve')) {
      if (state.approvalFails) return Response.json({ detail: 'Aprovação recusada pelo servidor.' }, { status: 400 })
      ticket.status = 'waiting_date_confirmation'
      ticket.selected_provider_id = quote.provider_id
      quote.status = 'selected'
      return Response.json(ticket)
    }
    if (url.endsWith('/date-response')) {
      const body = JSON.parse(String(init?.body))
      if (body.accepted) {
        ticket.status = 'resolved'
        ticket.scheduled_date = '2026-11-10T14:00:00Z'
      } else {
        state.dateRefusals += 1
        if (state.dateRefusals >= 3) ticket.status = 'escalated_to_adm'
      }
      return Response.json(ticket)
    }
    throw new Error(`Requisição inesperada: ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return { ...state, state, fetchMock }
}

it('executa o ciclo pela UI sem confirmar a visita antes do aceite do prestador', async () => {
  const { fetchMock } = backend()
  const user = userEvent.setup()
  const onNewMessage = vi.fn()
  const { rerender } = render(<PropertyWorkspace property={property} tab="adm" messages={[]} onNewMessage={onNewMessage} />)
  await user.click(await screen.findByText('Ações do prestador (demonstração)'))
  expect(screen.queryByRole('button', { name: /Relato de Manutenção/ })).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /Prestadores respondem/ }))
  await user.click(await screen.findByRole('button', { name: /Aprovar Mario Encanador/ }))
  expect(screen.queryByText(/agendamento confirmado!/)).not.toBeInTheDocument()
  await user.click(await screen.findByRole('button', { name: /Prestador recusa a data/ }))
  expect(await screen.findByText(/O agente vai propor a próxima janela/)).toBeInTheDocument()
  expect(screen.queryByText(/agendamento confirmado!/)).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /Prestador aceita a data/ }))
  expect(await screen.findByText(/Orçamento aprovado e agendamento confirmado!/)).toBeInTheDocument()
  const replies = fetchMock.mock.calls.filter(([url]) => url.endsWith('/date-response'))
  expect(replies.map(([, init]) => JSON.parse(String(init?.body)).accepted)).toEqual([false, true])
  // Nenhuma mensagem de confirmação é fabricada pela ação de aprovação.
  expect(onNewMessage).not.toHaveBeenCalled()
  rerender(<PropertyWorkspace property={property} tab="chat" messages={[]} onNewMessage={onNewMessage} />)
  expect(await screen.findByText(/Visita marcada/)).toHaveTextContent('10 de nov às 14:00')
})

it('mantém a aprovação pendente e mostra o erro real quando o servidor recusa', async () => {
  const { state, ticket, quote } = backend()
  ticket.status = 'awaiting_adm_approval'
  quote.status = 'received'
  quote.amount = 180
  state.approvalFails = true
  const user = userEvent.setup()
  render(<PropertyWorkspace property={property} tab="adm" messages={[]} onNewMessage={vi.fn()} />)
  await user.click(await screen.findByRole('button', { name: /Aprovar Mario Encanador/ }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Aprovação recusada pelo servidor')
  expect(screen.queryByText(/agendamento confirmado!/)).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Aprovar Mario Encanador/ })).toBeEnabled()
})

it('consulta respostas externas a cada 5 segundos e atualiza status e orçamento', async () => {
  vi.useFakeTimers()
  const { ticket, quote, fetchMock } = backend()
  let unmount = () => {}
  await act(async () => {
    const view = render(<PropertyWorkspace property={property} tab="adm" messages={[]} onNewMessage={vi.fn()} />)
    unmount = view.unmount
  })
  quote.status = 'received'
  quote.amount = 275
  ticket.status = 'awaiting_adm_approval'
  await act(async () => { await vi.advanceTimersByTimeAsync(4999) })
  expect(screen.queryByRole('button', { name: /Aprovar Mario/ })).not.toBeInTheDocument()
  await act(async () => { await vi.advanceTimersByTimeAsync(1) })
  expect(screen.getByRole('button', { name: /Aprovar Mario/ })).toHaveTextContent('275')
  ticket.status = 'resolved'
  ticket.scheduled_date = '2026-11-10T14:00:00Z'
  await act(async () => { fireEvent(window, new Event('focus')) })
  expect(screen.getByText(/Orçamento aprovado e agendamento confirmado!/)).toBeInTheDocument()
  const requestCount = fetchMock.mock.calls.length
  unmount()
  await act(async () => { await vi.advanceTimersByTimeAsync(10000); fireEvent(window, new Event('focus')) })
  expect(fetchMock).toHaveBeenCalledTimes(requestCount)
})

it('escala ao anfitrião depois de três recusas sem anunciar uma nova proposta', async () => {
  const { ticket } = backend()
  ticket.status = 'waiting_date_confirmation'
  const user = userEvent.setup()
  render(<PropertyWorkspace property={property} tab="adm" messages={[]} onNewMessage={vi.fn()} />)
  await user.click(await screen.findByText('Ações do prestador (demonstração)'))
  for (let attempt = 0; attempt < 3; attempt += 1) {
    await user.click(await screen.findByRole('button', { name: /Prestador recusa a data/ }))
    if (attempt < 2) await screen.findByText(/O agente vai propor a próxima janela/)
  }
  expect(await screen.findByText(/tentativas de data se esgotaram/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Prestador aceita a data/ })).not.toBeInTheDocument()
})

it('permite ao anfitrião aceitar ou recusar solicitações de hospedagem com notificação no chat', async () => {
  const pendingBooking = {
    id: 'book-pending-1',
    property_id: property.id,
    guest_name: 'Hóspede Interessado (a1b2)',
    guest_contact: '(81) 99999-1111',
    start_date: '2026-12-15',
    end_date: '2026-12-18',
    status: 'pending_approval',
    total_price: 960,
    num_guests: 2,
    created_at: '2026-11-08T12:00:00Z',
  }
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith(`/properties/${property.id}/tickets`)) return Response.json([])
    if (url.endsWith(`/properties/${property.id}/bookings`)) return Response.json([pendingBooking])
    if (url.endsWith(`/bookings/${pendingBooking.id}/approve`)) {
      const body = JSON.parse(String(init?.body || '{}'))
      pendingBooking.status = 'confirmed'
      if (body.final_price) pendingBooking.total_price = body.final_price
      return Response.json(pendingBooking)
    }
    throw new Error(`Requisição inesperada: ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)

  const user = userEvent.setup()
  const onNewMessage = vi.fn()
  render(<PropertyWorkspace property={property} tab="adm" messages={[]} onNewMessage={onNewMessage} />)

  expect(await screen.findByText(/Hóspede Interessado \(a1b2\)/)).toBeInTheDocument()
  const approveBtn = await screen.findByRole('button', { name: /Aceitar Reserva/ })
  await user.click(approveBtn)

  expect(await screen.findByRole('status')).toHaveTextContent(/confirmada/)
  expect(onNewMessage).toHaveBeenCalledTimes(1)
  expect(onNewMessage.mock.calls[0]![0].body).toMatch(/aprovou sua reserva/i)
})

it('exibe 3 fornecedores com nota real do Google, endereço e permite recusar propostas para nova cotação', async () => {
  const ticket: MaintenanceTicket = {
    id: 'ticket-3prov',
    property_id: property.id,
    run_id: 'run-3prov',
    reported_by_role: 'tenant',
    category: 'electrician',
    urgency: 'urgent',
    location_in_property: 'Suíte',
    description: 'Chuveiro elétrico não esquenta',
    status: 'awaiting_adm_approval',
    notify_tenant: true,
    adm_synthesis: '3 eletricistas do Recife enviaram propostas detalhadas.',
    created_at: '2026-11-08T12:00:00Z',
  }
  const quotes: Quote[] = [
    {
      id: 'q1',
      ticket_id: ticket.id,
      run_id: ticket.run_id,
      provider_id: 'p1',
      provider_name: 'Capibaribe Soluções Elétricas',
      provider_rating: 4.9,
      provider_reviews_count: 219,
      provider_address: 'Cais do Apolo, 410 - Bairro do Recife',
      amount: 165,
      description: 'Troca de resistência blindada com garantia de 90 dias',
      proposed_availability: 'Hoje em até 2h',
      status: 'received',
      is_recommended: true,
    },
    {
      id: 'q2',
      ticket_id: ticket.id,
      run_id: ticket.run_id,
      provider_id: 'p2',
      provider_name: 'PortoVolt Engenharia Elétrica',
      provider_rating: 4.8,
      provider_reviews_count: 154,
      provider_address: 'Rua da Guia, 202 - Bairro do Recife',
      amount: 210,
      description: 'Reparo elétrico completo do chuveiro e disjuntor',
      proposed_availability: 'Hoje à tarde',
      status: 'received',
      is_recommended: false,
    },
    {
      id: 'q3',
      ticket_id: ticket.id,
      run_id: ticket.run_id,
      provider_id: 'p3',
      provider_name: 'EletroPernambuco Instalações',
      provider_rating: 4.6,
      provider_reviews_count: 87,
      provider_address: 'Av. Marquês de Olinda, 190 - Bairro do Recife',
      amount: 145,
      description: 'Troca rápida do elemento aquecedor',
      proposed_availability: 'Amanhã às 08h30',
      status: 'received',
      is_recommended: false,
    },
  ]

  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith(`/properties/${property.id}/tickets`)) return Response.json([ticket])
    if (url.endsWith(`/properties/${property.id}/bookings`)) return Response.json([])
    if (url.endsWith(`/tickets/${ticket.id}/quotes`)) return Response.json(quotes)
    if (url.endsWith(`/tickets/${ticket.id}/reject-quotes`)) {
      const body = JSON.parse(String(init?.body || '{}'))
      quotes[0]!.amount = 148
      ticket.adm_synthesis = `Propostas renegociadas (${body.reason})`
      return Response.json(ticket)
    }
    throw new Error(`Requisição inesperada: ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)

  const user = userEvent.setup()
  render(<PropertyWorkspace property={property} tab="adm" messages={[]} onNewMessage={vi.fn()} />)

  expect(await screen.findByText('Capibaribe Soluções Elétricas')).toBeInTheDocument()
  expect(screen.getByText('PortoVolt Engenharia Elétrica')).toBeInTheDocument()
  expect(screen.getByText('EletroPernambuco Instalações')).toBeInTheDocument()
  expect(screen.getByText(/219 avaliações no Google/)).toBeInTheDocument()
  expect(screen.getByText(/Cais do Apolo, 410/)).toBeInTheDocument()
  expect(screen.getByText('Ciclo do Chamado (Fluxo C)')).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: /Recusar propostas e solicitar novos orçamentos/ }))
  await user.click(screen.getByRole('button', { name: /Confirmar e pedir novas propostas/ }))

  expect(await screen.findByText(/Propostas renegociadas/)).toBeInTheDocument()
})
