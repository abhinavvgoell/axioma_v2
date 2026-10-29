export type Language = 'python' | 'java'
export type ProblemKind = 'function' | 'stdin_stdout'
export type JobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface Job {
  id: string
  mode: 'dsa_analysis' | 'repository_review'
  language: Language
  status: JobStatus
  created_at: string
  updated_at: string
  progress_message: string | null
  error_code: string | null
}

export interface EvidenceClaim {
  id: string
  type: 'executed' | 'static' | 'statistical' | 'model' | 'unverified'
  confidence: 'high' | 'medium' | 'low'
  summary: string
  provenance: {
    tool: string | null
    tool_version: string | null
    input_hash: string | null
    observed_at: string | null
    details: Record<string, unknown>
  }
  artifact_ids: string[]
}

export interface ComplexityResult {
  method: string
  estimate: string
  confidence: 'high' | 'medium' | 'low'
  methods_disagree: boolean
  explanation: string | null
  details: Record<string, unknown>
}

export interface AnalysisReport {
  job_id: string
  claims: EvidenceClaim[]
  complexity: ComplexityResult | null
  tests: { total: number; passed: number; failed: number; skipped: number }
  test_cases: TestCaseResult[]
  verification_gates: {
    order: number
    name: string
    state: 'passed' | 'failed' | 'not_run'
    evidence_claim_ids: string[]
  }[]
}

export interface TestCaseResult {
  name: string
  outcome: 'passed' | 'failed' | 'skipped'
  origin: 'catalog_sample' | 'generated_differential' | 'reference_validation' | 'property_check' | 'program_execution' | 'unknown'
  duration_ms: number | null
  details: Record<string, unknown>
}

export interface OptimizationProposal {
  rule_id: string
  title: string
  summary: string
  evidence_type: 'static'
  confidence: 'low'
  candidate_code: string
  limitations: string[]
}

export interface OptimizationProposalResponse {
  proposals: OptimizationProposal[]
  message: string
}

export interface ProblemMatch {
  recognized: boolean
  match_state: 'matched' | 'not_found' | 'ambiguous'
  candidate_titles: string[]
  slug: string | null
  title: string | null
  topics: string[]
  test_count: number
  test_source: string | null
  problem: Record<string, unknown> | null
}

export interface JobEvent {
  id: number
  job_id: string
  status: JobStatus
  message: string
  created_at: string
}
