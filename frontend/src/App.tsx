import { useEffect, useRef, useState } from 'react'
import { ApiError, cancelJob, findOptimizationProposals, generateComplexityBenchmarks, getJob, getReport, matchProblem, submitJob } from './api'
import type { AnalysisReport, Job, JobStatus, Language, OptimizationProposal, ProblemMatch } from './types'
import LandingPage from './LandingPage'
import './App.css'

const terminalStatuses = new Set<JobStatus>(['completed', 'failed', 'cancelled'])
const historyStorageKey = 'axioma.mode1.recent-jobs.v1'
const historyLimit = 20

function twoSumBenchmarks() {
  return [32, 64, 128, 256].map((size) => ({
    size,
    args: [Array<number>(size).fill(0), -1],
    kwargs: {},
  }))
}

function benchmarkPlan(problem: Record<string, unknown>) {
  const constraints = problem.constraints
  const samples = problem.samples
  if (!Array.isArray(constraints) || !Array.isArray(samples) || samples.length === 0) return null
  const scalableInputs: {
    path: string
    minimum: unknown
    maximum: unknown
    sampleLength: number
    pattern: 'ascending' | 'repeated_characters'
  }[] = []
  for (const value of constraints) {
    if (typeof value !== 'object' || value === null) continue
    const constraint = value as Record<string, unknown>
    if (typeof constraint.path !== 'string') continue
    const match = /^args\[(\d+)\]\.length$/.exec(constraint.path)
    if (!match) continue
    const sample = samples[0] as Record<string, unknown>
    const args = sample.args
    const index = Number(match[1])
    if (!Array.isArray(args)) continue
    const sampleValue = args[index]
    if (typeof sampleValue === 'string') {
      scalableInputs.push({ path: constraint.path, minimum: constraint.minimum, maximum: constraint.maximum, sampleLength: sampleValue.length, pattern: 'repeated_characters' })
      continue
    }
    if (!Array.isArray(sampleValue)) continue
    const values = sampleValue as unknown[]
    if (!values.every((item) => typeof item === 'number' && Number.isFinite(item))) continue
    scalableInputs.push({ path: constraint.path, minimum: constraint.minimum, maximum: constraint.maximum, sampleLength: values.length, pattern: 'ascending' })
  }
  if (scalableInputs.length === 0) return null

  scalableInputs.sort((left, right) => {
    const leftIndex = Number(/\[(\d+)\]/.exec(left.path)?.[1] ?? -1)
    const rightIndex = Number(/\[(\d+)\]/.exec(right.path)?.[1] ?? -1)
    return leftIndex - rightIndex
  })
  const { path, minimum, maximum, sampleLength, pattern } = scalableInputs[scalableInputs.length - 1]
  const low = Math.max(1, Number.isInteger(minimum) ? Number(minimum) : 1, sampleLength)
  const high = Math.min(32, Number.isInteger(maximum) ? Number(maximum) : 32)
  if (high - low < 3) return null
  const sizes = Array.from({ length: 4 }, (_, index) => Math.round(low + (high - low) * index / 3))
  if (new Set(sizes).size !== 4) return null
  return { size_path: path, sizes, pattern }
}

interface HistoryEntry {
  id: string
  language: Language
  created_at: string
  topics: string[]
  summary?: HistorySummary
}

interface HistorySummary {
  passed: number
  failed: number
  skipped: number
  complexity: string | null
}

function readHistory(): HistoryEntry[] {
  try {
    const value = JSON.parse(localStorage.getItem(historyStorageKey) ?? '[]') as unknown
    if (!Array.isArray(value)) return []
    const entries: HistoryEntry[] = []
    for (const item of value) {
      if (typeof item !== 'object' || item === null) continue
      const stored = item as Record<string, unknown>
      if (
        typeof stored.id !== 'string'
        || !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(stored.id)
        || (stored.language !== 'python' && stored.language !== 'java')
        || typeof stored.created_at !== 'string'
      ) continue
      const topics = Array.isArray(stored.topics)
        ? stored.topics.filter((topic): topic is string => typeof topic === 'string').slice(0, 8)
        : []
      const summaryValue = stored.summary
      const summary = typeof summaryValue === 'object' && summaryValue !== null
        ? summaryValue as Record<string, unknown>
        : null
      const validSummary = summary
        && Number.isInteger(summary.passed) && Number(summary.passed) >= 0
        && Number.isInteger(summary.failed) && Number(summary.failed) >= 0
        && Number.isInteger(summary.skipped) && Number(summary.skipped) >= 0
        && (summary.complexity === null || typeof summary.complexity === 'string')
        ? {
            passed: Number(summary.passed),
            failed: Number(summary.failed),
            skipped: Number(summary.skipped),
            complexity: summary.complexity as string | null,
          }
        : undefined
      entries.push({
        id: stored.id,
        language: stored.language,
        created_at: stored.created_at,
        topics,
        ...(validSummary ? { summary: validSummary } : {}),
      })
    }
    return entries.slice(0, historyLimit)
  } catch {
    return []
  }
}

