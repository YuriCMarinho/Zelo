import { useState } from 'react'
import {
  fetchQuotes,
  sendChatMessage,
  startTicketResolution,
  submitDateResponse,
  submitQuoteResponse,
} from '../api/client'
import type { Property } from '../contracts'

interface ProviderSimulatorProps {
  property: Property
  currentTicketId?: string | null
  ticketStatus?: string | null
  onTicketUpdated: () => void
}

// Respostas de exemplo dos prestadores (canal simulado; nada sai para terceiros).
const SAMPLE_QUOTES = [
  { amount: 180, description: 'Troca do componente com garantia de 90 dias', proposedAvailability: 'Amanhã cedo' },
  { amount: 240, description: 'Reparo completo e teste de vazamento', proposedAvailability: 'Hoje à tarde' },
  { amount: 150, description: 'Reparo simples, peça à parte', proposedAvailability: 'Sexta-feira' },
]

export function ProviderSimulator({
  property,
  currentTicketId,
  ticketStatus,
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

  async function handleSimulateNodeS() {
    setRunning(true)
    setFeedback(null)
    try {
      const res = await sendChatMessage({
        propertyId: property.id,
        message: 'A parede da sala está com a pintura descascando e com mofo.',
        senderRole: 'tenant',
      })
      if (res.ticketId) {
        setFeedback(`Ticket #${res.ticketId.slice(0, 8)} aberto! Sem prestador prévio: Nó S acionado para busca e validação.`)
      } else {
        setFeedback('Mensagem enviada com sucesso ao assistente.')
      }
      onTicketUpdated()
    } catch (err: unknown) {
      setFeedback(`Erro ao simular Nó S: ${err instanceof Error ? err.message : String(err)}`)
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

  async function runProviderAction(action: () => Promise<string>) {
    setRunning(true)
    setFeedback(null)
    try {
      setFeedback(await action())
      onTicketUpdated()
    } catch (err: unknown) {
      setFeedback(`Erro do prestador: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setRunning(false)
    }
  }

  function handleProvidersSendQuotes() {
    if (!currentTicketId) return
    void runProviderAction(async () => {
      let quotes = await fetchQuotes(currentTicketId)
      let pending = quotes.filter((q) => q.status === 'requested')
      if (pending.length === 0 && (ticketStatus === 'open' || ticketStatus === 'requesting_quotes')) {
        await startTicketResolution(currentTicketId)
        quotes = await fetchQuotes(currentTicketId)
        pending = quotes.filter((q) => q.status === 'requested')
      }
      if (pending.length === 0) {
        return 'Nenhum prestador pendente no momento para enviar orçamento.'
      }
      for (const [index, quote] of pending.entries()) {
        await submitQuoteResponse(currentTicketId, quote.provider_id, SAMPLE_QUOTES[index % SAMPLE_QUOTES.length]!)
      }
      return `${pending.length} prestador(es) enviaram orçamento. O anfitrião já pode decidir.`
    })
  }

  function handleDateReply(accepted: boolean) {
    if (!currentTicketId) return
    void runProviderAction(async () => {
      await submitDateResponse(
        currentTicketId,
        accepted,
        accepted ? 'Confirmo a data proposta.' : 'Não consigo nesta data.',
      )
      return accepted
        ? 'Prestador confirmou o dia. Chamado concluído e hóspede avisado se estiver no imóvel.'
        : 'Prestador recusou. O agente vai propor a próxima janela da agenda.'
    })
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
          <span>Abre ticket de chuveiro e pede orçamentos aos prestadores (Nó 2 → Nó 3).</span>
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

        <button
          type="button"
          className="scenario-btn"
          disabled={running}
          onClick={handleSimulateNodeS}
        >
          <strong>Simular Descoberta (Nó S)</strong>
          <span>Relata pintura em RJ (sem prestador prévio): aciona Nó S para buscar e validar.</span>
        </button>

        {currentTicketId && (ticketStatus === 'waiting_quotes' || ticketStatus === 'requesting_quotes') && (
          <button
            type="button"
            className="scenario-btn"
            disabled={running}
            onClick={handleProvidersSendQuotes}
          >
            <strong>Prestadores respondem</strong>
            <span>Cada prestador consultado envia seu orçamento (Passo 1).</span>
          </button>
        )}

        {currentTicketId && ticketStatus === 'waiting_date_confirmation' && (
          <>
            <button
              type="button"
              className="scenario-btn"
              disabled={running}
              onClick={() => handleDateReply(true)}
            >
              <strong>Prestador aceita a data</strong>
              <span>Devolutiva do dia positiva (Passo 4).</span>
            </button>
            <button
              type="button"
              className="scenario-btn"
              disabled={running}
              onClick={() => handleDateReply(false)}
            >
              <strong>Prestador recusa a data</strong>
              <span>Volta ao Passo 3 com a próxima janela.</span>
            </button>
          </>
        )}

        {currentTicketId && (ticketStatus === 'open' || ticketStatus === 'no_providers_fallback') && (
          <button
            type="button"
            className="scenario-btn"
            disabled={running}
            onClick={handleTriggerResolution}
          >
            <strong>{ticketStatus === 'no_providers_fallback' ? 'Buscar prestadores de novo' : 'Iniciar Resolução'}</strong>
            <span>Dispara o Nó 3 no chamado #{currentTicketId.slice(0, 8)}.</span>
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
