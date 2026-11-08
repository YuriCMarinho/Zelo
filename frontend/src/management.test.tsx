import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { ManagementPage } from './management'
import { properties } from './demo-data'
import type { MaintenanceTicket } from './contracts'

beforeEach(() => { localStorage.clear(); window.history.replaceState(null, '', '/') })
afterEach(() => { cleanup(); vi.unstubAllGlobals(); localStorage.clear(); window.history.replaceState(null, '', '/') })
const nextYear = new Date().getFullYear() + 1

// delay: null tira o setTimeout por tecla; com ele, o 1º teste passava de 5 s na suíte completa.
describe('telas de gestão', () => {
  it('valida datas, cria uma reserva, impede conflitos e persiste os dados', async () => {
    const user = userEvent.setup({ delay: null })
    window.history.replaceState(null, '', '/reservas')
    render(<App />)
    async function fill(guest: string, start: string, end: string) {
      await user.click(screen.getByRole('button', { name: '+ Nova reserva' }))
      const form = screen.getByRole('heading', { name: 'Nova reserva' }).closest('form')!
      await user.type(within(form).getByLabelText('Nome do hóspede'), guest)
      await user.type(within(form).getByLabelText('Check-in'), `${nextYear}-01-${start}`)
      await user.type(within(form).getByLabelText('Check-out'), `${nextYear}-01-${end}`)
      await user.click(within(form).getByRole('button', { name: 'Salvar reserva' }))
      return form
    }
    const form = await fill('Ana Costa', '10', '09')
    expect(screen.getByRole('alert')).toHaveTextContent('posterior ao check-in')
    await user.clear(within(form).getByLabelText('Check-out'))
    await user.type(within(form).getByLabelText('Check-out'), `${nextYear}-01-14`)
    await user.click(within(form).getByRole('button', { name: 'Salvar reserva' }))
    expect(screen.getByRole('heading', { name: 'Ana Costa' })).toBeInTheDocument()
    await fill('Pedro Silva', '12', '16')
    expect(screen.getByRole('alert')).toHaveTextContent('já possui uma reserva')
    cleanup(); render(<App />)
    await user.type(screen.getByLabelText('Hóspede'), 'Ana Costa')
    expect(screen.getByRole('heading', { name: 'Ana Costa' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Marina Oliveira' })).not.toBeInTheDocument()
    const reservation = screen.getByRole('heading', { name: 'Ana Costa' }).closest('article')!
    await user.click(within(reservation).getByRole('link', { name: /Ver imóvel/ }))
    for (let month = 0; month < 12 - new Date().getMonth(); month += 1) {
      await user.click(screen.getByRole('button', { name: 'Próximo mês' }))
    }
    expect(screen.getAllByTitle('Reserva de Ana Costa')).toHaveLength(4)
  })

  it('cria um chamado e acompanha até a conclusão', async () => {
    const user = userEvent.setup({ delay: null })
    window.history.replaceState(null, '', '/manutencao')
    render(<App />)
    await user.click(screen.getByRole('button', { name: '+ Novo chamado' }))
    await user.type(screen.getByLabelText('Assunto'), 'Torneira vazando')
    await user.type(screen.getByLabelText('Descrição'), 'Vazamento na cozinha.')
    await user.click(screen.getByRole('button', { name: 'Criar chamado' }))
    const card = screen.getByRole('heading', { name: 'Torneira vazando' }).closest('article')!
    await user.click(within(card).getByRole('button', { name: 'Iniciar atendimento' }))
    await user.click(within(card).getByRole('button', { name: 'Marcar como concluído' }))
    expect(within(card).getByText('✓ Atendimento concluído')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Status'), '0')
    expect(screen.queryByRole('heading', { name: 'Torneira vazando' })).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Status'), '2')
    expect(screen.getByRole('heading', { name: 'Torneira vazando' })).toBeInTheDocument()
  })

  it('salva preferências e desfaz mudanças não salvas', async () => {
    const user = userEvent.setup({ delay: null })
    window.history.replaceState(null, '', '/configuracoes')
    render(<App />)
    await user.clear(screen.getByLabelText('Nome'))
    await user.type(screen.getByLabelText('Nome'), 'Yuri')
    await user.type(screen.getByLabelText('E-mail'), 'yuri@example.com')
    await user.click(screen.getByRole('checkbox', { name: /Reservas e estadias/ }))
    await user.click(screen.getByRole('button', { name: 'Salvar preferências' }))
    cleanup(); render(<App />)
    expect(screen.getByLabelText('Nome')).toHaveValue('Yuri')
    expect(screen.getByRole('checkbox', { name: /Reservas e estadias/ })).not.toBeChecked()
    await user.type(screen.getByLabelText('Nome'), ' Silva')
    await user.click(screen.getByRole('button', { name: 'Desfazer alterações' }))
    expect(screen.getByLabelText('Nome')).toHaveValue('Yuri')
    expect(screen.getByLabelText('E-mail')).toHaveValue('yuri@example.com')
  })
})

const chatTicket: MaintenanceTicket = {
  id: 'ticket-chat-1', run_id: 'run-chat-1', property_id: 'prop-real-1',
  reported_by_role: 'tenant', category: 'plumber', urgency: 'urgent',
  location_in_property: 'Cozinha', description: 'Torneira da cozinha vazando',
  status: 'awaiting_adm_approval', notify_tenant: true, created_at: '2026-11-08T07:00:00Z',
}
const realProperties = [{ ...properties[0]!, id: chatTicket.property_id, title: 'Imóvel do chat' }, properties[1]!]

describe('chamados do chat na gestão de manutenção', () => {
  it('carrega chamados reais, filtra por imóvel e status e abre o atendimento', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(Response.json([chatTicket]))
    vi.stubGlobal('fetch', fetchMock)
    const navigate = vi.fn()
    render(<ManagementPage view="manutencao" navigate={navigate} propertiesList={realProperties} />)
    const card = (await screen.findByRole('heading', { name: chatTicket.description })).closest('article')!
    expect(fetchMock).toHaveBeenCalledWith('/api/tickets')
    expect(within(card).getByText('Imóvel do chat')).toBeInTheDocument()
    expect(within(card).getByText('Aguardando sua aprovação')).toBeInTheDocument()
    expect(within(card).queryByRole('button', { name: 'Marcar como concluído' })).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Status'), '0')
    expect(screen.queryByRole('heading', { name: chatTicket.description })).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Status'), '1')
    await user.selectOptions(screen.getByLabelText('Imóvel'), properties[1]!.id)
    expect(screen.queryByRole('heading', { name: chatTicket.description })).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Imóvel'), chatTicket.property_id)
    await user.click(screen.getByRole('link', { name: 'Acompanhar atendimento' }))
    expect(navigate).toHaveBeenCalledWith(`/imoveis/${chatTicket.property_id}?aba=adm`)
    expect(localStorage.getItem('zelo-tickets-v1')).toBeNull()
  })

  it('atualiza o status real quando a janela volta ao foco', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(Response.json([chatTicket]))
      .mockResolvedValue(Response.json([{ ...chatTicket, status: 'resolved' }]))
    vi.stubGlobal('fetch', fetchMock)
    render(<ManagementPage view="manutencao" navigate={vi.fn()} propertiesList={realProperties} />)
    await screen.findByText('Aguardando sua aprovação')
    fireEvent(window, new Event('focus'))
    expect(await screen.findByText('Concluído', { selector: 'p' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('mostra falha de carregamento e permite tentar novamente', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(new Response('', { status: 503 }))
      .mockResolvedValue(Response.json([chatTicket])))
    render(<ManagementPage view="manutencao" navigate={vi.fn()} propertiesList={realProperties} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível atualizar')
    expect(screen.queryByText('Nenhum chamado por aqui')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Atualizar chamados' }))
    expect(await screen.findByRole('heading', { name: chatTicket.description })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
