import { useEffect, useRef, useState } from 'react'
import { ApiError, cancelJob, findOptimizationProposals, getJob, getReport, submitJob } from './api'
import type { AnalysisReport, Job, JobStatus, Language, OptimizationProposal, ProblemKind } from './types'
import LandingPage from './LandingPage'
import './App.css'

const starterSamples = JSON.stringify(
  [{ name: 'example', args: [[1, 2, 3]], kwargs: {}, expected: 6 }],
  null,
  2,
)
const starterStdinSamples = JSON.stringify(
  [{ name: 'example', stdin: '1 2 3\n', expected_stdout: '6\n' }],
  null,
  2,
)

const starterConstraints = JSON.stringify(
  [{ path: 'args[0].length', minimum: 1, maximum: 100 }],
  null,
  2,
)

const starterCode: Record<Language, string> = {
  python: 'def solve(values):\n    return sum(values)\n',
  java: 'class Solution {\n    public int solve(int[] values) {\n        int total = 0;\n        for (int value : values) total += value;\n        return total;\n    }\n}\n',
}
const starterStdinCode: Record<Language, string> = {
  python: 'import sys\n\nvalues = list(map(int, sys.stdin.read().split()))\nprint(sum(values))\n',
  java: 'import java.util.*;\n\nclass Main {\n    public static void main(String[] args) {\n        Scanner scanner = new Scanner(System.in);\n        long total = 0;\n        while (scanner.hasNextLong()) total += scanner.nextLong();\n        System.out.println(total);\n    }\n}\n',
}

const starterEntrypoint: Record<Language, string> = {
  python: 'solve',
  java: 'Solution.solve',
}

const terminalStatuses = new Set<JobStatus>(['completed', 'failed', 'cancelled'])
const historyStorageKey = 'axioma.mode1.recent-jobs.v1'
const historyLimit = 20

interface HistoryEntry {
  id: string
  language: Language
  created_at: string
}

function readHistory(): HistoryEntry[] {
  try {
    const value = JSON.parse(localStorage.getItem(historyStorageKey) ?? '[]') as unknown
    if (!Array.isArray(value)) return []
    return value.filter((item): item is HistoryEntry => (
      typeof item === 'object'
      && item !== null
      && 'id' in item
      && typeof item.id === 'string'
      && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(item.id)
      && 'language' in item
      && (item.language === 'python' || item.language === 'java')
      && 'created_at' in item
      && typeof item.created_at === 'string'
    )).slice(0, historyLimit)
  } catch {
    return []
  }
}

