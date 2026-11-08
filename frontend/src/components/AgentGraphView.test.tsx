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

  it('permite alternar os filtros de cidade e imóvel através do dropbox', async () => {
    const user = userEvent.setup()
    render(<AgentGraphView navigate={() => {}} propertiesList={[...properties]} />)

    const select = screen.getByRole('combobox', { name: 'Filtrar por Cidade ou Imóvel' }) as HTMLSelectElement
    expect(select).toBeInTheDocument()
    expect(select.value).toBe('all')

    // Filtra por cidade
    await user.selectOptions(select, 'city:Fortaleza')
    expect(select.value).toBe('city:Fortaleza')

    // Filtra por imóvel específico
    await user.selectOptions(select, 'casa-aurora')
    expect(select.value).toBe('casa-aurora')

    // Retorna para todos
    await user.selectOptions(select, 'all')
    expect(select.value).toBe('all')
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

  it('renderiza o dropbox de cidades e imóveis dentro da div do grafo e não exibe elementos ruidosos', () => {
    render(<AgentGraphView navigate={() => {}} propertiesList={[...properties]} />)

    // O botão de guia explicativo e a dica solta foram removidos por feedback de design
    expect(screen.queryByRole('button', { name: /Como funciona a Observabilidade/ })).not.toBeInTheDocument()
    expect(screen.queryByText('Clique em qualquer bolinha para inspecionar')).not.toBeInTheDocument()
    expect(screen.queryByText('1. Traces & Spans')).not.toBeInTheDocument()

    // O dropbox de cidades/imóveis está dentro da div do grafo
    const select = screen.getByRole('combobox', { name: 'Filtrar por Cidade ou Imóvel' })
    expect(select).toBeInTheDocument()
    expect(screen.getByText('Cidade / Imóvel:')).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Filtrar por Cidade' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Filtrar por Imóvel' })).toBeInTheDocument()
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