function AnalyzerApp() {
  const [language, setLanguage] = useState<Language>('python')
  const [statement, setStatement] = useState('')
  const [code, setCode] = useState('')
  const [problemMatch, setProblemMatch] = useState<ProblemMatch | null>(null)
  const [matching, setMatching] = useState(false)
  const [proposal, setProposal] = useState<OptimizationProposal | null>(null)
  const [proposalMessage, setProposalMessage] = useState<string | null>(null)
  const [proposalBusy, setProposalBusy] = useState(false)
  const [history, setHistory] = useState<HistoryEntry[]>(readHistory)
  const [job, setJob] = useState<Job | null>(null)
  const [report, setReport] = useState<AnalysisReport | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const eventSource = useRef<EventSource | null>(null)
  const activeJobId = job?.id
  const activeJobStatus = job?.status

  function rememberReportSummary(jobId: string, nextReport: AnalysisReport) {
    setHistory((current) => current.map((item) => item.id === jobId
      ? {
          ...item,
          summary: {
            passed: nextReport.tests.passed,
            failed: nextReport.tests.failed,
            skipped: nextReport.tests.skipped,
            complexity: nextReport.complexity?.estimate ?? null,
          },
        }
      : item))
  }

  useEffect(() => () => eventSource.current?.close(), [])

  useEffect(() => {
    try {
      localStorage.setItem(historyStorageKey, JSON.stringify(history))
    } catch {
      // The current analysis still works when browser storage is unavailable.
    }
  }, [history])

  useEffect(() => {
    if (!activeJobId || !activeJobStatus || terminalStatuses.has(activeJobStatus)) return
    eventSource.current?.close()
    const source = new EventSource(`/api/v1/jobs/${activeJobId}/events`)
    eventSource.current = source
    const refresh = async (nextStatus?: JobStatus, message?: string) => {
      try {
        const current = await getJob(activeJobId)
        const updated = {
          ...current,
          status: nextStatus ?? current.status,
          progress_message: message ?? current.progress_message,
        }
        setJob(updated)
        if (terminalStatuses.has(updated.status)) {
          source.close()
          if (updated.status === 'completed') {
            const completedReport = await getReport(activeJobId)
            setReport(completedReport)
            rememberReportSummary(activeJobId, completedReport)
          }
        }
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : 'Could not refresh the job status.')
      }
    }
    source.addEventListener('job_status', (event) => {
      const payload = JSON.parse((event as MessageEvent<string>).data) as {
        status: JobStatus
        message: string
      }
      void refresh(payload.status, payload.message)
    })
    source.onerror = () => {
      void refresh()
    }
    void refresh()
    return () => source.close()
  }, [activeJobId, activeJobStatus])

  function updateCode(value: string) {
    setCode(value)
    setProposal(null)
    setProposalMessage(null)
  }

  async function findOptimization() {
    setProposalBusy(true)
    setProposal(null)
    setProposalMessage(null)
    setError(null)
    try {
      if (!code.trim()) throw new Error('Paste your solution code before asking for an improvement.')
      const match = problemMatch?.recognized && problemMatch.problem
        ? problemMatch
        : await identifyStatement()
      if (!match.recognized || !match.problem) {
        throw new Error('Axioma needs to recognize the problem before suggesting an improvement.')
      }
      const result = await findOptimizationProposals({ language, code, problem: match.problem })
      setProposal(result.proposals[0] ?? null)
      setProposalMessage(result.message)
    } catch (reason) {
      setError(reason instanceof ApiError
        ? reason.message
        : reason instanceof Error
          ? reason.message
          : 'Could not look for an optimization.')
    } finally {
      setProposalBusy(false)
    }
  }

  async function identifyStatement(value = statement): Promise<ProblemMatch> {
    setMatching(true)
    try {
      const result = await matchProblem(value)
      setProblemMatch(result)
      return result
    } finally {
      setMatching(false)
    }
  }

  async function runAnalysis(optimization?: OptimizationProposal) {
    setBusy(true)
    setError(null)
    setReport(null)
    try {
      if (!statement.trim()) throw new Error('Paste a problem statement first.')
      if (!code.trim()) throw new Error('Paste your solution code first.')
      const match = await identifyStatement()
      if (!match.recognized || !match.problem) {
        throw new Error('Axioma could not match this problem yet. The starter catalog currently supports Two Sum, Best Time to Buy and Sell Stock, Valid Parentheses, and Permutation in String.')
      }
      const problem = match.problem
      const request: Record<string, unknown> = { language, code, problem }
      if (optimization) {
        request.optimization_code = optimization.candidate_code
        request.optimization_notes = optimization.summary
        if (optimization.rule_id === 'two_sum_pairwise_to_hash_map_v1') {
          request.complexity_benchmarks = twoSumBenchmarks()
        }
      } else {
        const plan = benchmarkPlan(problem)
        if (plan) {
          try {
            const generated = await generateComplexityBenchmarks({
              problem,
              ...plan,
              pattern: plan.pattern,
              seed: 0,
            })
            if (generated.benchmarks.length === 4) request.complexity_benchmarks = generated.benchmarks
          } catch {
            // Keep the normal sample analysis available when a pack cannot produce a benchmark.
          }
        }
      }
      const path = `/v1/jobs/mode1/${language}-function`
      const created = await submitJob(path, request)
      setJob(created)
      setHistory((current) => [
        { id: created.id, language: created.language, created_at: created.created_at, topics: match.topics },
        ...current.filter((item) => item.id !== created.id),
      ].slice(0, historyLimit))
    } catch (reason) {
      setError(
        reason instanceof ApiError
          ? reason.message
          : reason instanceof Error
            ? reason.message
            : 'Could not submit this analysis.',
      )
    } finally {
      setBusy(false)
    }
  }

  async function stopJob() {
    if (!job) return
    try {
      setJob(await cancelJob(job.id))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not cancel this job.')
    }
  }

  async function openHistoryJob(jobId: string) {
    setError(null)
    setReport(null)
    setJob(null)
    try {
      const selected = await getJob(jobId)
      setJob(selected)
      if (selected.status === 'completed') {
        const loadedReport = await getReport(jobId)
        setReport(loadedReport)
        rememberReportSummary(jobId, loadedReport)
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not load this saved run.')
      if (reason instanceof ApiError && reason.status === 404) {
        setHistory((current) => current.filter((item) => item.id !== jobId))
      }
    }
  }

  function exportReport() {
    if (!job || !report) return
    const payload = {
      exported_at: new Date().toISOString(),
      job,
      topics: history.find((item) => item.id === job.id)?.topics ?? [],
      report,
    }
    const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `axioma-report-${job.id.slice(0, 8)}.json`
    anchor.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  const isRunning = job !== null && !terminalStatuses.has(job.status)
  const canCancel = job?.status === 'queued' || job?.status === 'running'
  const topicSignals = history.reduce<Record<string, { failed: number; checked: number }>>((signals, item) => {
    if (!item.summary) return signals
    const checked = item.summary.passed + item.summary.failed
    for (const topic of item.topics) {
      signals[topic] ??= { failed: 0, checked: 0 }
      signals[topic].failed += item.summary.failed
      signals[topic].checked += checked
    }
    return signals
  }, {})
  const weakestTopicSignals = Object.entries(topicSignals)
    .filter(([, counts]) => counts.checked >= 3)
    .sort((left, right) => (right[1].failed / right[1].checked) - (left[1].failed / left[1].checked))
    .slice(0, 4)
  const recentComplexity = history.filter((item) => item.summary?.complexity).slice(0, 5)

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Axioma home">
          <span className="brand-mark">A.</span><span>axioma</span><sup>®</sup>
        </a>
          <div className="workspace-label">LOCAL WORKSPACE <i>/</i> MODE 1</div>
        <div className="topbar-right"><span className="header-status">EVIDENCE, BUILT IN</span><span className="avatar">AG</span></div>
      </header>

      <div className="layout" id="main">
        <aside className="rail" aria-label="Product navigation">
          <div className="rail-section-label">WORKSPACE</div>
          <button className="rail-item selected" aria-current="page"><span className="rail-icon">⌘</span><span>Analyzer</span></button>
          <button className="rail-item" disabled title="Repository review is not implemented yet"><span className="rail-icon">⌂</span><span>Repository review</span><small>SOON</small></button>
          <div className="rail-divider" />
          <div className="rail-section-label">RECENT RUNS <span>{history.length}</span></div>
          {history.length > 0 && <button className="rail-clear" onClick={() => setHistory([])}>CLEAR LOCAL HISTORY</button>}
          <div className="rail-history" aria-label="Recent analyses">
            {history.length === 0
              ? <p className="rail-history-empty">Completed and submitted runs will appear here. This browser stores job IDs only.</p>
              : history.map((item) => (
                <button
                  className={`rail-history-item${job?.id === item.id ? ' active' : ''}`}
                  key={item.id}
                  onClick={() => void openHistoryJob(item.id)}
                  aria-current={job?.id === item.id ? 'true' : undefined}
                  title={`Open ${item.language} run ${item.id}`}
                >
                  <span>{item.language.toUpperCase()}</span>
                  <code>{item.id.slice(0, 8)}</code>
                  <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time>
                  {item.topics.length > 0 && <small className="rail-history-topics">{item.topics.join(' · ')}</small>}
                  {item.summary?.complexity && <small className="rail-history-estimate">{item.summary.complexity}</small>}
                </button>
              ))}
          </div>
          <div className="rail-divider" />
          <details className="rail-insights">
            <summary>LEARNING INSIGHTS</summary>
            <p className="rail-insight-note">Signals from your saved runs. They are not a skill score.</p>
            <div className="rail-subheading">TOPIC SIGNALS</div>
            {weakestTopicSignals.length === 0
              ? <p className="rail-history-empty">Collect at least three executed checks per topic to see a signal.</p>
              : <div className="rail-topic-list">{weakestTopicSignals.map(([topic, counts]) => (
                <div className="rail-topic-row" key={topic}>
                  <span>{topic}</span>
                  <b>{Math.round((counts.failed / counts.checked) * 100)}% failed</b>
                  <small>{counts.failed}/{counts.checked} checks</small>
                </div>
              ))}</div>}
            <div className="rail-subheading complexity-history-label">RECENT COMPLEXITY</div>
            {recentComplexity.length === 0
              ? <p className="rail-history-empty">No estimates in saved reports yet.</p>
              : <div className="rail-topic-list">{recentComplexity.map((item) => (
                <div className="rail-complexity-row" key={item.id}>
                  <code>{item.summary?.complexity}</code>
                  <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleDateString()}</time>
                </div>
              ))}</div>}
          </details>
          <div className="rail-bottom"><div className="rail-section-label">RUNTIME</div><div className="runtime-state"><span className="runtime-pip" /> API checked on run</div></div>
        </aside>

        <section className="main-panel">
          <div className="page-heading">
            <div><div className="eyebrow">MODE 1 <span>/</span> DSA SOLUTION ANALYZER</div><h1>Check your solution.</h1><p>Paste a problem and your code. Axioma supplies checks and growth benchmarks when the problem pack supports them.</p></div>
            <div className="page-actions">{report && <button className="quiet-button" onClick={exportReport}>EXPORT REPORT JSON</button>}{canCancel && <button className="quiet-button" onClick={() => void stopJob()}>Cancel job</button>}<button className="run-button" onClick={() => void runAnalysis()} disabled={busy || isRunning}><span>{busy || isRunning ? '◌' : '▶'}</span>{busy ? 'SUBMITTING' : isRunning ? 'ANALYZING' : 'RUN ANALYSIS'}</button></div>
          </div>

          {error && <div className="error-banner" role="alert"><span>!</span>{error}<button onClick={() => setError(null)} aria-label="Dismiss error">×</button></div>}

          <div className="workbench">
            <section className="input-panel" aria-label="Problem statement">
              <div className="panel-heading"><span>01</span><h2>Problem</h2><span className="panel-meta">PASTE STATEMENT</span></div>
              <label className="field-label" htmlFor="problem-statement">PROBLEM STATEMENT</label>
              <textarea id="problem-statement" className="text-input statement-input" value={statement} onChange={(event) => { setStatement(event.target.value); setProblemMatch(null); setProposal(null); setProposalMessage(null) }} onBlur={() => { if (statement.trim()) void identifyStatement(statement).catch(() => setProblemMatch(null)) }} rows={7} placeholder="Paste the full problem statement here. Axioma will look for a matching test pack." />
              <div className={`problem-match${problemMatch?.recognized ? ' matched' : problemMatch ? ' unmatched' : ''}`} aria-live="polite">
                {matching ? <><span className="match-pip" />Looking for a supported problem…</> : problemMatch?.recognized
                  ? <><b>{problemMatch.title}</b><span>{problemMatch.test_count} Axioma checks ready</span><details><summary>TEST PACK SOURCE</summary><small>{problemMatch.test_source}</small></details></>
                  : problemMatch ? <><b>Problem not recognized yet</b><span>Check that the problem title is included in the pasted statement.</span></>
                    : <><span className="match-pip idle" />Test cases and problem details will be filled in when Axioma recognizes the statement.</>}
              </div>
              <div className="input-note"><span>i</span><p>Only the statement and your solution are needed. Test cases are supplied by Axioma for supported problems.</p></div>
            </section>

            <section className="editor-panel" aria-label="Candidate source code">
              <div className="panel-heading"><span>02</span><h2>Your code</h2><label className="language-picker"><span className="field-label">LANGUAGE</span><select value={language} onChange={(event) => { setLanguage(event.target.value as Language); setProposal(null); setProposalMessage(null) }}><option value="python">Python</option><option value="java">Java</option></select></label></div>
              <label className="field-label" htmlFor="candidate-code">SOLUTION · EDITABLE</label>
              <textarea id="candidate-code" className="text-input code-input source-editor" value={code} onChange={(event) => updateCode(event.target.value)} spellCheck={false} aria-label="Candidate source code" placeholder={language === 'python' ? 'Paste your Python solution here…' : 'Paste your Java solution here…'} />
              <div className="editor-footer"><span><i className="editor-dot" /> UNSAVED SOURCE</span><span>UTF-8 <i>·</i> SPACES: 4</span></div>
              <div className="editor-callout"><span>↳</span><p>Axioma checks this code against the matched problem pack and reports which cases pass or fail.</p></div>
              <section className="proposal-panel" aria-label="Optimization suggestions">
                <div className="proposal-heading"><div><span className="field-label">OPTIONAL · RULE-BASED</span><h3>Look for an improvement</h3></div><button className="quiet-button" onClick={() => void findOptimization()} disabled={proposalBusy || busy || isRunning || !code.trim()}>{proposalBusy ? 'CHECKING…' : 'SUGGEST'}</button></div>
                <p>For supported patterns, Axioma can offer a candidate. It never replaces your code automatically.</p>
                {proposalMessage && <div className={`proposal-message${proposal ? ' proposal-found' : ''}`} role="status">{proposalMessage}</div>}
                {proposal && <div className="proposal-result"><h4>{proposal.title}</h4><p>{proposal.summary}</p><details><summary>VIEW CANDIDATE AND LIMITATIONS</summary><pre>{proposal.candidate_code}</pre><ul>{proposal.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul></details><button className="run-button proposal-verify" onClick={() => void runAnalysis(proposal)} disabled={busy || isRunning}>{busy ? 'SUBMITTING…' : 'VERIFY WITH TESTS + BENCHMARKS'}</button><small>Runs the original and candidate against the same problem checks. Your editor code stays unchanged.</small></div>}
              </section>
            </section>
            <section className="results-panel" aria-label="Analysis results" aria-live="polite">
              <div className="panel-heading"><span>03</span><h2>Analysis</h2><span className="panel-meta">{report ? 'RESULT' : 'LIVE STATUS'}</span></div>
              <JobStatusView job={job} />
              {report ? <>
                <div className="report-results">
                  <div className="summary-strip"><div><b>{report.tests.total}</b><span>CHECKS</span></div><div className="pass-value"><b>{report.tests.passed}</b><span>PASSED</span></div><div className="fail-value"><b>{report.tests.failed}</b><span>FAILED</span></div><div className="skip-value"><b>{report.tests.skipped}</b><span>SKIPPED</span></div></div>
                  <section className="report-section complexity-section" aria-labelledby="complexity-heading">
                    <div className="report-section-heading"><h3 id="complexity-heading">Time complexity</h3><span>ESTIMATE</span></div>
                    <Complexity result={report.complexity} />
                  </section>
                  <section className="report-section" aria-labelledby="claims-heading">
                    <div className="report-section-heading"><h3 id="claims-heading">Evidence</h3><span>{report.claims.length} {report.claims.length === 1 ? 'CLAIM' : 'CLAIMS'}</span></div>
                    <Claims claims={report.claims} />
                  </section>
                  {report.verification_gates.length > 0 && <GateList gates={report.verification_gates} />}
                  <div className="report-foot">RESULTS REFLECT THIS RUN'S CONFIGURED CHECKS</div>
                </div>
              </> : <EmptyResults job={job} />}
            </section>
          </div>
          <footer className="page-foot"><span>AXIOMA <i>/</i> MODE 1 WORKSPACE</span><span>NO CLAIM WITHOUT CONTEXT</span><span>LOCAL BUILD · 0.1.0</span></footer>
        </section>
      </div>
    </main>
  )
}

