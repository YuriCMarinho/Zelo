import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StateTimeline } from './StateTimeline'

describe('StateTimeline Component', () => {
  it('exibe a máquina de estados com os 5 passos do Fluxo C', () => {
    render(<StateTimeline status="waiting_quotes" />)

    expect(screen.getByText(/1\. Coleta de Orçamentos/)).toBeInTheDocument()
    expect(screen.getByText(/2\. Decisão do Anfitrião/)).toBeInTheDocument()
    expect(screen.getByText(/3\. Regra Urgência × Agenda/)).toBeInTheDocument()
    expect(screen.getByText(/4\. Confirmação do Prestador/)).toBeInTheDocument()
    expect(screen.getByText(/5\. Aviso ao Hóspede e Conclusão/)).toBeInTheDocument()
  })
})
