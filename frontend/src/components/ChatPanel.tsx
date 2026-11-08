import { useEffect, useRef, useState, type FormEvent } from 'react'
import { fetchChatHistory, getSessionId, sendChatMessage } from '../api/client'
import type { ChatMessage, ChatRole, Property } from '../contracts'
import { ZeloLogo } from './Header'

interface ChatPanelProps {
  property: Property
  messages: ChatMessage[]
  onNewMessage: (msg: ChatMessage) => void
  onTicketCreated?: (ticketId: string) => void
  onBookingCreated?: (bookingId: string) => void
  scheduledVisit?: string | null
}

const DEFAULT_GUEST_SUGGESTIONS = [
  'Quero reservar no próximo fim de semana',
  'Qual o horário de check-in?',
  'O chuveiro do banheiro parou de esquentar',
]

const DEFAULT_CLEANER_SUGGESTIONS = [
  'Vistoria pós-checkout: vazamento na pia da cozinha',
  'Lâmpada da suíte queimou após saída do hóspede',
  'Fechadura da porta de entrada está emperrando',
]

export function ChatPanel({
  property,
  messages,
  onNewMessage,
  onTicketCreated,
  onBookingCreated,
  scheduledVisit,
}: ChatPanelProps) {
  const [role, setRole] = useState<ChatRole>('hospede')
  const [draft, setDraft] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [isTyping, setIsTyping] = useState(false)
  const [suggestedActions, setSuggestedActions] = useState<string[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const typingDelayRef = useRef(0)
  const seenRemoteIdsRef = useRef<Set<string>>(new Set())

  const activeChannel: 'guest' | 'cleaner' = role === 'camareira' ? 'cleaner' : 'guest'
  const sessionId = getSessionId()

  const visibleMessages = messages.filter((m) => {
    if (m.propertyId !== property.id) return false
    const msgChannel = m.channel === 'cleaner' || m.sender === 'camareira' ? 'cleaner' : 'guest'
    return msgChannel === activeChannel
  })

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [visibleMessages.length, isTyping, role])

  useEffect(() => {
    if (!loading) return
    const timer = window.setTimeout(() => setIsTyping(true), typingDelayRef.current)
    return () => window.clearTimeout(timer)
  }, [loading])

  // Sincroniza notificações automáticas do anfitrião (ex: aprovação ou recusa da reserva)
  useEffect(() => {
    let active = true
    async function syncHistory() {
      const history = await fetchChatHistory(property.id, activeChannel, sessionId)
      if (!active || !history.length) return
      for (const item of history) {
        if (seenRemoteIdsRef.current.has(item.id)) continue
        const alreadyInLocal = messages.some(
          (m) => m.propertyId === property.id && m.body === item.body,
        )
        seenRemoteIdsRef.current.add(item.id)
        if (!alreadyInLocal && item.sender === 'agent') {
          onNewMessage({
            id: item.id,
            propertyId: property.id,
            channel: item.channel === 'cleaner' ? 'cleaner' : 'guest',
            sender: 'agent',
            body: item.body,
            time: new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' }).format(
              new Date(item.created_at),
            ),
            ticketId: item.ticket_id,
            bookingId: item.booking_id,
          })
        }
      }
    }
    const timer = window.setInterval(() => {
      void syncHistory()
    }, 4000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [property.id, activeChannel, sessionId, messages, onNewMessage])

  async function submitText(rawText: string) {
    const text = rawText.trim()
    if (!text || loading) return

    const timeStr = new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' }).format(new Date())

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      propertyId: property.id,
      channel: activeChannel,
      sender: role,
      body: text,
      time: timeStr,
    }
    onNewMessage(userMsg)
    setDraft('')
    const initialPause = 300 + Math.random() * 200
    typingDelayRef.current = initialPause
    setLoading(true)
    setError('')
    const startedAt = Date.now()

    try {
      const res = await sendChatMessage({
        propertyId: property.id,
        message: text,
        senderRole: role === 'camareira' ? 'cleaner' : 'tenant',
        sessionId,
        channel: activeChannel,
      })

      const variation = 0.85 + Math.random() * 0.3
      const typingTime = Math.min(700, Math.max(300, (250 + res.responseText.length * 2) * variation))
      const remainingPause = Math.max(0, initialPause - (Date.now() - startedAt))
      await new Promise<void>((resolve) => window.setTimeout(resolve, remainingPause + typingTime))

      const agentMsg: ChatMessage = {
        id: crypto.randomUUID(),
        propertyId: property.id,
        channel: activeChannel,
        sender: 'agent',
        body: res.responseText,
        time: new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' }).format(new Date()),
        ticketId: res.ticketId,
        bookingId: res.bookingId,
        suggestedActions: res.suggestedActions,
      }
      onNewMessage(agentMsg)
      if (res.suggestedActions?.length) {
        setSuggestedActions(res.suggestedActions)
      }

      if (res.ticketId && onTicketCreated) {
        onTicketCreated(res.ticketId)
      }
      if (res.bookingId && onBookingCreated) {
        onBookingCreated(res.bookingId)
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Não foi possível processar a mensagem. Tente novamente.')
      setDraft(text)
    } finally {
      setIsTyping(false)
      setLoading(false)
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    await submitText(draft)
  }

  const activeSuggestions =
    role === 'camareira'
      ? DEFAULT_CLEANER_SUGGESTIONS
      : suggestedActions.length > 0
      ? suggestedActions
      : DEFAULT_GUEST_SUGGESTIONS

  return (
    <div className="chat-container" aria-label={`Ponto único de chat: ${property.title}`}>
      {error && <p role="alert" className="form-error" style={{ padding: '12px 20px' }}>{error}</p>}
      {/* Header Conversa.dc.html */}
      <div className="chat-header">
        <ZeloLogo size={44} />
        <div style={{ flex: 1 }}>
          <h2>Converse sobre {property.title}</h2>
          <p>
            {role === 'camareira'
              ? `Canal Operacional de Vistoria & Limpeza · ${property.neighborhood}`
              : `Canal do Hóspede (Reservas, Dúvidas e Suporte) · ${property.neighborhood}`}
          </p>
        </div>
        <span
          style={{
            fontSize: '11px',
            padding: '4px 8px',
            borderRadius: '999px',
            background: 'var(--mar-08)',
            color: 'var(--mar-72)',
            fontWeight: 600,
          }}
          title="Sessão isolada para testes simultâneos sem mistura de histórico"
        >
          Sessão #{sessionId.slice(-4)}
        </span>
      </div>

      {/* Seletor de Canal Isolado (Canal do Hóspede vs Canal Operacional da Camareira) */}
      <div className="chat-role-bar" style={{ flexWrap: 'wrap', gap: '8px' }}>
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
        <small style={{ color: 'var(--mar-72)', fontSize: '12px', marginLeft: 'auto' }}>
          {role === 'hospede'
            ? 'Histórico exclusivo do hóspede (reservas, dúvidas ou relatos de manutenção).'
            : 'Histórico interno da equipe para vistoria pós-checkout.'}
        </small>
      </div>

      {/* Balões de mensagens */}
      <div className="chat-messages" aria-live="polite">
        {visibleMessages.length === 0 ? (
          <div style={{ textAlign: 'center', color: 'var(--mar-72)', margin: 'auto', fontSize: '14px', maxWidth: '460px' }}>
            {role === 'hospede' ? (
              <>
                Solicite uma <strong>reserva informando as datas</strong> (o anfitrião aprovará pelo valor calculado),
                tire dúvidas sobre o imóvel ou relate qualquer problema de manutenção durante a estadia.
              </>
            ) : (
              <>
                Canal de <strong>vistoria pós-checkout</strong>: relate avarias encontradas durante a limpeza
                (vazamentos, lâmpadas, ar-condicionado) para acionar prestadores antes do próximo check-in.
              </>
            )}
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

        {isTyping && (
          <div className="msg-bubble agent" style={{ opacity: 0.7 }}>
            Digitando resposta...
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Sugestões rápidas de interação */}
      <div
        style={{
          display: 'flex',
          gap: '8px',
          flexWrap: 'wrap',
          padding: '8px 16px',
          borderTop: '1px solid var(--mar-12)',
          background: 'var(--areia-clara, #faf8f5)',
        }}
        aria-label="Sugestões rápidas"
      >
        {activeSuggestions.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            disabled={loading}
            onClick={() => void submitText(suggestion)}
            style={{
              fontSize: '12px',
              padding: '5px 10px',
              borderRadius: '999px',
              border: '1px solid var(--mar-24)',
              background: '#fff',
              color: 'var(--mar-profundo)',
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {suggestion}
          </button>
        ))}
      </div>

      {/* Input bar */}
      <form className="chat-input-bar" onSubmit={handleSubmit}>
        <label htmlFor="msg-input" className="sr-only">
          Mensagem
        </label>
        <input
          id="msg-input"
          className="chat-input"
          placeholder={
            role === 'camareira'
              ? 'Relate um item da vistoria pós-checkout...'
              : 'Peça uma reserva com datas, tire dúvidas ou relate um problema...'
          }
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