function JobStatusView({ job }: { job: Job | null }) {
  if (!job) return null
  const label: Record<JobStatus, string> = {
    queued: 'QUEUED', running: 'RUNNING', completed: 'COMPLETE', failed: 'FAILED', cancelled: 'CANCELLED',
  }
  return <div className={`job-status status-${job.status}`}><span className="status-pip" /><div><b>{label[job.status]}</b><p>{job.progress_message ?? 'Job accepted by the API.'}</p></div><code title="Job ID">{job.id.slice(0, 8)}</code></div>
}

function EmptyResults({ job }: { job: Job | null }) {
  const copy = job?.status === 'failed'
    ? 'The worker could not complete this run. Check that the API, worker, and sandbox are available.'
    : job?.status === 'cancelled'
      ? 'This run was cancelled before a report was produced.'
      : job
        ? 'Waiting for the worker. Status updates arrive over the live job stream.'
        : 'No analysis has run yet. Submit the problem and candidate to see evidence here.'
  return <div className="empty-results"><span className="empty-glyph">A.</span><p>{copy}</p>{job && <span className="empty-id">JOB {job.id}</span>}</div>
}

function EvidenceBadge({ type, confidence }: { type: string; confidence: string }) {
  return <div className="evidence-badges"><span className={`evidence-type type-${type}`}>{type.replaceAll('_', ' ')}</span><span className={`confidence confidence-${confidence}`}>{confidence} confidence</span></div>
}

