import { useState } from 'react'
import { sendChatMessage, startTicketResolution } from '../api/client'
import type { Property } from '../contracts'

interface ProviderSimulatorProps {
  property: Property
  currentTicketId?: string | null
  onTicketUpdated: () => void
}

export function ProviderSimulator({
  property,
  currentTicketId,
  onTicketUpdated,
}: ProviderSimulatorProps) {
  const [running, setRunning] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)

  async function handleSimulateMaintenance() {
    setRunning(true)
    setFeedback(null)
    try {
      const res = await sendChatMessage({
        propertyId: property.id,
        message: 'O chuveiro do banheiro da suíte não esquenta e está saindo água gelada.',
        senderRole: 'tenant',
      })
      if (res.ticketId) {
        setFeedback(`Ticket #${res.ticketId.slice(0, 8)} aberto e orçamentos solicitados!`)
      } else {
        setFeedback('Mensagem enviada com sucesso ao assistente.')
      }
      onTicketUpdated()
    } catch (err: unknown) {
      setFeedback(`Erro ao simular: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setRunning(false)
    }
  }

  async function handleSimulateCommercial() {
    setRunning(true)
    setFeedback(null)
    try {
      const res = await sendChatMessage({
        propertyId: property.id,
        message: 'Qual é o horário padrão de check-in e como funciona o wi-fi?',
        senderRole: 'tenant',
      })
      setFeedback(`Nó 1 Comercial respondeu: "${res.responseText.slice(0, 80)}..."`)
      onTicketUpdated()
    } catch (err: unknown) {
      setFeedback(`Erro: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setRunning(false)
    }
  }

  async function handleTriggerResolution() {
    if (!currentTicketId) return
    setRunning(true)
    setFeedback(null)
    try {
      await startTicketResolution(currentTicketId)
      setFeedback('Nó 3 ativado: cotações solicitadas e síntese enviada para aprovação!')
      onTicketUpdated()
    } catch (err: unknown) {
      setFeedback(`Erro ao iniciar resolução: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="simulator-box" aria-label="Simulador de cenários do avaliador">
      <div>
        <span className="eyebrow">CONTROLE DE DEMONSTRAÇÃO · HACKATHON</span>
        <h3 style={{ margin: '4px 0 2px', fontSize: '18px' }}>Simulador de Cenários dos Agentes</h3>
        <p style={{ margin: 0, fontSize: '13px', color: 'var(--mar-72)' }}>
          Dispare cenários do Fluxo A e Fluxo C para acompanhar a máquina de estados em tempo real.
        </p>
      </div>

      <div className="scenario-btns">
        <button
          type="button"
          className="scenario-btn"
          disabled={running}
          onClick={handleSimulateMaintenance}
        >
          <strong>Relato de Manutenção</strong>
          <span>Abre ticket de chuveiro e coleta 3 orçamentos (Nó 2 → Nó 3).</span>
        </button>

        <button
          type="button"
          className="scenario-btn"
          disabled={running}
          onClick={handleSimulateCommercial}
        >
          <strong>Dúvida Comercial</strong>
          <span>Roteador direciona ao Nó 1 (Comercial) sem gerar ticket.</span>
        </button>

        {currentTicketId && (
          <button
            type="button"
            className="scenario-btn"
            disabled={running}
            onClick={handleTriggerResolution}
          >
            <strong>Re-executar Resolução</strong>
            <span>Re-dispara o Nó 3 no chamado #{currentTicketId.slice(0, 8)}.</span>
          </button>
        )}
      </div>

      {feedback && (
        <div
          style={{
            padding: '10px 14px',
            borderRadius: '10px',
            background: 'var(--mar-08)',
            fontSize: '13px',
            fontWeight: 500,
          }}
        >
          {feedback}
        </div>
      )}
    </div>
  )
}
