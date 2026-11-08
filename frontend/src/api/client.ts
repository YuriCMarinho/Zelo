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

export async function fetchTicketsForProperty(propertyId: string): Promise<MaintenanceTicket[]> {
  try {
    const res = await fetch(`${API_BASE}/properties/${propertyId}/tickets`)
    if (res.ok) {
      return await res.json()
    }
  } catch {
    // fallback
  }
  return []
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
  try {
    const res = await fetch(`${API_BASE}/tickets/${ticketId}/quotes`)
    if (res.ok) {
      return await res.json()
    }
  } catch {
    // fallback
  }
  return []
}

export async function approveQuote(
  ticketId: string,
  providerId: string,
  runId?: string,
): Promise<MaintenanceTicket> {
  try {
    const res = await fetch(`${API_BASE}/tickets/${ticketId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider_id: providerId,
        run_id: runId || `run-approve-${Date.now()}`,
      }),
    })
    if (res.ok) {
      return await res.json()
    }
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail ?? `Falha ao aprovar orçamento (HTTP ${res.status})`)
  } catch (e: unknown) {
    if (e instanceof Error && e.message.includes('Falha ao aprovar')) {
      throw e
    }
    // Modo offline / mock fallback para testes locais
  }
  return {
    id: ticketId,
    run_id: runId || `run-approved-${Date.now()}`,
    property_id: 'casa-aurora',
    reported_by_role: 'tenant',
    category: 'eletricista',
    urgency: 'normal',
    location_in_property: 'Banheiro',
    description: 'Chuveiro sem água quente',
    status: 'resolved',
    selected_provider_id: providerId,
    scheduled_date: 'amanhã, 9h',
    notify_tenant: true,
    created_at: new Date().toISOString(),
  }
}

export async function startTicketResolution(ticketId: string): Promise<MaintenanceTicket> {
  try {
    const res = await fetch(`${API_BASE}/tickets/${ticketId}/start-resolution`, {
      method: 'POST',
    })
    if (res.ok) {
      return await res.json()
    }
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail ?? `Falha ao iniciar resolução (HTTP ${res.status})`)
  } catch (e: unknown) {
    if (e instanceof Error && e.message.includes('Falha ao iniciar')) {
      throw e
    }
    // fallback
  }
  return {
    id: ticketId,
    run_id: `run-start-${Date.now()}`,
    property_id: 'casa-aurora',
    reported_by_role: 'tenant',
    category: 'eletricista',
    urgency: 'normal',
    location_in_property: 'Banheiro',
    description: 'Reparo em andamento',
    status: 'awaiting_adm_approval',
    notify_tenant: true,
    created_at: new Date().toISOString(),
  }
}

async function postProviderReply(url: string, body: unknown): Promise<MaintenanceTicket> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => null)
    throw new Error(detail?.detail ?? `Status ${res.status}`)
  }
  return await res.json()
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
  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        property_id: params.propertyId,
        message: params.message,
        sender_role: params.senderRole,
        run_id: params.runId,
      }),
    })
    if (res.ok) {
      const data = await res.json()
      return {
        runId: data.run_id,
        propertyId: data.property_id,
        routeDestination: data.route_destination,
        responseText: data.response_text,
        ticketId: data.ticket_id,
        suggestedActions: data.suggested_actions || [],
      }
    }
  } catch {
    // fallback quando backend offline
  }
  return {
    runId: `run-mock-${Date.now()}`,
    propertyId: params.propertyId,
    routeDestination: 'commercial_node1',
    responseText: 'Olá! Recebemos sua mensagem com carinho. Como podemos ajudar?',
    ticketId: null,
    suggestedActions: [],
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