function Claims({ claims }: { claims: AnalysisReport['claims'] }) {
  if (claims.length === 0) return <div className="empty-claims">This run did not produce evidence claims.</div>
  return <div className="claim-list">{claims.map((claim) => {
    const optimization = claim.type === 'executed' && claim.provenance.tool?.includes('optimization-checker')
    return <article className="claim-card" key={claim.id}><div className="claim-top"><span className="claim-id">{claim.id}</span><EvidenceBadge type={claim.type} confidence={claim.confidence} /></div><p>{claim.summary}</p>{optimization && <OptimizationReview details={claim.provenance.details as OptimizationReviewDetails} />}<details><summary>PROVENANCE</summary><dl><dt>TOOL</dt><dd>{claim.provenance.tool ?? 'Not recorded'}</dd><dt>VERSION</dt><dd>{claim.provenance.tool_version ?? 'Not recorded'}</dd>{claim.provenance.input_hash && <><dt>INPUT HASH</dt><dd className="hash-value">{claim.provenance.input_hash}</dd></>}</dl></details></article>
  })}</div>
}

interface OptimizationReviewDetails {
  state?: string
  checks?: { requested?: number; checked?: number; passed?: number; failed?: number; skipped?: number }
  original_code?: string
  optimized_code?: string
  optimization_notes?: string | null
  complexity_before?: { method?: string; estimate?: string; confidence?: string }
  complexity_after?: { method?: string; estimate?: string; confidence?: string }
  measurements?: Record<string, unknown>[]
  measurement_method?: string
  measurement_skipped_reason?: string | null
  measurement_limit?: string
  limitation?: string
  warmups?: number
  trials?: number
}

