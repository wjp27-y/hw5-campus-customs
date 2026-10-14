export type Ticket = {
  id: number
  type: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: 'open' | 'resolved' | string
  resolved: boolean
  created_at: string
}

export type CashAccount = {
  account: string
  balance: number
  date: string
}

export type ProgressEvent = {
  stage: string
  agent: string
  status: string
  message: string
  details?: {
    assignments?: Array<{ agent: string; reason: string }>
    findings?: string[]
    recommendations?: string[]
    tools_used?: string[]
    reasoning?: string
    follow_up_required?: boolean
    requires_human_review?: boolean
  }
}

export type TicketRun = {
  ticket_id: number
  status: string
  resolved: boolean
  boss: {
    dispatch_plan: { rationale: string; assignments: Array<{ agent: string; reason: string }> }
    final_judgment: {
      status: string
      summary: string
      reasoning: string
      follow_up_required: boolean
    }
    tools_used: string[]
  }
  agents: Array<{
    agent: string
    summary: string
    findings: string[]
    recommendations: string[]
    blocked: boolean
    tools_used: string[]
  }>
  customer_reply: { message: string; requires_human_review: boolean } | null
}

export type ApprovalChoice =
  | { kind: 'payment'; paymentKind: 'invoice' | 'rent'; refId: number }
  | { kind: 'purchase'; ticketId: number }
