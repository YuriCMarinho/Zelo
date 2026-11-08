import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'

beforeEach(() => { localStorage.clear(); window.history.replaceState(null, '', '/') })
afterEach(() => { cleanup(); localStorage.clear(); window.history.replaceState(null, '', '/') })
const nextYear = new Date().getFullYear() + 1

describe('telas de gestão', () => {
  it('valida datas, cria uma reserva, impede conflitos e persiste os dados', async () => {
    const user = userEvent.setup()
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
    const user = userEvent.setup()
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
    const user = userEvent.setup()
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
