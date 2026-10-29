// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { Complexity, EmptyResults, EvidenceBadge, JobStatusView, ProblemMatchCard, TestCaseList } from './App'
import type { AnalysisReport, Job, ProblemMatch } from './types'

afterEach(cleanup)

describe('analysis evidence states', () => {
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

    expect(screen.getByText(/Imported sample.*Compiler error.*4 ms/)).toBeTruthy()
    expect(screen.getByText('EXPECTED')).toBeTruthy()
    expect(screen.getByText('OBSERVED')).toBeTruthy()
    expect(screen.getByText(/syntax error/)).toBeTruthy()
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
