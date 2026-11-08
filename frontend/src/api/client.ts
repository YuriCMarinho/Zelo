import type {
  AuditEvent,
  CostSummary,
  MaintenanceTicket,
  Property,
  Quote,
} from '../contracts'
import { properties as defaultProperties } from '../demo-data'

const API_BASE = '/api'

export async function fetchProperties(): Promise<Property[]> {
  try {
    const res = await fetch(`${API_BASE}/properties`)
    if (!res.ok) throw new Error(`Status ${res.status}`)
    const data = await res.json()
    if (Array.isArray(data) && data.length > 0) {
      // Mapeia para o contrato de Property da UI
      return data.map((item: Record<string, unknown>, index: number) => {
        const matched = defaultProperties.find((p) => p.id === item.id)
        const fallback = matched || (defaultProperties[index % defaultProperties.length] ?? defaultProperties[0])!
        const isRecife =
          String(item.city || '').toLowerCase().includes('recife') ||
          String(item.id || '').includes('recife') ||
          String(item.id || '').includes('portodigital')
        return {
          id: String(item.id || fallback.id),
          title: String(item.name || item.title || fallback.title),
          location: item.address
            ? `${String(item.address)}, ${String(item.city || 'Recife')}`
            : fallback.location,
          neighborhood: String(item.neighborhood || (isRecife ? 'Recife Antigo' : fallback.neighborhood)),
          description: String(item.description || fallback.description),
          image: fallback.image,
          gallery: fallback.gallery,
          nightlyRate: fallback.nightlyRate,
          guests: fallback.guests,
          bedrooms: fallback.bedrooms,
          beds: fallback.beds,
          baths: fallback.baths,
          rating: fallback.rating,
          reviews: fallback.reviews,
          amenities: fallback.amenities,
          occupancy: fallback.occupancy,
          tag: isRecife ? 'Porto Digital · Recife' : fallback.tag,
        }
      })
    }
  } catch {
    // Modo offline / mock fallback
  }
  return [...defaultProperties]
}

export async function fetchTickets(propertyId?: string): Promise<MaintenanceTicket[]> {
  const query = propertyId ? `?property_id=${encodeURIComponent(propertyId)}` : ''
  const res = await fetch(`${API_BASE}/tickets${query}`)
  if (!res.ok) throw new Error('Não foi possível carregar os chamados. Tente atualizar a lista.')
  const data: unknown = await res.json()
  if (!Array.isArray(data)) throw new Error('O atendimento retornou uma lista de chamados inválida.')
  return data as MaintenanceTicket[]
}

async function requestJson(url: string, init: RequestInit | undefined, failure: string): Promise<unknown> {
  let res: Response
  try {
    res = await fetch(url, init)
  } catch {
    throw new Error(`${failure}. Não foi possível conectar ao atendimento.`)
  }
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    const detail = typeof data?.detail === 'string' ? data.detail : `HTTP ${res.status}`
    throw new Error(`${failure}: ${detail}`)
  }
  try {
    return await res.json()
  } catch {
    throw new Error(`${failure}: resposta inválida do atendimento.`)
  }
}

export async function fetchTicketsForProperty(propertyId: string): Promise<MaintenanceTicket[]> {
  const data = await requestJson(`${API_BASE}/properties/${encodeURIComponent(propertyId)}/tickets`, undefined, 'Falha ao carregar chamados')
  if (!Array.isArray(data)) throw new Error('O atendimento retornou uma lista de chamados inválida.')
  return data as MaintenanceTicket[]
}

export async function fetchTicket(ticketId: string): Promise<MaintenanceTicket | null> {
  try {
    const res = await fetch(`${API_BASE}/tickets/${ticketId}`)
    if (res.ok) {
      return await res.json()
    }
  } catch {
    // fallback
  }
  return null
}

export async function fetchQuotes(ticketId: string): Promise<Quote[]> {
  const data = await requestJson(`${API_BASE}/tickets/${encodeURIComponent(ticketId)}/quotes`, undefined, 'Falha ao carregar orçamentos')
  if (!Array.isArray(data)) throw new Error('O atendimento retornou uma lista de orçamentos inválida.')
  return data as Quote[]
}

async function postTicket(url: string, body: unknown, failure: string): Promise<MaintenanceTicket> {
  const data = await requestJson(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  }, failure)
  if (!data || typeof data !== 'object' || !('id' in data) || typeof data.id !== 'string' ||
    !('status' in data) || typeof data.status !== 'string') {
    throw new Error(`${failure}: resposta inválida do atendimento.`)
  }
  return data as MaintenanceTicket
}

