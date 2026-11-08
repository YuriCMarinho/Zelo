import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../App'
import { AgentGraphView } from './AgentGraphView'
import { properties } from '../demo-data'

afterEach(() => {
  cleanup()
  window.history.replaceState(null, '', '/')
})

describe('AgentGraphView Component', () => {
  it('renderiza o cabeçalho, nós de imóveis e fases dos agentes', () => {
    render(<AgentGraphView navigate={() => {}} propertiesList={[...properties]} />)

    expect(screen.getByRole('heading', { name: 'Grafo de Fases dos Agentes & Imóveis' })).toBeInTheDocument()
    expect(screen.getAllByText('Casa Aurora').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Loft Jardim').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/Studio Tech/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/Roteador/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/Nó 1: Comercial/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/Nó 2: Validador/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/3.2 Decisão ADM/).length).toBeGreaterThanOrEqual(1)
  })

  it('permite alternar os filtros de imóveis', async () => {
    const user = userEvent.setup()
    render(<AgentGraphView navigate={() => {}} propertiesList={[...properties]} />)

    const auroraBtn = screen.getByRole('button', { name: 'Casa Aurora' })
    await user.click(auroraBtn)
    expect(auroraBtn).toHaveClass('active')

    const allBtn = screen.getByRole('button', { name: 'Todos os Imóveis' })
    await user.click(allBtn)
    expect(allBtn).toHaveClass('active')
  })

  it('abre detalhes e telemetria Langfuse ao clicar em uma bolinha do grafo', async () => {
    const user = userEvent.setup()
    render(<AgentGraphView navigate={() => {}} propertiesList={[...properties]} />)

    const validatorNode = screen.getByRole('button', { name: /Selecionar nó Nó 2: Validador/ })
    await user.click(validatorNode)

    expect(screen.getByRole('heading', { name: 'Nó 2: Validador' })).toBeInTheDocument()
    expect(screen.getByText('Qwen/Qwen3.5-4B (Featherless)')).toBeInTheDocument()
    expect(screen.getByText('validator.ticket_structuring')).toBeInTheDocument()
    expect(screen.getByText('run-demo-001')).toBeInTheDocument()
  })

  it('renderiza o filtro de casas dentro do card e não exibe elementos ruidosos removidos', () => {
    render(<AgentGraphView navigate={() => {}} propertiesList={[...properties]} />)

    // O botão de guia explicativo e a dica solta foram removidos por feedback de design
    expect(screen.queryByRole('button', { name: /Como funciona a Observabilidade/ })).not.toBeInTheDocument()
    expect(screen.queryByText('Clique em qualquer bolinha para inspecionar')).not.toBeInTheDocument()
    expect(screen.queryByText('1. Traces & Spans')).not.toBeInTheDocument()

    // O filtro de nós por imóvel está no toolbar interno do card
    const cardToolbar = screen.getByRole('radiogroup', { name: 'Filtrar nós por imóvel' })
    expect(cardToolbar).toBeInTheDocument()
  })
})

describe('Navegação até o Grafo de Agentes pelo Header', () => {
  it('navega para /agentes e renderiza o grafo a partir do menu principal', async () => {
    const user = userEvent.setup()
    render(<App />)

    const navLink = screen.getByRole('link', { name: 'Grafo de Agentes' })
    await user.click(navLink)

    expect(screen.getByRole('heading', { name: 'Grafo de Fases dos Agentes & Imóveis' })).toBeInTheDocument()
  })
})
