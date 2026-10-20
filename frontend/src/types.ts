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
  verification_gates: {
    order: number
    name: string
    state: 'passed' | 'failed' | 'not_run'
    evidence_claim_ids: string[]
  }[]
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

export interface JobEvent {
  id: number
  job_id: string
  status: JobStatus
  message: string
  created_at: string
}
