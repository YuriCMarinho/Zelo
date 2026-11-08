import { useEffect, useRef, useState, type FormEvent } from 'react'
import { sendChatMessage } from '../api/client'
import type { ChatMessage, ChatRole, Property } from '../contracts'
import { ZeloLogo } from './Header'

interface ChatPanelProps {
  property: Property
  messages: ChatMessage[]
  onNewMessage: (msg: ChatMessage) => void
  onTicketCreated?: (ticketId: string) => void
  scheduledVisit?: string | null
}

export function ChatPanel({
  property,
  messages,
  onNewMessage,
  onTicketCreated,
  scheduledVisit,
}: ChatPanelProps) {
  const [role, setRole] = useState<ChatRole>('hospede')
  const [draft, setDraft] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const visibleMessages = messages.filter((m) => m.propertyId === property.id)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [visibleMessages])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const text = draft.trim()
    if (!text || loading) return

    const timeStr = new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' }).format(new Date())

    // Adiciona a mensagem do usuário na interface
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      propertyId: property.id,
      channel: 'guest',
      sender: role,
      body: text,
      time: timeStr,
    }
    onNewMessage(userMsg)
    setDraft('')
    setLoading(true)

    try {
      const res = await sendChatMessage({
        propertyId: property.id,
        message: text,
        senderRole: role === 'camareira' ? 'cleaner' : 'tenant',
      })

      const agentMsg: ChatMessage = {
        id: crypto.randomUUID(),
        propertyId: property.id,
        channel: 'guest',
        sender: 'agent',
        body: res.responseText,
        time: new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' }).format(new Date()),
        ticketId: res.ticketId,
      }
      onNewMessage(agentMsg)

      if (res.ticketId && onTicketCreated) {
        onTicketCreated(res.ticketId)
      }
    } catch {
      onNewMessage({
        id: crypto.randomUUID(),
        propertyId: property.id,
        channel: 'guest',
        sender: 'agent',
        body: 'Recebemos seu relato! Nossa equipe e nossos agentes já estão cuidando da situação.',
        time: timeStr,
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="chat-container" aria-label={`Ponto único de chat: ${property.title}`}>
      {/* Header Conversa.dc.html */}
      <div className="chat-header">
        <ZeloLogo size={44} />
        <div>
          <h2>Converse sobre {property.title}</h2>
          <p>Atendimento do seu anfitrião · {property.neighborhood}</p>
        </div>
      </div>

      {/* Switcher de remetente (Hóspede x Camareira) para testar o Roteador Barato */}
      <div className="chat-role-bar">
        <span>Estou falando como:</span>
        <div className="role-chips" role="radiogroup" aria-label="Remetente da mensagem">
          <button
            type="button"
            className={`role-chip ${role === 'hospede' ? 'selected' : ''}`}
            aria-pressed={role === 'hospede'}
            onClick={() => setRole('hospede')}
          >
            Hóspede
          </button>
          <button
            type="button"
            className={`role-chip ${role === 'camareira' ? 'selected' : ''}`}
            aria-pressed={role === 'camareira'}
            onClick={() => setRole('camareira')}
          >
            Camareira
          </button>
        </div>
      </div>

      {/* Balões de mensagens */}
      <div className="chat-messages" aria-live="polite">
        {visibleMessages.length === 0 ? (
          <div style={{ textAlign: 'center', color: 'var(--mar-72)', margin: 'auto', fontSize: '14px' }}>
            Envie uma dúvida comercial (horário de check-in, wifi) ou um relato de manutenção (torneira quebrada,
            chuveiro frio).
          </div>
        ) : (
          visibleMessages.map((m) => {
            const isUser = m.sender === 'hospede' || m.sender === 'camareira' || m.sender === 'anfitriao'
            return (
              <div key={m.id} className={`msg-bubble ${isUser ? 'guest' : 'agent'}`}>
                <div>{m.body}</div>
                <div className="msg-meta">
                  {m.sender === 'agent' ? 'Assistente Zelo' : m.sender === 'camareira' ? 'Camareira' : 'Hóspede'}{' '}
                  · {m.time}
                </div>
              </div>
            )
          })
        )}

        {/* Banner de Visita Marcada conforme Conversa.dc.html */}
        {scheduledVisit && (
          <div className="msg-bubble scheduled">
            <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
              <rect x="3" y="5" width="18" height="16" rx="3" fill="none" stroke="currentColor" strokeWidth="2" />
              <path
                d="M3 10 H21 M8 3 V7 M16 3 V7"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
            <span>Visita marcada · {scheduledVisit}</span>
          </div>
        )}

        {loading && (
          <div className="msg-bubble agent" style={{ opacity: 0.7 }}>
            Digitando resposta...
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input bar */}
      <form className="chat-input-bar" onSubmit={handleSubmit}>
        <label htmlFor="msg-input" className="sr-only">
          Mensagem
        </label>
        <input
          id="msg-input"
          className="chat-input"
          placeholder="Escreva uma mensagem..."
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={loading}
          maxLength={1500}
        />
        <button
          type="submit"
          className="chat-send-btn"
          disabled={!draft.trim() || loading}
          aria-label="Enviar mensagem"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M5 12 H19 M13 6 L19 12 L13 18"
              fill="none"
              stroke="#F6F3EE"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </form>
    </div>
  )
}
