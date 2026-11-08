import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { parseRoute } from './routes'

afterEach(() => {
  cleanup()
  window.history.replaceState(null, '', '/')
})

describe('navegação por imóvel', () => {
  it('interpreta imóvel e aba pela URL e volta para a listagem em rotas desconhecidas', () => {
    expect(parseRoute('/imoveis/loft-jardim', '?aba=adm')).toEqual({ view: 'property', propertyId: 'loft-jardim', tab: 'adm' })
    expect(parseRoute('/imoveis/inexistente', '')).toEqual({ view: 'listing' })
  })

  it('abre um imóvel e alterna entre calendário, chat e sessão ADM', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('link', { name: /Casa Aurora/ }))
    expect(screen.getByRole('heading', { name: 'Calendário de ocupação' })).toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: 'Chat do imóvel' }))
    expect(screen.getByRole('heading', { name: 'Converse sobre Casa Aurora' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Camareira' }))
    await user.type(screen.getByRole('textbox', { name: 'Mensagem' }), 'A torneira está vazando')
    await user.click(screen.getByRole('button', { name: 'Enviar mensagem' }))
    expect(screen.getByText('A torneira está vazando')).toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: 'Agente ⇄ Anfitrião' }))
    expect(screen.getByText(/Somente as decisões deste imóvel/)).toBeInTheDocument()
    expect(screen.queryByText('A torneira está vazando')).not.toBeInTheDocument()
  })

  it('mantém mensagens separadas entre imóveis', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('link', { name: /Casa Aurora/ }))
    await user.click(screen.getByRole('link', { name: 'Chat do imóvel' }))
    await user.type(screen.getByRole('textbox', { name: 'Mensagem' }), 'Mensagem da Aurora')
    await user.click(screen.getByRole('button', { name: 'Enviar mensagem' }))
    await user.click(screen.getByRole('link', { name: 'Imóveis' }))
    await user.click(screen.getByRole('link', { name: /Loft Jardim/ }))
    await user.click(screen.getByRole('link', { name: 'Chat do imóvel' }))
    expect(screen.queryByText('Mensagem da Aurora')).not.toBeInTheDocument()
  })

  it('permite escolher um orçamento apenas na demonstração local', async () => {
    const user = userEvent.setup()
    expect(parseRoute('/imoveis/casa-aurora', '?aba=orcamentos')).toEqual({ view: 'property', propertyId: 'casa-aurora', tab: 'orcamentos' })
    render(<App />)
    await user.click(screen.getByRole('link', { name: /Casa Aurora/ }))
    await user.click(screen.getByRole('link', { name: 'Orçamentos' }))
    await user.click(screen.getByRole('radio', { name: /Volt Reparos/ }))
    expect(screen.getByRole('radio', { name: /Volt Reparos/ })).toHaveAttribute('aria-checked', 'true')
    await user.click(screen.getByRole('button', { name: /Escolher Volt Reparos/ }))
    expect(screen.getByText('Escolha simulada')).toBeInTheDocument()
    expect(screen.getByText(/nenhuma contratação ou agendamento/)).toBeInTheDocument()
  })
  it('permite ao anfitrião aprovar um orçamento na sessão ADM e avançar para agendamento', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('link', { name: /Casa Aurora/ }))
    await user.click(screen.getByRole('link', { name: 'Agente ⇄ Anfitrião' }))

    // Verifica que a síntese de orçamentos e cartões estão visíveis
    expect(await screen.findByText(/Pedimos orçamento/)).toBeInTheDocument()
    expect(screen.getByText('Carlos Eletricista')).toBeInTheDocument()
    expect(screen.getByText('Volt Reparos')).toBeInTheDocument()

    // Botão inicial de aprovação para Carlos
    const approveBtn = screen.getByRole('button', { name: /Aprovar Carlos/ })
    expect(approveBtn).toBeInTheDocument()

    // Clica no cartão da Volt Reparos e vê o botão mudar
    await user.click(screen.getByText('Volt Reparos'))
    expect(screen.getByRole('button', { name: /Aprovar Volt Reparos/ })).toBeInTheDocument()

    // Aprova o orçamento
    await user.click(screen.getByRole('button', { name: /Aprovar Volt Reparos/ }))
    expect(await screen.findByText(/Orçamento aprovado e agendamento confirmado/)).toBeInTheDocument()

    // Volta ao chat e verifica o banner de visita marcada
    await user.click(screen.getByRole('link', { name: 'Chat do imóvel' }))
    expect(await screen.findByText(/Visita marcada/)).toBeInTheDocument()
  })

  it('navega para o painel de auditoria & custos pela barra de navegação', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('link', { name: 'Auditoria' }))
    expect(screen.getByRole('heading', { name: 'Consumo do Orçamento Featherless' })).toBeInTheDocument()
    expect(screen.getByText(/Teto global: US\$/)).toBeInTheDocument()
  })

  it('exibe a máquina de estados com os 5 passos do Fluxo C', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('link', { name: /Casa Aurora/ }))
    await user.click(screen.getByRole('link', { name: 'Chat do imóvel' }))

    expect(screen.getByText(/1\. Coleta de Orçamentos/)).toBeInTheDocument()
    expect(screen.getByText(/2\. Decisão do Anfitrião/)).toBeInTheDocument()
    expect(screen.getByText(/3\. Regra Urgência × Agenda/)).toBeInTheDocument()
    expect(screen.getByText(/4\. Confirmação do Prestador/)).toBeInTheDocument()
    expect(screen.getByText(/5\. Aviso ao Hóspede e Conclusão/)).toBeInTheDocument()

    // Simulador de cenários presente
    expect(screen.getByText('Simulador de Cenários dos Agentes')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Relato de Manutenção/ })).toBeInTheDocument()
  })

  it('abre e fecha o modal de reset de demonstração para avaliadores', async () => {
    const user = userEvent.setup()
    render(<App />)
    const resetBtn = screen.getByRole('button', { name: /Resetar Demo/ })
    expect(resetBtn).toBeInTheDocument()
    await user.click(resetBtn)
    expect(screen.getByText('Resetar Dados da Demonstração?')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Cancelar' }))
    expect(screen.queryByText('Resetar Dados da Demonstração?')).not.toBeInTheDocument()
  })

  it('abre o menu mobile pelas 3 linhas e navega até reservas', async () => {
    const user = userEvent.setup()
    render(<App />)
    const menuBtn = screen.getByRole('button', { name: 'Abrir menu de navegação' })
    expect(menuBtn).toBeInTheDocument()
    await user.click(menuBtn)
    expect(screen.getByRole('navigation', { name: 'Navegação mobile' })).toBeInTheDocument()
    const mobileLinks = screen.getAllByRole('link', { name: 'Reservas' })
    await user.click(mobileLinks[mobileLinks.length - 1]!)
    expect(screen.getByRole('button', { name: '+ Nova reserva' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Navegação mobile' })).not.toBeInTheDocument()
  })
})