export function approveQuote(
  ticketId: string,
  providerId: string,
  runId?: string,
): Promise<MaintenanceTicket> {
  return postTicket(`${API_BASE}/tickets/${encodeURIComponent(ticketId)}/approve`, {
    provider_id: providerId,
    run_id: runId || `run-approve-${Date.now()}`,
  }, 'Falha ao aprovar orçamento')
}

export function startTicketResolution(ticketId: string): Promise<MaintenanceTicket> {
  return postTicket(`${API_BASE}/tickets/${encodeURIComponent(ticketId)}/start-resolution`, undefined, 'Falha ao iniciar resolução')
}

function postProviderReply(url: string, body: unknown): Promise<MaintenanceTicket> {
  return postTicket(url, body, 'Falha ao registrar resposta do prestador')
}

/** Prestador (canal simulado/allowlist) envia o orçamento pedido pelo Nó 3. */
export function submitQuoteResponse(
  ticketId: string,
  providerId: string,
  reply: { amount: number; description?: string; proposedAvailability?: string },
): Promise<MaintenanceTicket> {
  return postProviderReply(`${API_BASE}/tickets/${ticketId}/quotes/${providerId}/response`, {
    amount: reply.amount,
    description: reply.description,
    proposed_availability: reply.proposedAvailability,
  })
}

/** Prestador escolhido aceita ou recusa a data proposta (devolutiva do dia). */
export function submitDateResponse(
  ticketId: string,
  accepted: boolean,
  message?: string,
): Promise<MaintenanceTicket> {
  return postProviderReply(`${API_BASE}/tickets/${ticketId}/date-response`, { accepted, message })
}

export interface ChatApiResult {
  runId: string
  propertyId: string
  routeDestination: string
  responseText: string
  ticketId: string | null
  suggestedActions: string[]
}

export async function sendChatMessage(params: {
  propertyId: string
  message: string
  senderRole: 'tenant' | 'cleaner'
  runId?: string
}): Promise<ChatApiResult> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        property_id: params.propertyId,
        message: params.message,
        sender_role: params.senderRole,
        run_id: params.runId,
      }),
    })
  } catch {
    throw new Error('Não foi possível conectar ao atendimento. Verifique se o backend está disponível e tente novamente.')
  }
  if (!res.ok) {
    if (res.status === 404) throw new Error('Este imóvel não foi encontrado no atendimento. Atualize a página para carregar os imóveis disponíveis.')
    if (res.status === 400) throw new Error('A mensagem não pôde ser processada. Revise o conteúdo e tente novamente.')
    throw new Error(`O atendimento está indisponível (HTTP ${res.status}). Tente novamente em instantes.`)
  }
  let data: Record<string, unknown>
  try {
    data = await res.json()
    if (!data || typeof data.response_text !== 'string' || !data.response_text.trim()) throw new Error()
  } catch {
    throw new Error('O atendimento retornou uma resposta inválida. Tente novamente.')
  }
  return {
    runId: String(data.run_id),
    propertyId: String(data.property_id),
    routeDestination: String(data.route_destination),
    responseText: data.response_text as string,
    ticketId: typeof data.ticket_id === 'string' ? data.ticket_id : null,
    suggestedActions: Array.isArray(data.suggested_actions) ? data.suggested_actions : [],
  }
}

export async function fetchCostSummary(): Promise<CostSummary> {
  try {
    const res = await fetch(`${API_BASE}/costs/summary`)
    if (res.ok) {
      return await res.json()
    }
  } catch {
    // fallback
  }
  return {
    total_cost_usd: 0,
    total_input_tokens: 1250,
    total_output_tokens: 420,
    total_calls: 8,
    by_node: { router: 0.0001, validator_node2: 0.0003, resolver_node3: 0.0012 },
    by_model: { 'Qwen/Qwen3.5-4B': 0.0004, 'Qwen/Qwen3.5-9B': 0.0012 },
    budget_limit_usd: 25,
    percentage_used: (0 / 25) * 100,
  }
}

export async function fetchAuditEvents(ticketId?: string): Promise<AuditEvent[]> {
  try {
    const url = ticketId ? `${API_BASE}/audit?ticket_id=${ticketId}` : `${API_BASE}/audit`
    const res = await fetch(url)
    if (res.ok) {
      return await res.json()
    }
  } catch {
    // fallback
  }
  return []
}

export async function resetDemoData(): Promise<{ status: string; message: string }> {
  try {
    const res = await fetch(`${API_BASE}/demo/reset`, { method: 'POST' })
    if (res.ok) {
      return await res.json()
    }
  } catch {
    // fallback
  }
  return { status: 'success', message: 'Ambiente de demonstração reinicializado (modo local).' }
}

