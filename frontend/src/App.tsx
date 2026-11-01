import { useEffect, useRef, useState } from 'react'
import { ApiError, cancelJob, findOptimizationProposals, generateComplexityBenchmarks, getJob, getReport, matchProblem, requestGemmaReview, submitJob } from './api'
import type { AnalysisReport, GemmaReviewResponse, Job, JobStatus, Language, OptimizationProposal, ProblemMatch } from './types'
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
  const [gemmaReview, setGemmaReview] = useState<GemmaReviewResponse | null>(null)
  const [gemmaBusy, setGemmaBusy] = useState(false)
  const [gemmaError, setGemmaError] = useState<string | null>(null)
  const [history, setHistory] = useState<HistoryEntry[]>(readHistory)
  const [job, setJob] = useState<Job | null>(null)
  const [report, setReport] = useState<AnalysisReport | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const eventSource = useRef<EventSource | null>(null)
  const lineNumberGutter = useRef<HTMLDivElement | null>(null)
  const codeEditor = useRef<HTMLTextAreaElement | null>(null)
  const codeLineCount = Math.max(1, code.split('\n').length)
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
    setReport(null)
    setProposal(null)
    setProposalMessage(null)
    setGemmaReview(null)
    setGemmaError(null)
  }

  function goToSourceLocation(location: string) {
    const lineMatch = location.match(/:(\d+)(?::\d+)?$/)
    const editor = codeEditor.current
    if (!editor || !lineMatch) return
    const lineNumber = Number(lineMatch[1])
    let start = 0
    for (let line = 1; line < lineNumber; line += 1) {
      const nextLine = code.indexOf('\n', start)
      if (nextLine < 0) return
      start = nextLine + 1
    }
    const newline = code.indexOf('\n', start)
    editor.focus()
    editor.setSelectionRange(start, newline < 0 ? code.length : newline)
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

  async function askGemma() {
    setGemmaBusy(true)
    setGemmaReview(null)
    setGemmaError(null)
    try {
      if (!report || !job || job.status !== 'completed' || report.job_id !== job.id) {
        throw new Error('Run Axioma analysis on the current problem and code first.')
      }
      const result = await requestGemmaReview({
        job_id: report.job_id,
        language,
        code,
        problem_statement: statement,
      })
      setGemmaReview(result)
    } catch (reason) {
      setGemmaError(reason instanceof Error ? reason.message : 'Gemma review failed.')
    } finally {
      setGemmaBusy(false)
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
              <textarea id="problem-statement" className="text-input statement-input" value={statement} onChange={(event) => { setStatement(event.target.value); setReport(null); setProblemMatch(null); setProposal(null); setProposalMessage(null); setGemmaReview(null); setGemmaError(null) }} onBlur={() => { if (statement.trim()) void identifyStatement(statement).catch(() => setProblemMatch(null)) }} rows={7} placeholder="Paste the full problem statement here. Axioma will look for a matching test pack." />
              <ProblemMatchCard matching={matching} problemMatch={problemMatch} />
              <div className="input-note"><span>i</span><p>Only the statement and your solution are needed. Test cases are supplied by Axioma for supported problems.</p></div>
            </section>

            <section className="editor-panel" aria-label="Candidate source code">
              <div className="panel-heading"><span>02</span><h2>Your code</h2><label className="language-picker"><span className="field-label">LANGUAGE</span><select value={language} onChange={(event) => { setLanguage(event.target.value as Language); setReport(null); setProposal(null); setProposalMessage(null); setGemmaReview(null); setGemmaError(null) }}><option value="python">Python</option><option value="java">Java</option></select></label></div>
              <label className="field-label" htmlFor="candidate-code">SOLUTION · EDITABLE</label>
              <div className="source-editor-wrap">
                <div className="line-number-gutter" ref={lineNumberGutter} aria-hidden="true">{Array.from({ length: codeLineCount }, (_, index) => <span key={index}>{index + 1}</span>)}</div>
                <textarea id="candidate-code" ref={codeEditor} className="text-input code-input source-editor" value={code} onChange={(event) => updateCode(event.target.value)} onScroll={(event) => { if (lineNumberGutter.current) lineNumberGutter.current.scrollTop = event.currentTarget.scrollTop }} spellCheck={false} aria-label="Candidate source code" placeholder={language === 'python' ? 'Paste your Python solution here…' : 'Paste your Java solution here…'} />
              </div>
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
                  <section className="proposal-panel gemma-panel" aria-label="Gemma 4 advisory">
                    <div className="proposal-heading"><div><span className="field-label">OPTIONAL · GEMMA 4 · LOW CONFIDENCE</span><h3>Check for a better approach</h3></div><button className="quiet-button" onClick={() => void askGemma()} disabled={gemmaBusy || busy || isRunning || job?.status !== 'completed'}>{gemmaBusy ? 'ANALYZING…' : 'CHECK EFFICIENCY'}</button></div>
                    <p>Gemma compares your solution with Axioma’s time estimate and may report current and alternative auxiliary space. Estimates are unverified; suggestions never change your code. This sends your code to Google’s Gemini API, where free-tier content may be used to improve its products.</p>
                    {gemmaError && <div className="proposal-message" role="alert">{gemmaError}</div>}
                    {gemmaReview && <div className="gemma-review" role="status"><div className="gemma-review-meta">MODEL SUGGESTION · {gemmaReview.model} · LOW CONFIDENCE</div><pre>{gemmaReview.advisory}</pre><ul>{gemmaReview.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul></div>}
                  </section>
                  <EvidenceReview report={report} />
                  <section className="report-section complexity-section" aria-labelledby="complexity-heading">
                    <div className="report-section-heading"><h3 id="complexity-heading">Complexity estimate</h3><span>HEURISTIC</span></div>
                    <Complexity result={report.complexity} />
                  </section>
                  <details className="report-section checks-dropdown" aria-labelledby="checks-heading">
                    <summary className="report-section-heading"><h3 id="checks-heading">Checks and input cases</h3><span>{report.tests.total} CHECKS · {report.tests.passed} PASSED · {report.tests.failed} FAILED · {report.tests.skipped} SKIPPED</span></summary>
                    <TestCaseList cases={report.test_cases} summary={report.tests} onGoToLocation={goToSourceLocation} />
                  </details>
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

export function JobStatusView({ job }: { job: Job | null }) {
  if (!job) return null
  const label: Record<JobStatus, string> = {
    queued: 'QUEUED', running: 'RUNNING', completed: 'COMPLETE', failed: 'WORKER FAILURE', cancelled: 'CANCELLED',
  }
  return <div className={`job-status status-${job.status}`}><span className="status-pip" /><div><b>{label[job.status]}</b><p>{job.progress_message ?? 'Job accepted by the API.'}</p>{job.status === 'failed' && job.error_code && <small>Failure category: {failureLabel(job.error_code)}</small>}</div><code title="Job ID">{job.id.slice(0, 8)}</code></div>
}

export function EmptyResults({ job }: { job: Job | null }) {
  const copy = job?.status === 'failed'
    ? 'The worker could not complete this run. Check that the API, worker, and sandbox are available.'
    : job?.status === 'cancelled'
      ? 'This run was cancelled before a report was produced.'
      : job
        ? 'Waiting for the worker. Status updates arrive over the live job stream.'
        : 'No analysis has run yet. Submit the problem and candidate to see evidence here.'
  return <div className="empty-results"><span className="empty-glyph">A.</span><p>{copy}</p>{job && <span className="empty-id">JOB {job.id}</span>}{!job && <div className="empty-review-prompts"><b>YOUR REPORT WILL SHOW</b><div><span>01</span><section><strong>Which checks ran?</strong><small>Per-case outcomes and where each check came from.</small></section></div><div><span>02</span><section><strong>What inputs were covered?</strong><small>Recorded case inputs when Axioma can link them safely.</small></section></div><div><span>03</span><section><strong>What code signals were detected?</strong><small>Supported patterns used by the static analysis.</small></section></div><div><span>04</span><section><strong>Where are the limits?</strong><small>Method, confidence, and documented caveats.</small></section></div></div>}</div>
}

function evidenceLabel(type: string) {
  return ({ executed: 'Executed check', static: 'Static heuristic', statistical: 'Statistical evidence', model: 'Model prediction', unverified: 'Unverified' } as Record<string, string>)[type] ?? 'Unknown evidence'
}

export function ProblemMatchCard({ matching, problemMatch }: { matching: boolean; problemMatch: ProblemMatch | null }) {
  return <div className={`problem-match${problemMatch?.recognized ? ' matched' : problemMatch ? ' unmatched' : ''}`} aria-live="polite">
    {matching ? <><span className="match-pip" />Looking for a supported problem…</> : problemMatch?.recognized
      ? <><b>{problemMatch.title}</b><span>{problemMatch.test_count} Axioma checks ready</span><details><summary>TEST PACK SOURCE</summary><small>{problemMatch.test_source}</small></details></>
      : problemMatch?.match_state === 'ambiguous'
        ? <><b>More than one problem may match</b><span>No pack was selected. Add the exact problem title to narrow it down.</span><ul>{problemMatch.candidate_titles.map((title) => <li key={title}>{title}</li>)}</ul></>
        : problemMatch ? <><b>No supported problem match</b><span>The current catalog could not find a sufficiently reliable match. No tests will be selected automatically.</span></>
          : <><span className="match-pip idle" />Test cases and problem details will be filled in when Axioma recognizes the statement.</>}
  </div>
}

function originLabel(claim: AnalysisReport['claims'][number]) {
  const tool = claim.provenance.tool ?? ''
  if (tool.includes('benchmark')) return 'Empirical benchmark'
  if (tool.includes('optimization-checker')) return 'Rule-based candidate verification'
  if (tool.includes('catalog')) return 'Imported problem examples'
  if (tool.includes('generated') || tool.includes('differential')) return 'Generated differential check'
  if (tool.includes('mutation')) return 'Mutation testing'
  if (tool.includes('property')) return 'User-supplied property checks'
  if (tool.includes('harness') || tool.includes('stdin-worker')) return 'Axioma test harness'
  if (claim.type === 'model') return 'No model is configured in Mode 1'
  return 'Origin recorded in provenance'
}

export function EvidenceBadge({ type, confidence }: { type: string; confidence: string }) {
  return <div className="evidence-badges"><span className={`evidence-type type-${type}`}>{evidenceLabel(type)}</span><span className={`confidence confidence-${confidence}`}>{confidence} confidence</span></div>
}

export function Claims({ claims }: { claims: AnalysisReport['claims'] }) {
  if (claims.length === 0) return <div className="empty-claims">This run did not produce evidence claims.</div>
  return <div className="claim-list">{claims.map((claim) => {
    const optimization = claim.type === 'executed' && claim.provenance.tool?.includes('optimization-checker')
    return <article className="claim-card" key={claim.id}><div className="claim-top"><span className="claim-id">{claim.id}</span><EvidenceBadge type={claim.type} confidence={claim.confidence} /></div><p>{claim.summary}</p><small className="claim-origin">{originLabel(claim)}</small>{optimization && <OptimizationReview details={claim.provenance.details as OptimizationReviewDetails} />}</article>
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

export function Complexity({ result }: { result: AnalysisReport['complexity'] }) {
  if (!result) return <div className="complexity-unavailable">Axioma could not produce a complexity estimate for this solution.</div>
  const analysis = result.details.code_analysis as {
    signals?: { kind: string; label: string; line?: number | null }[]
    loop_count?: number
    maximum_loop_nesting?: number
    scope?: string
    limitations?: string[]
    auxiliary_space?: {
      state?: string
      estimate?: string | null
      method?: string
      reasoning?: string
      limitations?: string[]
    }
  } | undefined
  const points = Array.isArray(result.details.points) ? result.details.points as Record<string, unknown>[] : []
  const space = typeof result.details.space_measurement === 'object' && result.details.space_measurement !== null ? result.details.space_measurement as Record<string, unknown> : null
  const hasStaticEstimate = !result.estimate.startsWith('unknown')
  const storedStaticEstimate = typeof result.details.static_estimate === 'string' ? result.details.static_estimate : null
  const legacyCombinedEstimate = points.length > 0 && result.method.includes('+dynamic') && storedStaticEstimate === null
  const staticEstimate = storedStaticEstimate ?? (legacyCombinedEstimate ? null : result.estimate)
  const auxiliarySpace = analysis?.auxiliary_space
  return <article className="complexity-card"><div className="complexity-head"><div><span className="field-label">STATIC ESTIMATE · HEURISTIC</span><h3>{staticEstimate ? staticEstimate : hasStaticEstimate ? 'Not stored separately for this saved run' : 'Unable to estimate reliably'}</h3></div><span className={`confidence confidence-${result.confidence}`}>{result.confidence} confidence</span></div><div className="method-line"><span>METHOD</span><code>{result.method}</code></div>{result.methods_disagree && <div className="disagree-note"><b>METHODS DISAGREE</b><p>The available estimates did not agree. Review the measurements before relying on this class.</p></div>}{result.explanation && <p className="complexity-explanation">{result.explanation}</p>}{analysis && <section className="code-analysis-signals" aria-label="Detected code patterns"><div className="signals-heading"><b>WHAT AXIOMA FOUND</b><span>{analysis.loop_count ?? 0} loops · max nesting {analysis.maximum_loop_nesting ?? 0}</span></div>{analysis.signals?.length ? <ul>{analysis.signals.map((signal, index) => <li key={`${signal.kind}-${signal.line ?? 'na'}-${index}`}><span>{signal.label}</span>{signal.line ? <code>LINE {signal.line}</code> : null}</li>)}</ul> : <p>No listed patterns were detected in the selected function.</p>}{analysis.scope && <small>{analysis.scope}.</small>}{analysis.limitations?.length ? <details><summary>LIMITS OF THIS ANALYSIS</summary><ul>{analysis.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul></details> : null}</section>}{auxiliarySpace && <section className="space-observation"><h4>Auxiliary space · static estimate</h4>{auxiliarySpace.state === 'estimated' && typeof auxiliarySpace.estimate === 'string' ? <><b>{auxiliarySpace.estimate}</b><span>Low-confidence upper bound · excludes input and returned output</span><small>{auxiliarySpace.reasoning ?? auxiliarySpace.method}</small>{auxiliarySpace.limitations?.length ? <details><summary>LIMITS OF THIS SPACE ESTIMATE</summary><ul>{auxiliarySpace.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul></details> : null}</> : <span>{auxiliarySpace.reasoning ?? 'Unknown — this code pattern is not covered by the current space rules.'}</span>}</section>}{points.length > 0 && <section className="empirical-measurements"><h4>Empirical benchmark · not an asymptotic proof</h4><small>{String(result.details.measurement_method ?? 'Measurement method not recorded')}{typeof result.details.fit === 'string' ? ` · observed growth fit: ${result.details.fit}` : ''}</small><ul>{points.map((point, index) => <li key={`${String(point.size)}-${index}`}><span>Input size {String(point.size ?? 'not recorded')}</span><code>{formatMeasurement(point)}</code>{typeof point.input_strategy === 'string' && <small>{point.input_strategy}</small>}</li>)}</ul></section>}<section className="space-observation"><h4>Measured memory growth</h4>{space?.state === 'estimated' && typeof space.estimate === 'string' ? <><b>{space.estimate}</b><span>Observed growth · not an asymptotic proof</span><small>{String(space.measurement ?? space.method ?? 'Memory observation')}</small></> : <span>No memory growth measurement was recorded for this run.</span>}</section><details><summary>RAW ANALYSIS DETAILS</summary><pre>{JSON.stringify(result.details, null, 2)}</pre></details></article>
}

export function EvidenceReview({ report }: { report: AnalysisReport }) {
  const codeAnalysis = report.complexity?.details.code_analysis as {
    signals?: { label: string }[]
    limitations?: string[]
  } | undefined
  const signalCount = codeAnalysis?.signals?.length ?? 0
  const inputCount = report.test_cases.filter((test) => Boolean(test.input_preview)).length
  const limitationsCount = codeAnalysis?.limitations?.length ?? 0
  const signalSummary = signalCount
    ? codeAnalysis?.signals?.slice(0, 2).map((signal) => signal.label).join(' · ')
    : report.complexity ? 'No supported code signals were listed.' : 'No complexity analysis was produced.'

  return <section className="evidence-review" aria-label="Evidence review">
    <div className="evidence-review-heading"><div><span className="field-label">REVIEW SURFACE</span><h3>Four questions, from this run</h3></div><span>NO INFERRED COVERAGE</span></div>
    <div className="evidence-review-grid">
      <a className="review-tile" href="#checks-heading"><span>01 · CHECKS</span><b>{report.tests.total} case{report.tests.total === 1 ? '' : 's'} recorded</b><small>{report.tests.passed} passed · {report.tests.failed} failed · {report.tests.skipped} skipped</small></a>
      <a className="review-tile" href="#checks-heading"><span>02 · INPUTS</span><b>{inputCount} / {report.test_cases.length} inputs available</b><small>Saved inputs show what was configured; they do not prove full edge-case coverage.</small></a>
      <a className="review-tile" href="#complexity-heading"><span>03 · CODE SIGNALS</span><b>{signalCount} signal{signalCount === 1 ? '' : 's'} detected</b><small>{signalSummary}</small></a>
      <a className="review-tile" href="#complexity-heading"><span>04 · CLAIM LIMITS</span><b>{report.complexity ? `${report.complexity.confidence} confidence` : 'No reliable estimate'}</b><small>{limitationsCount ? `${limitationsCount} documented limitation${limitationsCount === 1 ? '' : 's'} · inspect estimate details` : 'Review the method and caveats before relying on an estimate.'}</small></a>
    </div>
  </section>
}

function formatMeasurement(point: Record<string, unknown>) {
  if (typeof point.line_events === 'number') return `${point.line_events} source-line events`
  if (typeof point.median_elapsed_ns === 'number') return `${point.median_elapsed_ns} ns median`
  if (typeof point.elapsed_ns === 'number') return `${point.elapsed_ns} ns`
  return 'Measurement value unavailable'
}

function failureLabel(kind: string) {
  return ({ compile_error: 'Compiler error', runtime_error: 'Runtime error', timeout: 'Timed out', incorrect_output: 'Incorrect output', oracle_error: 'Reference/oracle check failed', worker_error: 'Worker error', sandbox_unavailable: 'Sandbox unavailable' } as Record<string, string>)[kind] ?? kind.replaceAll('_', ' ')
}

function diagnosticLocation(details: Record<string, unknown>, diagnostic: string) {
  const recorded = details.source_location
  if (typeof recorded === 'object' && recorded !== null) {
    const location = recorded as Record<string, unknown>
    if (typeof location.line === 'number') {
      const file = typeof location.file === 'string' ? location.file : 'Source'
      const column = typeof location.column === 'number' ? `:${location.column}` : ''
      return `${file}:${location.line}${column}`
    }
  }

  const python = diagnostic.match(/File ["']([^"']+)["'], line (\d+)(?:, column (\d+))?/)
    ?? diagnostic.match(/\(([^(),]+), line (\d+)\)/)
  if (python) return `${python[1]}:${python[2]}${python[3] ? `:${python[3]}` : ''}`

  const java = diagnostic.match(/([\w.$-]+\.java):(\d+)(?::(\d+))?/)
  return java ? `${java[1]}:${java[2]}${java[3] ? `:${java[3]}` : ''}` : null
}

export function TestCaseList({ cases, summary, onGoToLocation }: { cases: AnalysisReport['test_cases']; summary: AnalysisReport['tests']; onGoToLocation?: (location: string) => void }) {
  if (cases.length === 0) return <div className="empty-claims">No per-case results were recorded. Summary: {summary.passed} passed, {summary.failed} failed, {summary.skipped} skipped.</div>
  const groups = [
    { outcome: 'failed', label: 'FAILED CASES' },
    { outcome: 'passed', label: 'PASSED CASES' },
    { outcome: 'skipped', label: 'SKIPPED CASES' },
  ] as const
  return <div className="test-case-groups">{groups.map((group) => {
    const groupedCases = cases
      .filter((test) => test.outcome === group.outcome)
      .sort((left, right) => left.name.localeCompare(right.name, undefined, { numeric: true, sensitivity: 'base' }))
    if (groupedCases.length === 0) return null
    return <section className={`test-case-group group-${group.outcome}`} key={group.outcome}>
      <div className="test-case-group-heading"><h4>{group.label}</h4><span>{groupedCases.length}</span></div>
      <div className="test-case-list">{groupedCases.map((test, index) => {
    const kind = typeof test.details.failure_kind === 'string' ? test.details.failure_kind : null
    const origin = ({ catalog_sample: 'Imported sample', generated_differential: 'Generated differential', reference_validation: 'Reference validation', property_check: 'Property check', program_execution: 'Program execution', unknown: 'Origin unknown' } as Record<string, string>)[test.origin]
    const expected = test.details.expected ?? test.details.expected_stdout
    const observed = test.details.actual ?? test.details.actual_stdout
    const diagnostic = ['error', 'reason', 'stderr', 'message']
      .map((key) => test.details[key])
      .find((value): value is string => typeof value === 'string' && value.trim().length > 0)
    const location = diagnostic ? diagnosticLocation(test.details, diagnostic) : null
    const hasSourceError = kind === 'compile_error' || kind === 'runtime_error'
    return <details className={`test-case test-${test.outcome}`} key={`${test.name}-${index}`}>
      <summary className="test-case-summary"><span><b>{test.name}</b><small>{origin}{kind ? ` · ${failureLabel(kind)}` : ''}</small></span><strong>{test.outcome.toUpperCase()}</strong></summary>
      {test.details.truncated === true && <small>Output truncated by Axioma; showing a bounded preview.</small>}
      {test.outcome === 'failed' && hasSourceError && diagnostic && <section className="test-diagnostic" aria-label="Failure diagnostic"><div className="test-diagnostic-heading"><b>{failureLabel(kind!)}</b>{location ? onGoToLocation ? <button type="button" className="diagnostic-location" aria-label={`Go to ${location} in editor`} onClick={() => onGoToLocation(location)}>{location} ↗</button> : <code>{location}</code> : <small>Source location not recorded</small>}</div><pre>{diagnostic.slice(0, 4000)}</pre></section>}
      {expected !== undefined && <dl className="test-case-values"><dt>EXPECTED</dt><dd>{JSON.stringify(expected)}</dd><dt>OBSERVED</dt><dd>{observed === undefined ? 'Not recorded' : JSON.stringify(observed)}</dd></dl>}
      {test.input_preview && <div className="case-input-preview"><b>TEST INPUT{test.input_preview.truncated ? ' · BOUNDED PREVIEW' : ''}</b><pre>{JSON.stringify(test.input_preview.data, null, 2)}</pre><small>Snapshot SHA-256 {test.input_preview.sha256.slice(0, 16)}{test.input_preview.truncated ? ' · hash covers the full saved snapshot' : ''}</small></div>}
      <details><summary>CASE DETAILS</summary><pre>{JSON.stringify(test.details, null, 2)}</pre></details>
    </details>
      })}</div>
    </section>
  })}</div>
}

export function GateList({ gates }: { gates: AnalysisReport['verification_gates'] }) {
  const labels = { passed: 'PASSED', failed: 'FAILED', not_run: 'NOT RUN' }
  return <div className="gate-list"><h3>VERIFICATION GATES</h3>{gates.map((gate) => <div className="gate-row" key={`${gate.order}-${gate.name}`}><span className="gate-order">{String(gate.order + 1).padStart(2, '0')}</span><span>{gate.name}</span><b className={`gate-state gate-${gate.state}`}>{labels[gate.state]}</b></div>)}</div>
}

function App() {
  return window.location.pathname === '/analyzer'
    ? <AnalyzerApp />
    : <LandingPage />
}

export default App