function OptimizationReview({ details }: { details: OptimizationReviewDetails }) {
  const limit = details.measurement_limit ?? details.limitation
  return <section className="optimization-review" aria-label="Optimization candidate review"><div className={`optimization-state optimization-${details.state ?? 'inconclusive'}`}>{(details.state ?? 'inconclusive').toUpperCase()} EQUIVALENCE</div>{details.checks && <div className="optimization-counts"><span>{details.checks.passed ?? 0} passed</span><span>{details.checks.failed ?? 0} failed</span><span>{details.checks.skipped ?? 0} skipped</span><span>{details.checks.checked ?? 0}/{details.checks.requested ?? 0} checked</span></div>}{details.optimization_notes && <p className="optimization-notes">{details.optimization_notes}</p>}<div className="optimization-complexity"><div><span>BEFORE</span><b>{details.complexity_before?.estimate ?? '—'}</b><small>{details.complexity_before?.method ?? 'No estimate'}</small></div><div><span>AFTER</span><b>{details.complexity_after?.estimate ?? '—'}</b><small>{details.complexity_after?.method ?? 'No estimate'}</small></div></div>{details.measurements?.length ? <details><summary>MEASUREMENTS · {details.measurement_method ?? 'method not recorded'}</summary><pre>{JSON.stringify(details.measurements, null, 2)}</pre></details> : <p className="field-hint">{details.measurement_skipped_reason ?? 'No measurements were produced for this run.'}</p>}<details><summary>BEFORE AND ALTERNATE SOURCE</summary><div className="optimization-source"><span>ORIGINAL</span><pre>{details.original_code ?? 'Not recorded'}</pre><span>USER-PROVIDED CANDIDATE</span><pre>{details.optimized_code ?? 'Not recorded'}</pre></div></details>{limit && <p className="field-hint">{limit}{details.warmups && details.trials ? ` Trials: ${details.trials}; warmups: ${details.warmups}.` : ''}</p>}</section>
}

