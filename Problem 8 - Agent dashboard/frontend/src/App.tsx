import { useCallback, useEffect, useMemo, useState } from 'react'
import { approvePayment, approvePurchase, API_ORIGIN, getCash, getTickets, runTicket } from './api'
import type { ApprovalChoice, CashAccount, ProgressEvent, Ticket, TicketRun } from './types'

const agents: Record<string, { name: string; role: string; icon: string; tone: string }> = {
  boss: { name: 'Kakashi Hatake', role: 'Team lead · Boss', icon: '🥷', tone: 'kakashi' },
  inventory: { name: 'Naruto Uzumaki', role: 'Inventory specialist', icon: '🌀', tone: 'naruto' },
  accounting: { name: 'Sakura Haruno', role: 'Accounting specialist', icon: '🌸', tone: 'sakura' },
  facilities: { name: 'Sasuke Uchiha', role: 'Facilities specialist', icon: '⚡', tone: 'sasuke' },
  customer_service: { name: 'Sai', role: 'Customer service', icon: '🖌️', tone: 'sai' },
  team: { name: 'Team 7', role: 'Agent operations', icon: '🐾', tone: 'team' },
}

function agentFor(role: string) {
  return agents[role] ?? { name: role.replaceAll('_', ' '), role: 'Agent', icon: '✦', tone: 'team' }
}

function money(value: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(value)
}

function transactionChoices(report: TicketRun, ticket: Ticket): ApprovalChoice[] {
  const statements = [
    report.boss.final_judgment.summary,
    report.boss.final_judgment.reasoning,
    ...report.agents.flatMap((agent) => [...agent.findings, ...agent.recommendations]),
  ].join(' ')
  const choices: ApprovalChoice[] = []
  const invoiceIntent = /\b(pay|paid|payment|settle|approve|approval)\b.{0,36}\b(invoice|bill)\b|\b(invoice|bill)\b.{0,36}\b(pay|paid|payment|settle|approve|approval)\b/i.test(statements)
  const rentIntent = /\b(pay|paid|payment|settle|approve|approval)\b.{0,36}\b(rent|lease)\b|\b(rent|lease)\b.{0,36}\b(pay|paid|payment|settle|approve|approval)\b/i.test(statements)
  const purchaseIntent = /\b(approve|approval|purchase|buy|restock|place an? order)\b/i.test(statements)

  if (invoiceIntent && ticket.invoice_id) choices.push({ kind: 'payment', paymentKind: 'invoice', refId: ticket.invoice_id })
  if (rentIntent && ticket.lease_id) choices.push({ kind: 'payment', paymentKind: 'rent', refId: ticket.lease_id })
  if (purchaseIntent && ticket.sku && ticket.qty) choices.push({ kind: 'purchase', ticketId: ticket.id })
  return choices
}

function YaleMark() {
  return (
    <svg className="yale-mark" viewBox="0 0 52 58" role="img" aria-label="Campus Customs shield">
      <path d="M5 4h42v31L26 54 5 35z" fill="currentColor" />
      <path d="M11 10h30v22L26 47 11 32z" fill="#fff" />
      <path d="M18 17h16v4h-6v17h-4V21h-6z" fill="#0f2e5f" />
      <circle cx="26" cy="7" r="2" fill="#a9b5c5" />
    </svg>
  )
}

function PawIcon() {
  return (
    <svg viewBox="0 0 32 30" aria-hidden="true" className="paw-icon">
      <ellipse cx="16" cy="20" rx="8" ry="6.5" />
      <ellipse cx="6.4" cy="11" rx="3.3" ry="4.3" transform="rotate(-24 6.4 11)" />
      <ellipse cx="13.2" cy="6.4" rx="3.2" ry="4.1" transform="rotate(-8 13.2 6.4)" />
      <ellipse cx="20.2" cy="6.4" rx="3.2" ry="4.1" transform="rotate(8 20.2 6.4)" />
      <ellipse cx="26" cy="11" rx="3.3" ry="4.3" transform="rotate(24 26 11)" />
    </svg>
  )
}

