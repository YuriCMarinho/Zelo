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
})
