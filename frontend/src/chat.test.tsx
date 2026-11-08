import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { sendChatMessage } from './api/client'
import { ChatPanel } from './components/ChatPanel'
import { properties } from './demo-data'
import { parseRoute } from './routes'

const request = { propertyId: 'prop-copacabana-01', message: 'qual o horario do check-in?', senderRole: 'tenant' as const }
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('atendimento conectado ao backend', () => {
  it.each([
    { response: 'Olá!', delay: 7200, apiTime: 0 },
    { response: 'a'.repeat(100), delay: 9800, apiTime: 0 },
    { response: 'a'.repeat(400), delay: 14000, apiTime: 0 },
    { response: 'Olá!', delay: 7200, apiTime: 5000 },
    { response: 'Olá!', delay: 11200, apiTime: 10000 },
    { response: 'a'.repeat(100), delay: 13800, apiTime: 10000 },
  ])('aguarda $delay ms com API de $apiTime ms e mantém a digitação completa', async ({ response, delay, apiTime }) => {
    vi.useFakeTimers()
    vi.spyOn(Math, 'random').mockReturnValue(0.5)
    const apiResponse = new Response(JSON.stringify({
      run_id: 'run-delay', property_id: request.propertyId,
      route_destination: 'commercial_node1', response_text: response, ticket_id: null,
    }))
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => apiTime > 0
      ? new Promise<Response>((resolve) => window.setTimeout(() => resolve(apiResponse), apiTime))
      : Promise.resolve(apiResponse)))
    const onNewMessage = vi.fn()
    render(<ChatPanel property={properties[0]!} messages={[]} onNewMessage={onNewMessage} />)
    await act(async () => {
      fireEvent.change(screen.getByRole('textbox', { name: 'Mensagem' }), { target: { value: 'oi' } })
      fireEvent.click(screen.getByRole('button', { name: 'Enviar mensagem' }))
    })
    expect(onNewMessage).toHaveBeenCalledTimes(1)
    expect(screen.queryByText('Digitando resposta...')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Enviar mensagem' })).toBeDisabled()
    await act(async () => { await vi.advanceTimersByTimeAsync(5999) })
    expect(screen.queryByText('Digitando resposta...')).not.toBeInTheDocument()
    await act(async () => { await vi.advanceTimersByTimeAsync(1) })
    expect(screen.getByText('Digitando resposta...')).toBeInTheDocument()
    await act(async () => { await vi.advanceTimersByTimeAsync(delay - 6001) })
    expect(onNewMessage).toHaveBeenCalledTimes(1)
    await act(async () => { await vi.advanceTimersByTimeAsync(1) })
    expect(onNewMessage).toHaveBeenCalledTimes(2)
    expect(onNewMessage.mock.calls[1]![0].body).toBe(response)
    expect(screen.queryByText('Digitando resposta...')).not.toBeInTheDocument()
  })

  it('cancela o indicador de digitação se a requisição falhar antes da pausa', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    render(<ChatPanel property={properties[0]!} messages={[]} onNewMessage={vi.fn()} />)
    await act(async () => {
      fireEvent.change(screen.getByRole('textbox', { name: 'Mensagem' }), { target: { value: 'oi' } })
      fireEvent.click(screen.getByRole('button', { name: 'Enviar mensagem' }))
    })
    expect(screen.getByRole('alert')).toBeInTheDocument()
    await act(async () => { await vi.advanceTimersByTimeAsync(11000) })
    expect(screen.queryByText('Digitando resposta...')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Enviar mensagem' })).toBeEnabled()
  })

  it('retorna a resposta do agente e encaminha o imóvel e o remetente corretos', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ run_id: 'run-1', property_id: request.propertyId, route_destination: 'commercial_node1', response_text: 'Check-in a partir das 15h.', ticket_id: null })))
    vi.stubGlobal('fetch', fetchMock)
    expect((await sendChatMessage(request)).responseText).toBe('Check-in a partir das 15h.')
    expect(JSON.parse(fetchMock.mock.calls[0]![1].body)).toMatchObject({ property_id: request.propertyId, sender_role: 'tenant', message: request.message })
  })

  it.each([404, 500, 503])('não inventa uma resposta quando a API retorna HTTP %s', async (status) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status })))
    await expect(sendChatMessage(request)).rejects.toThrow(status === 404 ? /imóvel não foi encontrado/ : /indisponível/)
  })

  it('rejeita um retorno sem mensagem do agente', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}')))
    await expect(sendChatMessage(request)).rejects.toThrow(/resposta inválida/)
  })

  it('mostra erro de conexão no chat e preserva o texto para nova tentativa', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const onNewMessage = vi.fn()
    const user = userEvent.setup()
    render(<ChatPanel property={properties[0]!} messages={[]} onNewMessage={onNewMessage} />)
    await user.type(screen.getByRole('textbox', { name: 'Mensagem' }), request.message)
    await user.click(screen.getByRole('button', { name: 'Enviar mensagem' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/backend está disponível/)
    expect(screen.getByRole('textbox', { name: 'Mensagem' })).toHaveValue(request.message)
    expect(onNewMessage).toHaveBeenCalledTimes(1)
    expect(onNewMessage.mock.calls[0]![0].sender).toBe('hospede')
  })

  it('aceita rotas dos imóveis carregados da API', () => {
    expect(parseRoute('/imoveis/prop-copacabana-01', '?aba=chat', [{ id: 'prop-copacabana-01' }])).toEqual({ view: 'property', propertyId: 'prop-copacabana-01', tab: 'chat' })
  })
})
