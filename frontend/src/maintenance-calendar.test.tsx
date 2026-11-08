import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import App from './App'
import { properties } from './demo-data'
import type { MaintenanceTicket } from './contracts'

const property = properties[0]!
const visitDate = property.occupancy[0]!.startDate
const ticket: MaintenanceTicket = {
  id: 'ticket-visit', run_id: 'run-visit', property_id: property.id,
  reported_by_role: 'tenant', category: 'plumber', urgency: 'urgent',
  location_in_property: 'Cozinha', description: 'Reparo da torneira da cozinha',
  status: 'confirmed_schedule', scheduled_date: `${visitDate}T09:00:00Z`,
  notify_tenant: true, created_at: `${visitDate}T08:00:00Z`,
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  window.history.replaceState(null, '', '/')
})

it.each(['confirmed_schedule', 'notifying_tenant', 'resolved'])(
  'mostra a visita de um chamado %s e preserva a reserva no mesmo dia', async (status) => {
    const fetchMock = vi.fn().mockImplementation((url: string) => Promise.resolve(Response.json(
      url === `/api/tickets?property_id=${property.id}` ? [{ ...ticket, status }] : [],
    )))
    vi.stubGlobal('fetch', fetchMock)
    window.history.replaceState(null, '', `/imoveis/${property.id}`)
    render(<App />)
    const day = await screen.findByRole('gridcell', { name: /Reparo da torneira da cozinha/ })
    expect(day).toHaveClass('day-maintenance')
    expect(day.getAttribute('title')).toContain('Reserva confirmada')
    expect(day.getAttribute('title')).toContain('09:00')
    expect(fetchMock).toHaveBeenCalledWith(`/api/tickets?property_id=${property.id}`)
  },
)

it('não marca uma data pendente e atualiza o calendário após a confirmação do prestador', async () => {
  let confirmed = false
  vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => Promise.resolve(Response.json(
    url === `/api/tickets?property_id=${property.id}` ? [
      { ...ticket, status: confirmed ? 'resolved' : 'waiting_date_confirmation' },
      { ...ticket, id: 'another-property', property_id: 'outro-imovel' },
    ] : [],
  ))))
  window.history.replaceState(null, '', `/imoveis/${property.id}`)
  render(<App />)
  expect(await screen.findByRole('heading', { name: 'Calendário de ocupação' })).toBeInTheDocument()
  expect(screen.queryByRole('gridcell', { name: /Reparo da torneira da cozinha/ })).not.toBeInTheDocument()
  confirmed = true
  fireEvent(window, new Event('focus'))
  expect(await screen.findByRole('gridcell', { name: /Reparo da torneira da cozinha/ })).toHaveClass('day-maintenance')
})