function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [cash, setCash] = useState<CashAccount | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [activity, setActivity] = useState<ProgressEvent[]>([])
  const [reports, setReports] = useState<Record<number, TicketRun>>({})
  const [approvals, setApprovals] = useState<ApprovalChoice[]>([])
  const [approvalSelection, setApprovalSelection] = useState<number>(0)
  const [approved, setApproved] = useState(false)
  const [running, setRunning] = useState(false)
  const [approving, setApproving] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const selectedTicket = useMemo(() => tickets.find((ticket) => ticket.id === selectedId) ?? null, [tickets, selectedId])
  const selectedReport = selectedId ? reports[selectedId] : undefined

  const refreshBoard = useCallback(async () => {
    const [nextTickets, nextCash] = await Promise.all([getTickets(), getCash()])
    setTickets(nextTickets)
    setCash(nextCash)
    if (selectedId === null && nextTickets.length) setSelectedId(nextTickets[0].id)
  }, [selectedId])

  useEffect(() => {
    let active = true
    Promise.all([getTickets(), getCash()])
      .then(([nextTickets, nextCash]) => {
        if (!active) return
        setTickets(nextTickets)
        setCash(nextCash)
        if (nextTickets.length) setSelectedId(nextTickets[0].id)
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'Could not reach the Campus Customs backend.')
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  async function startRun() {
    if (!selectedTicket || running) return
    setRunning(true)
    setError('')
    setNotice('')
    setActivity([])
    setApprovals([])
    setApproved(false)
    try {
      const report = await runTicket(selectedTicket.id, (event) => {
        setActivity((previous) => [...previous, event])
      })
      setReports((previous) => ({ ...previous, [report.ticket_id]: report }))
      const nextApprovals = transactionChoices(report, selectedTicket)
      setApprovals(nextApprovals)
      setApprovalSelection(0)
      await refreshBoard()
      if (nextApprovals.length) setApproved(false)
      else setNotice(`Ticket ${selectedTicket.id} run complete. Kakashi’s summary is ready below.`)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The agent run could not be completed.')
      try { await refreshBoard() } catch { /* retain the original run error */ }
    } finally {
      setRunning(false)
    }
  }

  async function confirmApproval() {
    if (!selectedTicket || !approved || approvals.length === 0) return
    const choice = approvals[approvalSelection]
    if (!choice) return
    setApproving(true)
    setError('')
    setNotice('')
    try {
      const result = choice.kind === 'payment'
        ? await approvePayment({
            kind: choice.paymentKind,
            ref_id: choice.refId,
            ticket_id: selectedTicket.id,
            human_approved: true,
            approved_by: 'Dashboard user',
          })
        : await approvePurchase({ ticket_id: choice.ticketId, human_approved: true, approved_by: 'Dashboard user' })
      setCash(result.cash_account)
      setReports((previous) => {
        const current = previous[selectedTicket.id]
        return current ? { ...previous, [selectedTicket.id]: { ...current, status: 'resolved', resolved: true } } : previous
      })
      await refreshBoard()
      const remainingApprovals = approvals.filter((_, index) => index !== approvalSelection)
      setApprovals(remainingApprovals)
      setApprovalSelection(0)
      setApproved(false)
      setNotice(`Approved ${choice.kind === 'payment' ? choice.paymentKind : 'purchase'} for ${money(result.amount_paid)}. Checking balance updated.${remainingApprovals.length ? ' Review the next suggested transaction.' : ''}`)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The approval could not be recorded.')
    } finally {
      setApproving(false)
    }
  }

  function selectTicket(id: number) {
    if (running) return
    setSelectedId(id)
    setActivity([])
    setError('')
    setNotice('')
    setApprovals([])
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <YaleMark />
          <div><strong>CAMPUS CUSTOMS</strong><span>YALE · AGENT OPERATIONS</span></div>
        </div>
        <div className="topbar-right"><span className="connection-dot" /> LOCAL DESK <span className="topbar-divider" /> <span>NEW HAVEN, CT</span></div>
      </header>

      <main className="page-wrap">
        <section className="welcome-row">
          <div>
            <div className="eyebrow"><PawIcon /> CAMPUS CUSTOMS · SERVICE DESK</div>
            <h1>Agent command desk</h1>
            <p className="intro">A clear view of every ticket, every teammate, and each decision in progress.</p>
          </div>
          <div className="cash-card">
            <div className="cash-label"><span className="cash-icon">＄</span><span>CHECKING BALANCE</span><span className="live-pill">LIVE</span></div>
            <strong>{cash ? money(cash.balance) : '—'}</strong>
            <small>{cash ? `Updated ${cash.date}` : 'Connecting to the backend'}</small>
          </div>
        </section>

        <section className="agent-strip" aria-label="Agent team">
          <div className="strip-heading"><span className="section-kicker">TEAM 7</span><span className="strip-rule" /><span className="strip-caption">One lead · four specialists</span></div>
          <div className="agent-row">
            {Object.entries(agents).filter(([role]) => role !== 'team').map(([role, agent]) => (
              <div className={`agent-chip ${role === 'boss' ? 'lead-chip' : ''}`} key={role}>
                <span className={`avatar avatar-${agent.tone}`}>{agent.icon}</span>
                <span className="agent-chip-text"><strong>{agent.name}</strong><small>{agent.role}</small></span>
                {role === 'boss' && <span className="lead-tag">LEAD</span>}
              </div>
            ))}
          </div>
        </section>

        {error && <div className="alert alert-error" role="alert"><strong>Couldn’t complete that step.</strong> {error}<small>Backend: {API_ORIGIN}</small></div>}
        {notice && <div className="alert alert-success" role="status"><span>✓</span> {notice}</div>}

        <div className="workspace-grid">
          <section className="ticket-column">
            <div className="section-title-row"><div><span className="section-kicker">INCOMING WORK</span><h2>Ticket board <span className="count-badge">{tickets.length || 3}</span></h2></div><span className="board-date">THREE SHOP REQUESTS</span></div>
            <div className="ticket-list">
              {loading && <div className="loading-card">Loading the ticket board…</div>}
              {!loading && tickets.map((ticket, index) => {
                const isSelected = ticket.id === selectedId
                const report = reports[ticket.id]
                return (
                  <button className={`ticket-card ${isSelected ? 'selected' : ''}`} key={ticket.id} onClick={() => selectTicket(ticket.id)} aria-pressed={isSelected}>
                    <span className="ticket-index">0{index + 1}</span>
                    <span className="ticket-main">
                      <span className="ticket-meta"><span className="ticket-id">CC-{ticket.id}</span><span className={`status-pill ${ticket.status === 'resolved' ? 'resolved' : 'open'}`}><i />{ticket.status}</span></span>
                      <strong>{ticket.subject}</strong>
                      <small>{ticket.type.replaceAll('_', ' ')}{ticket.sku ? ` · ${ticket.sku}` : ''}{ticket.size ? ` · Size ${ticket.size}` : ''}</small>
                      {report && <span className="mini-summary">{report.boss.final_judgment.summary}</span>}
                    </span>
                    <span className="ticket-chevron">{isSelected ? '●' : '›'}</span>
                  </button>
                )
              })}
              {!loading && tickets.length === 0 && <div className="loading-card">No tickets were returned by the backend.</div>}
            </div>
            <div className="ticket-footnote"><span className="footnote-shield">Y</span><span>Choose a ticket to brief Kakashi and start a supervised team run.</span></div>
          </section>

          <section className="case-column">
            <div className="case-heading">
              <div><span className="section-kicker">CASE FILE</span><h2>{selectedTicket ? `Ticket ${selectedTicket.id}` : 'Select a ticket'}</h2></div>
              {selectedTicket && <span className={`status-pill large ${selectedTicket.status === 'resolved' ? 'resolved' : 'open'}`}><i />{selectedTicket.status}</span>}
            </div>
            {selectedTicket ? (
              <>
                <div className="case-summary">
                  <div className="case-subject-icon"><PawIcon /></div>
                  <div><span className="case-category">{selectedTicket.type.replaceAll('_', ' ')}</span><h3>{selectedTicket.subject}</h3><p>{selectedTicket.sku ? `${selectedTicket.sku}${selectedTicket.size ? ` · ${selectedTicket.size}` : ''}${selectedTicket.qty ? ` · Qty ${selectedTicket.qty}` : ''}` : 'Customer service and store operations review'}</p></div>
                </div>
                <button className="run-button" onClick={() => void startRun()} disabled={running || loading}>
                  <span className="run-button-icon">{running ? <span className="spinner" /> : '▶'}</span>
                  <span>{running ? 'TEAM IN SESSION' : 'RUN AGENT TEAM'}</span>
                  <span className="run-shortcut">{running ? 'LIVE' : 'KAKASHI + TEAM 7'}</span>
                </button>
              </>
            ) : <div className="case-empty">Choose one of the three tickets to view its case file.</div>}

            <div className="activity-header"><div><span className="section-kicker">LIVE CASE NOTES</span><h3>Team conversation</h3></div>{running && <span className="running-indicator"><i /> RUNNING</span>}</div>
            <div className="activity-feed" aria-live="polite" aria-relevant="additions text">
              {activity.length === 0 && !selectedReport && !running && <div className="feed-empty"><span className="feed-empty-mark">✳</span><strong>The briefing room is ready.</strong><p>Start a run to follow Kakashi’s assignments, specialist findings, tool use, and final decision.</p></div>}
              {activity.length === 0 && running && <div className="feed-empty"><span className="spinner dark" /><strong>Connecting to the team…</strong><p>The first progress update will appear here.</p></div>}
              {activity.map((event, index) => {
                const agent = agentFor(event.agent)
                return (
                  <article className="activity-item" key={`${event.stage}-${event.agent}-${index}`}>
                    <span className={`avatar avatar-${agent.tone}`}>{agent.icon}</span>
                    <div className="activity-content">
                      <div className="activity-meta"><strong>{agent.name}</strong><span>{event.stage.replaceAll('_', ' ')}</span><span className={`activity-state ${event.status}`}>{event.status.replaceAll('_', ' ')}</span></div>
                      <p>{event.message}</p>
                      {event.details?.findings?.map((finding, findingIndex) => <div className="detail-line" key={`f${findingIndex}`}><span>Finding</span>{finding}</div>)}
                      {event.details?.recommendations?.map((recommendation, recommendationIndex) => <div className="detail-line recommendation" key={`r${recommendationIndex}`}><span>Recommendation</span>{recommendation}</div>)}
                      {event.details?.tools_used && event.details.tools_used.length > 0 && <div className="tool-row"><span>TOOLS</span>{event.details.tools_used.map((tool) => <code key={tool}>{tool}</code>)}</div>}
                      {event.details?.assignments && <div className="assignment-row">{event.details.assignments.map((assignment) => <span key={assignment.agent}><b>{agentFor(assignment.agent).name}</b> · {assignment.reason}</span>)}</div>}
                    </div>
                  </article>
                )
              })}
              {selectedReport && <div className="final-report">
                <div className="report-title"><span>✓</span><div><small>KAKASHI’S FINAL CALL</small><strong>{selectedReport.boss.final_judgment.status.replaceAll('_', ' ')}</strong></div></div>
                <p>{selectedReport.boss.final_judgment.summary}</p>
                <div className="report-reasoning">{selectedReport.boss.final_judgment.reasoning}</div>
                {selectedReport.agents.map((agentResult) => {
                  const agent = agentFor(agentResult.agent)
                  return <div className="agent-summary" key={agentResult.agent}><span className={`avatar small avatar-${agent.tone}`}>{agent.icon}</span><div><strong>{agent.name}</strong><p>{agentResult.summary}</p>{agentResult.tools_used.length > 0 && <small>Tools: {agentResult.tools_used.join(' · ')}</small>}</div></div>
                })}
                {selectedReport.customer_reply && <div className="customer-reply"><small>CUSTOMER SERVICE DRAFT</small><p>{selectedReport.customer_reply.message}</p>{selectedReport.customer_reply.requires_human_review && <span>Needs human review</span>}</div>}
              </div>}
            </div>
          </section>
        </div>

        <footer className="page-footer"><span>YALE BLUE · NEW HAVEN</span><span>Human approval is required before a payment or purchase is recorded.</span><span>LOCAL DEVELOPMENT DESK</span></footer>
      </main>

      {approvals.length > 0 && selectedTicket && (
        <div className="modal-backdrop" role="presentation">
          <section className="approval-modal" role="dialog" aria-modal="true" aria-labelledby="approval-title">
            <button className="modal-close" onClick={() => setApprovals([])} aria-label="Close approval window">×</button>
            <div className="modal-emblem"><span>!</span></div>
            <span className="section-kicker">HUMAN CHECKPOINT · TICKET {selectedTicket.id}</span>
            <h2 id="approval-title">Review the team’s recommendation</h2>
            <p className="modal-intro">The agents have recommended a financial action. Choose the transaction to approve. The backend will calculate the amount from the ticket and current database.</p>
            <div className="approval-options">
              {approvals.map((choice, index) => (
                <label className={`approval-option ${approvalSelection === index ? 'active' : ''}`} key={`${choice.kind}-${index}`}>
                  <input type="radio" name="approval-choice" checked={approvalSelection === index} onChange={() => setApprovalSelection(index)} />
                  <span className="option-icon">{choice.kind === 'payment' ? '＄' : '🧾'}</span>
                  <span><strong>{choice.kind === 'payment' ? `${choice.paymentKind === 'invoice' ? 'Pay invoice' : 'Pay rent'} · #${choice.refId}` : 'Approve ticket purchase'}</strong><small>{choice.kind === 'payment' ? 'Checking account debit' : `${selectedTicket.sku ?? 'Ticket item'} · Size ${selectedTicket.size ?? '—'} · Qty ${selectedTicket.qty ?? '—'}`}</small></span>
                </label>
              ))}
            </div>
            <label className="approval-confirm"><input type="checkbox" checked={approved} onChange={(event) => setApproved(event.target.checked)} /><span>I approve this transaction and understand it will debit the checking account.</span></label>
            <div className="modal-actions"><button className="secondary-button" onClick={() => setApprovals([])} disabled={approving}>Decide later</button><button className="approve-button" onClick={() => void confirmApproval()} disabled={!approved || approving}>{approving ? 'Recording…' : 'Approve transaction'}</button></div>
            <small className="modal-note">This local coursework dashboard records your click as human approval. It does not contact a vendor.</small>
          </section>
        </div>
      )}
    </div>
  )
}

export default App
