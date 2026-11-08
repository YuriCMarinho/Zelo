import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { resetDemoData } from './api/client'
import App from './App'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it.each([400, 500, 503])('rejeita reset com HTTP %s', async (status) => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status })))
  await expect(resetDemoData()).rejects.toThrow('Falha ao reinicializar')
})

it('rejeita falso sucesso com corpo inválido', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}')))
  await expect(resetDemoData()).rejects.toThrow('resposta inválida')
})

it('aceita somente confirmação real do backend', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ status: 'success', message: 'Reset concluído' })))
  expect(await resetDemoData()).toEqual({ status: 'success', message: 'Reset concluído' })
})

it('mantém o modal aberto e mostra erro quando o backend está offline', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
  const user = userEvent.setup()
  render(<App />)
  await user.click(screen.getByRole('button', { name: /Resetar Demo/ }))
  await user.click(screen.getByRole('button', { name: 'Confirmar Reset' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Falha ao reinicializar')
  expect(screen.getByRole('dialog')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Confirmar Reset' })).toBeEnabled()
})