function Complexity({ result }: { result: AnalysisReport['complexity'] }) {
  if (!result) return <div className="complexity-unavailable">Axioma could not produce a complexity estimate for this solution.</div>
  const analysis = result.details.code_analysis as {
    signals?: { kind: string; label: string; line?: number | null }[]
    loop_count?: number
    maximum_loop_nesting?: number
    scope?: string
    limitations?: string[]
  } | undefined
  return <article className="complexity-card"><div className="complexity-head"><div><span className="field-label">ESTIMATE</span><h3>{result.estimate}</h3></div><span className={`confidence confidence-${result.confidence}`}>{result.confidence} confidence</span></div><div className="method-line"><span>METHOD</span><code>{result.method}</code></div>{result.methods_disagree && <div className="disagree-note"><b>METHODS DISAGREE</b><p>The available estimates did not agree. Review the measurements before relying on this class.</p></div>}{result.explanation && <p className="complexity-explanation">{result.explanation}</p>}{analysis && <section className="code-analysis-signals" aria-label="Detected code patterns"><div className="signals-heading"><b>WHAT AXIOMA FOUND</b><span>{analysis.loop_count ?? 0} loops · max nesting {analysis.maximum_loop_nesting ?? 0}</span></div>{analysis.signals?.length ? <ul>{analysis.signals.map((signal, index) => <li key={`${signal.kind}-${signal.line ?? 'na'}-${index}`}><span>{signal.label}</span>{signal.line ? <code>LINE {signal.line}</code> : null}</li>)}</ul> : <p>No listed patterns were detected in the selected function.</p>}{analysis.scope && <small>{analysis.scope}.</small>}{analysis.limitations?.length ? <details><summary>LIMITS OF THIS ANALYSIS</summary><ul>{analysis.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul></details> : null}</section>}<details><summary>MEASUREMENT DETAILS</summary><pre>{JSON.stringify(result.details, null, 2)}</pre></details></article>
}

function GateList({ gates }: { gates: AnalysisReport['verification_gates'] }) {
  const labels = { passed: 'PASSED', failed: 'FAILED', not_run: 'NOT RUN' }
  return <div className="gate-list"><h3>VERIFICATION GATES</h3>{gates.map((gate) => <div className="gate-row" key={`${gate.order}-${gate.name}`}><span className="gate-order">{String(gate.order + 1).padStart(2, '0')}</span><span>{gate.name}</span><b className={`gate-state gate-${gate.state}`}>{labels[gate.state]}</b></div>)}</div>
}

function App() {
  return window.location.pathname === '/analyzer'
    ? <AnalyzerApp />
    : <LandingPage />
}

export default App
