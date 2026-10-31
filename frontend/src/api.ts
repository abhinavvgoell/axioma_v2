import type { AnalysisReport, GemmaReviewResponse, Job, Language, OptimizationProposalResponse, ProblemMatch } from './types'

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  const body = await response.json().catch(() => null) as unknown
  if (!response.ok) {
    const detail = typeof body === 'object' && body !== null && 'detail' in body
      ? (body as { detail: unknown }).detail
      : null
    const message = typeof detail === 'string'
      ? detail
      : detail
        ? JSON.stringify(detail)
        : `Request failed with HTTP ${response.status}.`
    throw new ApiError(message, response.status)
  }
  return body as T
}

export function submitJob(path: string, input: Record<string, unknown>): Promise<Job> {
  return request<Job>(path, { method: 'POST', body: JSON.stringify(input) })
}

export function getJob(jobId: string): Promise<Job> {
  return request<Job>(`/v1/jobs/${encodeURIComponent(jobId)}`)
}

export function getReport(jobId: string): Promise<AnalysisReport> {
  return request<AnalysisReport>(`/v1/jobs/${encodeURIComponent(jobId)}/result`)
}

export function cancelJob(jobId: string): Promise<Job> {
  return request<Job>(`/v1/jobs/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' })
}

export function findOptimizationProposals(input: {
  language: Language
  code: string
  problem: Record<string, unknown>
}): Promise<OptimizationProposalResponse> {
  return request<OptimizationProposalResponse>('/v1/optimization-proposals', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function requestGemmaReview(input: {
  job_id: string
  language: Language
  code: string
  problem_statement: string
}): Promise<GemmaReviewResponse> {
  return request<GemmaReviewResponse>('/v1/gemma-review', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function matchProblem(statement: string): Promise<ProblemMatch> {
  return request<ProblemMatch>('/v1/problem-specs/match', {
    method: 'POST',
    body: JSON.stringify({ statement }),
  })
}

export function generateComplexityBenchmarks(input: {
  problem: Record<string, unknown>
  size_path: string
  sizes: number[]
  pattern: 'ascending' | 'repeated_characters'
  seed: number
}): Promise<{ benchmarks: { size: number; args: unknown[]; kwargs: Record<string, unknown>; strategy: string }[] }> {
  return request('/v1/problem-specs/generate-complexity-benchmarks', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}