function AnalyzerApp() {
  const [language, setLanguage] = useState<Language>('python')
  const [problemKind, setProblemKind] = useState<ProblemKind>('function')
  const [statement, setStatement] = useState(
    'Given an integer array, return the sum of its values.',
  )
  const [entrypoint, setEntrypoint] = useState(starterEntrypoint.python)
  const [constraintsText, setConstraintsText] = useState(starterConstraints)
  const [functionSamplesText, setFunctionSamplesText] = useState(starterSamples)
  const [stdinSamplesText, setStdinSamplesText] = useState(starterStdinSamples)
  const [code, setCode] = useState(starterCode.python)
  const [referenceCode, setReferenceCode] = useState<Record<Language, string>>({ python: '', java: '' })
  const [independentReferenceCode, setIndependentReferenceCode] = useState<Record<Language, string>>({ python: '', java: '' })
  const [optimizationCode, setOptimizationCode] = useState<Record<Language, string>>({ python: '', java: '' })
  const [optimizationNotes, setOptimizationNotes] = useState('')
  const [benchmarksText, setBenchmarksText] = useState<Record<Language, string>>({ python: '[]', java: '[]' })
  const [generatedTests, setGeneratedTests] = useState(8)
  const [mutationTests, setMutationTests] = useState(0)
  const [history, setHistory] = useState<HistoryEntry[]>(readHistory)
  const [job, setJob] = useState<Job | null>(null)
  const [report, setReport] = useState<AnalysisReport | null>(null)
  const [proposals, setProposals] = useState<OptimizationProposal[]>([])
  const [proposalMessage, setProposalMessage] = useState<string | null>(null)
  const [proposalsBusy, setProposalsBusy] = useState(false)
  const [activeTab, setActiveTab] = useState<'evidence' | 'checks'>('evidence')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const eventSource = useRef<EventSource | null>(null)
  const rememberedCode = useRef({
    function: { ...starterCode },
    stdin_stdout: { ...starterStdinCode },
  })

  const samplesText = problemKind === 'function' ? functionSamplesText : stdinSamplesText
  const activeJobId = job?.id
  const activeJobStatus = job?.status

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
          if (updated.status === 'completed') setReport(await getReport(activeJobId))
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

  function changeLanguage(next: Language) {
    setLanguage(next)
    setEntrypoint(starterEntrypoint[next])
    setCode(rememberedCode.current[problemKind][next])
    setProposals([])
    setProposalMessage(null)
  }

  function updateCode(value: string) {
    setCode(value)
    rememberedCode.current[problemKind][language] = value
    setProposals([])
    setProposalMessage(null)
  }

  function changeProblemKind(next: ProblemKind) {
    rememberedCode.current[problemKind][language] = code
    setProblemKind(next)
    setCode(rememberedCode.current[next][language])
    setProposals([])
    setProposalMessage(null)
  }

  async function checkForOptimizationProposal() {
    setProposalsBusy(true)
    setError(null)
    setProposals([])
    setProposalMessage(null)
    try {
      const samples = JSON.parse(functionSamplesText) as Record<string, unknown>[]
      if (!Array.isArray(samples) || samples.length === 0) {
        throw new Error('Add at least one sample case before requesting a proposal.')
      }
      const result = await findOptimizationProposals({
        language,
        code,
        problem: {
          statement,
          interface: { kind: 'function', entrypoint },
          constraints: JSON.parse(constraintsText),
          samples: samples.map((sample) => ({ ...sample, kind: 'function' })),
        },
      })
      setProposals(result.proposals)
      setProposalMessage(result.message)
    } catch (reason) {
      setError(reason instanceof ApiError
        ? reason.message
        : reason instanceof Error
          ? reason.message
          : 'Could not inspect this source for supported patterns.')
    } finally {
      setProposalsBusy(false)
    }
  }

  function selectOptimizationProposal(proposal: OptimizationProposal) {
    setOptimizationCode((previous) => ({ ...previous, [language]: proposal.candidate_code }))
    setOptimizationNotes(proposal.summary)
    setProposalMessage('Candidate copied into the optimization panel. Run analysis to check it; this proposal has not been executed.')
  }

  async function runAnalysis() {
    setBusy(true)
    setError(null)
    setReport(null)
    try {
      const samples = JSON.parse(samplesText) as Record<string, unknown>[]
      if (!Array.isArray(samples) || samples.length === 0) {
        throw new Error('Add at least one sample case as a JSON array.')
      }
      const problem = problemKind === 'function'
        ? {
            statement,
            interface: { kind: 'function' as const, entrypoint },
            constraints: JSON.parse(constraintsText),
            samples: samples.map((sample) => ({ ...sample, kind: 'function' as const })),
          }
        : {
            statement,
            interface: { kind: 'stdin_stdout' as const },
            samples: samples.map((sample) => ({ ...sample, kind: 'stdin_stdout' as const })),
          }
      const request: Record<string, unknown> = { language, code, problem }
      let path: string
      if (problemKind === 'stdin_stdout') {
        path = '/v1/jobs/mode1/stdin-stdout'
      } else {
        const reference = referenceCode[language].trim()
        const independentReference = independentReferenceCode[language].trim()
        const optimization = optimizationCode[language].trim()
        if (optimizationNotes.trim() && !optimization) {
          throw new Error('Add an optimization candidate before adding notes.')
        }
        path = `/v1/jobs/mode1/${language}-function`
        request.reference_code = reference || null
        request.independent_reference_code = reference ? independentReference || null : null
        request.generated_tests = reference ? generatedTests : 0
        request.mutation_tests = reference ? mutationTests : 0
        request.optimization_code = optimization || null
        request.optimization_notes = optimizationNotes.trim() || null
        const benchmarks = JSON.parse(benchmarksText[language]) as unknown
        if (!Array.isArray(benchmarks)) {
          throw new Error('Complexity benchmarks must be a JSON array.')
        }
        if (benchmarks.length > 0) {
          const sizes = benchmarks.map((benchmark) => (
            typeof benchmark === 'object' && benchmark !== null && 'size' in benchmark
              ? (benchmark as { size: unknown }).size
              : null
          ))
          if (sizes.length < 4 || sizes.length > 6 || sizes.some((size) => !Number.isInteger(size))) {
            throw new Error('Provide four to six benchmarks with integer sizes, or leave the array empty.')
          }
          if (sizes.some((size, index) => index > 0 && Number(size) <= Number(sizes[index - 1]))) {
            throw new Error('Benchmark sizes must be unique and increase from first to last.')
          }
        }
        request.complexity_benchmarks = benchmarks
      }
      const created = await submitJob(path, request)
      setJob(created)
      setHistory((current) => [
        { id: created.id, language: created.language, created_at: created.created_at },
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
      if (selected.status === 'completed') setReport(await getReport(jobId))
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
                </button>
              ))}
          </div>
          <div className="rail-bottom"><div className="rail-section-label">RUNTIME</div><div className="runtime-state"><span className="runtime-pip" /> API checked on run</div></div>
        </aside>

        <section className="main-panel">
          <div className="page-heading">
            <div><div className="eyebrow">MODE 1 <span>/</span> DSA SOLUTION ANALYZER</div><h1>Code, with receipts.</h1><p>Run a candidate against your problem definition. Every result comes from the configured checks.</p></div>
            <div className="page-actions">{report && <button className="quiet-button" onClick={exportReport}>EXPORT REPORT JSON</button>}{canCancel && <button className="quiet-button" onClick={() => void stopJob()}>Cancel job</button>}{problemKind === 'function' && <button className="quiet-button" onClick={() => void checkForOptimizationProposal()} disabled={proposalsBusy || busy || isRunning}>{proposalsBusy ? 'CHECKING RULES' : 'CHECK FOR PROPOSAL'}</button>}<button className="run-button" onClick={() => void runAnalysis()} disabled={busy || isRunning}><span>{busy || isRunning ? '◌' : '▶'}</span>{busy ? 'SUBMITTING' : isRunning ? 'ANALYZING' : 'RUN ANALYSIS'}</button></div>
          </div>

          {error && <div className="error-banner" role="alert"><span>!</span>{error}<button onClick={() => setError(null)} aria-label="Dismiss error">×</button></div>}

          <div className="workbench">
            <section className="input-panel" aria-label="Problem and run settings">
              <div className="panel-heading"><span>01</span><h2>Problem</h2><span className="panel-meta">SPECIFICATION</span></div>
              <label className="field-label" htmlFor="problem-statement">STATEMENT</label>
              <textarea id="problem-statement" className="text-input statement-input" value={statement} onChange={(event) => setStatement(event.target.value)} rows={3} />
              <div className="field-row">
                <label className="field-block"><span className="field-label">LANGUAGE</span><select value={language} onChange={(event) => changeLanguage(event.target.value as Language)}><option value="python">Python</option><option value="java">Java</option></select></label>
                <label className="field-block"><span className="field-label">INTERFACE</span><select value={problemKind} onChange={(event) => changeProblemKind(event.target.value as ProblemKind)}><option value="function">Function</option><option value="stdin_stdout">stdin / stdout</option></select></label>
              </div>
              {problemKind === 'function' && <>
                <label className="field-block"><span className="field-label">ENTRYPOINT</span><input className="text-input mono-input" value={entrypoint} onChange={(event) => setEntrypoint(event.target.value)} /></label>
                <label className="field-block"><span className="field-label">CONSTRAINTS · JSON</span><textarea className="text-input json-input" value={constraintsText} onChange={(event) => setConstraintsText(event.target.value)} rows={4} spellCheck={false} /></label>
              </>}
              <label className="field-block"><span className="field-label">SAMPLES · JSON ARRAY</span><textarea className="text-input json-input samples-input" value={samplesText} onChange={(event) => problemKind === 'function' ? setFunctionSamplesText(event.target.value) : setStdinSamplesText(event.target.value)} rows={7} spellCheck={false} /></label>
              {problemKind === 'function' && <>
                <details className="reference-settings"><summary>REFERENCE CHECKS <span>OPTIONAL</span></summary><label className="field-block"><span className="field-label">REFERENCE IMPLEMENTATION</span><textarea className="text-input code-input compact-code" value={referenceCode[language]} onChange={(event) => setReferenceCode((previous) => ({ ...previous, [language]: event.target.value }))} rows={5} spellCheck={false} placeholder={language === 'python' ? 'def solve(values):\n    return sum(values)' : 'class Reference { /* implement solve */ }'} /></label><label className="field-block"><span className="field-label">INDEPENDENT REFERENCE · OPTIONAL</span><textarea className="text-input code-input compact-code" value={independentReferenceCode[language]} onChange={(event) => setIndependentReferenceCode((previous) => ({ ...previous, [language]: event.target.value }))} rows={5} spellCheck={false} disabled={!referenceCode[language].trim()} placeholder={language === 'python' ? 'def solve(values):\n    total = 0\n    for value in values:\n        total += value\n    return total' : 'class ReferenceIndependent { /* implement solve */ }'} /></label><p className="field-hint">Both user-supplied references must match the examples and each other before differential checks run. Agreement is corroboration, not proof.</p><label className="field-block generated-count"><span className="field-label">GENERATED CASES</span><input type="number" min={0} max={50} value={generatedTests} onChange={(event) => setGeneratedTests(Math.max(0, Math.min(50, Number(event.target.value))))} disabled={!referenceCode[language].trim()} /></label><label className="field-block generated-count"><span className="field-label">MUTATION TESTS</span><input type="number" min={0} max={20} value={mutationTests} onChange={(event) => setMutationTests(Math.max(0, Math.min(20, Number(event.target.value))))} disabled={!referenceCode[language].trim()} /></label><p className="field-hint">Mutants are generated from simple operators in the selected reference method. A score is low-confidence and only describes these finite checks.</p><p className="field-hint">Generated differential checks use the reference only after it passes the declared samples.</p></details>
                <details className="reference-settings optimization-settings"><summary>OPTIMIZATION CANDIDATE <span>OPTIONAL</span></summary><p className="field-hint">A candidate you provide is checked against declared outputs before Axioma reports its measurements. This does not generate or silently apply a rewrite.</p><label className="field-block"><span className="field-label">ALTERNATE SOURCE</span><textarea className="text-input code-input compact-code" value={optimizationCode[language]} onChange={(event) => setOptimizationCode((previous) => ({ ...previous, [language]: event.target.value }))} rows={7} spellCheck={false} placeholder={language === 'python' ? 'def solve(values):\n    return sum(values)' : 'class AxiomaOptimized {\n    public int solve(int[] values) {\n        // alternate implementation\n    }\n}'} /></label><label className="field-block"><span className="field-label">WHY THIS CHANGE? · OPTIONAL</span><textarea className="text-input" value={optimizationNotes} onChange={(event) => setOptimizationNotes(event.target.value)} rows={2} maxLength={2000} /></label><label className="field-block"><span className="field-label">BENCHMARK INPUTS · JSON ARRAY · 4–6 INCREASING SIZES</span><textarea className="text-input json-input" value={benchmarksText[language]} onChange={(event) => setBenchmarksText((previous) => ({ ...previous, [language]: event.target.value }))} rows={5} spellCheck={false} placeholder={'[{"size": 10, "args": [[1,2,3,4,5,6,7,8,9,10]]}, ...]'} /></label><p className="field-hint">Use inputs that match your function signature and declared constraints. Measurements run only after correctness checks pass and remain low-confidence evidence.</p></details>
              </>}
              <div className="input-note"><span>i</span><p>Submissions are sent to the local API. Code executes only when the worker and sandbox are available.</p></div>
            </section>

            <section className="editor-panel" aria-label="Candidate source code">
              <div className="panel-heading"><span>02</span><h2>Candidate</h2><span className="panel-meta">{language.toUpperCase()}</span></div>
              <label className="field-label" htmlFor="candidate-code">SOURCE · EDITABLE</label>
              <textarea id="candidate-code" className="text-input code-input source-editor" value={code} onChange={(event) => updateCode(event.target.value)} spellCheck={false} aria-label="Candidate source code" />
              <div className="editor-footer"><span><i className="editor-dot" /> UNSAVED SOURCE</span><span>UTF-8 <i>·</i> SPACES: 4</span></div>
              <div className="editor-callout"><span>↳</span><p>Change the starter solution, then run it against the samples. A green result only means those configured checks passed.</p></div>
              {proposalMessage && <div className="proposal-message" role="status">{proposalMessage}</div>}
              {proposals.map((proposal) => <article className="proposal-card" key={proposal.rule_id}><div className="proposal-top"><span className="evidence-type type-static">STATIC</span><span className="confidence confidence-low">LOW CONFIDENCE</span><span className="proposal-unverified">NOT RUN</span></div><h3>{proposal.title}</h3><p>{proposal.summary}</p><pre>{proposal.candidate_code}</pre><ul>{proposal.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul><button className="quiet-button" onClick={() => selectOptimizationProposal(proposal)}>USE AS OPTIMIZATION CANDIDATE</button></article>)}
            </section>

            <section className="results-panel" aria-label="Analysis results" aria-live="polite">
              <div className="panel-heading"><span>03</span><h2>Evidence</h2><span className="panel-meta">{report ? 'RESULT' : 'LIVE STATUS'}</span></div>
              <JobStatusView job={job} />
              {report ? <>
                <div className="summary-strip"><div><b>{report.tests.total}</b><span>CHECKS</span></div><div className="pass-value"><b>{report.tests.passed}</b><span>PASSED</span></div><div className="fail-value"><b>{report.tests.failed}</b><span>FAILED</span></div><div className="skip-value"><b>{report.tests.skipped}</b><span>SKIPPED</span></div></div>
                <div className="result-tabs" role="tablist" aria-label="Report sections"><button className={activeTab === 'evidence' ? 'active' : ''} role="tab" aria-selected={activeTab === 'evidence'} onClick={() => setActiveTab('evidence')}>CLAIMS <span>{report.claims.length}</span></button><button className={activeTab === 'checks' ? 'active' : ''} role="tab" aria-selected={activeTab === 'checks'} onClick={() => setActiveTab('checks')}>METHODS <span>{report.complexity ? 1 : 0}</span></button></div>
                <div className="result-content" role="tabpanel">{activeTab === 'evidence' ? <Claims claims={report.claims} /> : <Complexity result={report.complexity} />}</div>
                {report.verification_gates.length > 0 && <GateList gates={report.verification_gates} />}
                <div className="report-foot">RESULTS REFLECT THIS RUN'S CONFIGURED CHECKS</div>
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
  if (!result) return <div className="empty-claims">No complexity estimate was produced for this run.</div>
  return <article className="complexity-card"><div className="complexity-head"><div><span className="field-label">ESTIMATE</span><h3>{result.estimate}</h3></div><span className={`confidence confidence-${result.confidence}`}>{result.confidence} confidence</span></div><div className="method-line"><span>METHOD</span><code>{result.method}</code></div>{result.methods_disagree && <div className="disagree-note"><b>METHODS DISAGREE</b><p>The available estimates did not agree. Review the measurements before relying on this class.</p></div>}{result.explanation && <p className="complexity-explanation">{result.explanation}</p>}<details><summary>MEASUREMENT DETAILS</summary><pre>{JSON.stringify(result.details, null, 2)}</pre></details></article>
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
