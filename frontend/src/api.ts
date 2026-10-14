import type { CashAccount, ProgressEvent, Ticket, TicketRun } from './types'

export const API_ORIGIN = 'http://localhost:8000'

async function readJson<T>(response: Response): Promise<T> {
  const body = await response.json().catch(() => ({})) as { detail?: string }
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`)
  return body as T
}

export async function getTickets(): Promise<Ticket[]> {
  const response = await fetch(`${API_ORIGIN}/tickets`)
  const result = await readJson<{ tickets: Ticket[] }>(response)
  return result.tickets
}

export async function getCash(): Promise<CashAccount> {
  const response = await fetch(`${API_ORIGIN}/cash`)
  const result = await readJson<{ cash_account: CashAccount }>(response)
  return result.cash_account
}

export async function runTicket(
  ticketId: number,
  onProgress: (event: ProgressEvent) => void,
): Promise<TicketRun> {
  const response = await fetch(`${API_ORIGIN}/tickets/${ticketId}/run/stream`, {
    method: 'POST',
    headers: { Accept: 'text/event-stream' },
  })
  if (!response.ok) {
    const problem = await response.json().catch(() => ({})) as { detail?: string }
    throw new Error(problem.detail || `Could not start the agent team (${response.status})`)
  }
  if (!response.body) throw new Error('The backend did not provide a progress stream.')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let completed: TicketRun | undefined

  const handleFrame = (frame: string) => {
    let eventName = 'message'
    const data: string[] = []
    for (const line of frame.split(/\r?\n/)) {
      if (line.startsWith('event:')) eventName = line.slice(6).trim()
      if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
    }
    if (data.length === 0) return
    const payload = JSON.parse(data.join('\n')) as TicketRun | ProgressEvent | { detail?: string }
    if (eventName === 'progress') onProgress(payload as ProgressEvent)
    if (eventName === 'error') throw new Error((payload as { detail?: string }).detail || 'The agent run failed.')
    if (eventName === 'complete') completed = payload as TicketRun
  }

  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    let boundary = buffer.indexOf('\n\n')
    while (boundary >= 0) {
      handleFrame(buffer.slice(0, boundary).replace(/\r$/, ''))
      buffer = buffer.slice(boundary + 2)
      boundary = buffer.indexOf('\n\n')
    }
    if (done) break
  }
  if (buffer.trim()) handleFrame(buffer)
  if (!completed) throw new Error('The progress stream ended before the final ticket report arrived.')
  return completed
}

export async function approvePayment(input: {
  kind: 'invoice' | 'rent'
  ref_id: number
  ticket_id: number
  human_approved: true
  approved_by: string
}) {
  const response = await fetch(`${API_ORIGIN}/approvals/payment`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  return readJson<{ amount_paid: number; cash_account: CashAccount }>(response)
}

export async function approvePurchase(input: {
  ticket_id: number
  human_approved: true
  approved_by: string
}) {
  const response = await fetch(`${API_ORIGIN}/approvals/purchase`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  return readJson<{ amount_paid: number; cash_account: CashAccount }>(response)
}
