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
    { response: 'Olá!', delay: 4300, apiTime: 0 },
    { response: 'a'.repeat(100), delay: 4450, apiTime: 0 },
    { response: 'a'.repeat(400), delay: 4700, apiTime: 0 },
    { response: 'Olá!', delay: 4300, apiTime: 500 },
    { response: 'Olá!', delay: 4300, apiTime: 1000 },
    { response: 'a'.repeat(100), delay: 4450, apiTime: 1000 },
    { response: 'Olá!', delay: 6300, apiTime: 6000 },
  ])('aguarda $delay ms com API de $apiTime ms e mantém a digitação ágil', async ({ response, delay, apiTime }) => {
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
    await act(async () => { await vi.advanceTimersByTimeAsync(3999) })
    expect(screen.queryByText('Digitando resposta...')).not.toBeInTheDocument()
    await act(async () => { await vi.advanceTimersByTimeAsync(1) })
    expect(screen.getByText('Digitando resposta...')).toBeInTheDocument()
    await act(async () => { await vi.advanceTimersByTimeAsync(delay - 4001) })
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
    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
    expect(screen.queryByText('Digitando resposta...')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Enviar mensagem' })).toBeEnabled()
  })

  it('retorna a resposta do agente e encaminha o imóvel, remetente, canal e sessão corretos', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ run_id: 'run-1', property_id: request.propertyId, route_destination: 'commercial_node1', response_text: 'Check-in a partir das 15h.', ticket_id: null })))
    vi.stubGlobal('fetch', fetchMock)
    expect((await sendChatMessage(request)).responseText).toBe('Check-in a partir das 15h.')
    const body = JSON.parse(fetchMock.mock.calls[0]![1].body)
    expect(body).toMatchObject({ property_id: request.propertyId, sender_role: 'tenant', channel: 'guest', message: request.message })
    expect(body.session_id).toMatch(/^sess-/)
  })

  it('isola o histórico do Canal do Hóspede e do Canal da Camareira', async () => {
    const prop = properties[0]!
    const messages = [
      { id: 'm1', propertyId: prop.id, channel: 'guest' as const, sender: 'hospede' as const, body: 'Quero reservar para dezembro', time: '10:00' },
      { id: 'm2', propertyId: prop.id, channel: 'cleaner' as const, sender: 'camareira' as const, body: 'Vazamento encontrado na vistoria', time: '10:05' },
    ]
    const user = userEvent.setup()
    render(<ChatPanel property={prop} messages={messages} onNewMessage={vi.fn()} />)

    // No canal Hóspede (padrão), exibe apenas a mensagem do hóspede
    expect(screen.getByText('Quero reservar para dezembro')).toBeInTheDocument()
    expect(screen.queryByText('Vazamento encontrado na vistoria')).not.toBeInTheDocument()

    // Ao alternar para Camareira, exibe apenas o histórico operacional da camareira
    await user.click(screen.getByRole('button', { name: 'Camareira' }))
    expect(screen.getByText('Vazamento encontrado na vistoria')).toBeInTheDocument()
    expect(screen.queryByText('Quero reservar para dezembro')).not.toBeInTheDocument()
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
