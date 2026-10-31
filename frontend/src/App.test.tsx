// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import App, { Complexity, EmptyResults, EvidenceBadge, EvidenceReview, JobStatusView, ProblemMatchCard, TestCaseList } from './App'
import type { AnalysisReport, Job, ProblemMatch } from './types'

afterEach(() => {
  cleanup()
  window.history.replaceState({}, '', '/')
})

describe('analysis evidence states', () => {
  it('shows and scrolls line numbers alongside the editable code', () => {
    window.history.replaceState({}, '', '/analyzer')
    const { container } = render(<App />)
    const editor = screen.getByRole('textbox', { name: 'Candidate source code' })

    expect([...container.querySelectorAll('.line-number-gutter span')].map((line) => line.textContent)).toEqual(['1'])
    fireEvent.change(editor, { target: { value: 'first line\nsecond line\n' } })
    expect([...container.querySelectorAll('.line-number-gutter span')].map((line) => line.textContent)).toEqual(['1', '2', '3'])
    const gutter = container.querySelector('.line-number-gutter') as HTMLDivElement
    Object.defineProperty(editor, 'scrollTop', { configurable: true, value: 48, writable: true })
    fireEvent.scroll(editor)
    expect(gutter.scrollTop).toBe(48)
  })

  it('offers Gemma diagnostics only after an Axioma report exists', () => {
    window.history.replaceState({}, '', '/analyzer')
    render(<App />)

    expect(screen.queryByLabelText('Gemma 4 advisory')).toBeNull()
    expect(screen.queryByRole('button', { name: 'ASK GEMMA 4' })).toBeNull()
  })

  it('summarizes checks, saved input availability, code signals, and claim limits', () => {
    const report: AnalysisReport = {
      job_id: 'job-1',
      claims: [],
      complexity: {
        method: 'static_python_loop_depth',
        estimate: 'O(n)',
        confidence: 'low',
        methods_disagree: false,
        explanation: 'One scan.',
        details: {
          code_analysis: {
            signals: [{ kind: 'loop', label: 'Forward scan', line: 4 }],
            limitations: ['Called helpers are not inspected.'],
          },
        },
      },
      tests: { total: 1, passed: 1, failed: 0, skipped: 0 },
      test_cases: [{
        name: 'example', outcome: 'passed', origin: 'catalog_sample', duration_ms: 1,
        details: {},
        input_preview: { data: { args: [[1, 2]] }, sha256: 'a'.repeat(64), truncated: false },
      }],
      verification_gates: [],
    }

    render(<EvidenceReview report={report} />)

    expect(screen.getByText('1 case recorded')).toBeTruthy()
    expect(screen.getByText('1 / 1 inputs available')).toBeTruthy()
    expect(screen.getByText('Forward scan')).toBeTruthy()
    expect(screen.getByText('1 documented limitation · inspect estimate details')).toBeTruthy()
    expect(screen.getByText(/do not prove full edge-case coverage/)).toBeTruthy()
  })

  it('shows ambiguity and the candidate titles without selecting a problem pack', () => {
    const match: ProblemMatch = {
      recognized: false,
      match_state: 'ambiguous',
      candidate_titles: ['First Similar Problem', 'Second Similar Problem'],
      slug: null,
      title: null,
      topics: [],
      test_count: 0,
      test_source: null,
      problem: null,
    }

    render(<ProblemMatchCard matching={false} problemMatch={match} />)

    expect(screen.getByText('More than one problem may match')).toBeTruthy()
    expect(screen.getByText('First Similar Problem')).toBeTruthy()
    expect(screen.getByText('Second Similar Problem')).toBeTruthy()
  })

  it('previews the four evidence questions before the first run', () => {
    render(<EmptyResults job={null} />)

    expect(screen.getByText('Which checks ran?')).toBeTruthy()
    expect(screen.getByText('What inputs were covered?')).toBeTruthy()
    expect(screen.getByText('What code signals were detected?')).toBeTruthy()
    expect(screen.getByText('Where are the limits?')).toBeTruthy()
  })

  it('keeps no-match distinct from ambiguous matching', () => {
    const match: ProblemMatch = {
      recognized: false,
      match_state: 'not_found',
      candidate_titles: [],
      slug: null,
      title: null,
      topics: [],
      test_count: 0,
      test_source: null,
      problem: null,
    }

    render(<ProblemMatchCard matching={false} problemMatch={match} />)

    expect(screen.getByText('No supported problem match')).toBeTruthy()
    expect(screen.queryByText('More than one problem may match')).toBeNull()
  })

  it('shows failed checks with their origin and failure category', () => {
    render(<TestCaseList
      cases={[{
        name: 'example-1',
        outcome: 'failed',
        origin: 'catalog_sample',
        duration_ms: 4,
        details: { failure_kind: 'compile_error', stderr: 'syntax error', expected: 3, actual: 2 },
      }]}
      summary={{ total: 1, passed: 0, failed: 1, skipped: 0 }}
    />)

    expect(screen.getByText(/Imported sample.*Compiler error/)).toBeTruthy()
    expect(screen.getByText('EXPECTED')).toBeTruthy()
    expect(screen.getByText('OBSERVED')).toBeTruthy()
    expect(screen.getAllByText(/syntax error/).length).toBeGreaterThan(0)
  })

  it('shows a saved input preview and does not infer edge-case labels', () => {
    const { container } = render(<TestCaseList
      cases={[{
        name: 'example-1', outcome: 'passed', origin: 'catalog_sample', duration_ms: 4,
        details: {},
        input_preview: { data: { args: [[2, 7]], kwargs: {} }, sha256: 'b'.repeat(64), truncated: false },
      }]}
      summary={{ total: 1, passed: 1, failed: 0, skipped: 0 }}
    />)

    expect(screen.getByText('TEST INPUT')).toBeTruthy()
    expect(container.querySelector('.case-input-preview pre')?.textContent).toContain('"args"')
    expect(container.querySelector('.case-input-preview pre')?.textContent).toContain('2')
    expect(container.querySelector('.case-input-preview pre')?.textContent).toContain('7')
    expect(screen.getByText(/Snapshot SHA-256 b{16}/)).toBeTruthy()
  })

  it('groups failed cases first, orders names naturally, and keeps case details collapsed', () => {
    const { container } = render(<TestCaseList
      cases={[
        { name: 'dataset_case_10', outcome: 'passed', origin: 'catalog_sample', duration_ms: null, details: {} },
        { name: 'dataset_case_2', outcome: 'failed', origin: 'catalog_sample', duration_ms: null, details: { expected: 3, actual: 4 }, input_preview: { data: { args: [[1, 2]] }, sha256: 'c'.repeat(64), truncated: false } },
        { name: 'dataset_case_1', outcome: 'failed', origin: 'catalog_sample', duration_ms: null, details: { expected: 2, actual: 1 } },
        { name: 'dataset_case_3', outcome: 'skipped', origin: 'catalog_sample', duration_ms: null, details: {} },
      ]}
      summary={{ total: 4, passed: 1, failed: 2, skipped: 1 }}
    />)

    const groupHeadings = [...container.querySelectorAll('.test-case-group-heading h4')]
    expect(groupHeadings.map((heading) => heading.textContent)).toEqual([
      'FAILED CASES', 'PASSED CASES', 'SKIPPED CASES',
    ])
    const failedNames = [...container.querySelectorAll('.group-failed .test-case-summary b')]
    expect(failedNames.map((name) => name.textContent)).toEqual([
      'dataset_case_1', 'dataset_case_2',
    ])
    expect([...container.querySelectorAll('.group-failed details.test-case')].every((row) => !row.hasAttribute('open'))).toBe(true)
    expect(screen.queryByText(/No unambiguous saved input snapshot/)).toBeNull()
  })

  it('puts a runtime error and its recorded source location in the failed case', () => {
    const navigatedLocations: string[] = []
    render(<TestCaseList
      cases={[{
        name: 'runtime-error', outcome: 'failed', origin: 'catalog_sample', duration_ms: null,
        details: {
          failure_kind: 'runtime_error',
          error: 'IndexError: list index out of range',
          source_location: { file: 'submission.py', line: 8, function: 'solve' },
        },
      }]}
      summary={{ total: 1, passed: 0, failed: 1, skipped: 0 }}
      onGoToLocation={(location) => navigatedLocations.push(location)}
    />)

    expect(screen.getByText('IndexError: list index out of range')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Go to submission.py:8 in editor' })).toBeTruthy()
    fireEvent.click(screen.getByText('runtime-error'))
    fireEvent.click(screen.getByRole('button', { name: 'Go to submission.py:8 in editor' }))
    expect(navigatedLocations).toEqual(['submission.py:8'])
  })

  it('extracts the line from a Python syntax-error diagnostic', () => {
    render(<TestCaseList
      cases={[{
        name: 'compile-error', outcome: 'failed', origin: 'catalog_sample', duration_ms: null,
        details: {
          failure_kind: 'compile_error',
          error: 'SyntaxError: invalid syntax (submission.py, line 4)',
        },
      }]}
      summary={{ total: 1, passed: 0, failed: 1, skipped: 0 }}
    />)

    expect(screen.getByText('Compiler error')).toBeTruthy()
    expect(screen.getByText('submission.py:4')).toBeTruthy()
    expect(screen.getAllByText(/SyntaxError: invalid syntax/).length).toBeGreaterThan(0)
  })

  it('labels model claims without implying a model is currently configured', () => {
    render(<EvidenceBadge type="model" confidence="low" />)

    expect(screen.getByText('Model prediction')).toBeTruthy()
    expect(screen.getByText('low confidence')).toBeTruthy()
  })

  it('labels worker failure using the API error code', () => {
    const job: Job = {
      id: '7be9906d-a037-4c2f-861c-b5c124197bbf',
      mode: 'dsa_analysis',
      language: 'java',
      status: 'failed',
      created_at: '2026-10-29T12:00:00Z',
      updated_at: '2026-10-29T12:00:01Z',
      progress_message: 'The analysis worker could not run this submission',
      error_code: 'sandbox_unavailable',
    }

    render(<><JobStatusView job={job} /><EmptyResults job={job} /></>)

    expect(screen.getByText('WORKER FAILURE')).toBeTruthy()
    expect(screen.getByText('Failure category: Sandbox unavailable')).toBeTruthy()
    expect(screen.getByText(/API, worker, and sandbox are available/)).toBeTruthy()
  })

  it('separates static estimate, measured points, and unavailable auxiliary-space estimate', () => {
    const complexity: NonNullable<AnalysisReport['complexity']> = {
      method: 'static_python_loop_depth+dynamic_line_event_fit',
      estimate: 'O(n) (measured line-event fit: O(n))',
      confidence: 'low',
      methods_disagree: false,
      explanation: 'Static and line-event estimates agree.',
      details: {
        measurement_method: 'executed_source_line_events',
        static_estimate: 'O(n)',
        fit: 'O(n)',
        points: [
          { size: 10, line_events: 20, input_strategy: 'ascending' },
          { size: 20, line_events: 40, input_strategy: 'ascending' },
        ],
        space_measurement: { state: 'not_estimated', reason: 'Too few sizes.' },
      },
    }

    render(<Complexity result={complexity} />)

    expect(screen.getByText('STATIC ESTIMATE · HEURISTIC')).toBeTruthy()
    expect(screen.getByText('Empirical benchmark · not an asymptotic proof')).toBeTruthy()
    expect(screen.getByText('20 source-line events')).toBeTruthy()
    expect(screen.getByText('No auxiliary-space estimate was produced for this run.')).toBeTruthy()
  })

  it('does not present a legacy combined result as a separately stored static estimate', () => {
    const complexity: NonNullable<AnalysisReport['complexity']> = {
      method: 'static_ast_loop_depth+dynamic_line_event_fit',
      estimate: 'O(n) (measured line-event fit: O(n))',
      confidence: 'low',
      methods_disagree: false,
      explanation: null,
      details: {
        measurement_method: 'executed_source_line_events',
        fit: 'O(n)',
        points: [{ size: 10, line_events: 20 }],
      },
    }

    render(<Complexity result={complexity} />)

    expect(screen.getByText('Not stored separately for this saved run')).toBeTruthy()
    expect(screen.getByText(/observed growth fit: O\(n\)/)).toBeTruthy()
  })
})
