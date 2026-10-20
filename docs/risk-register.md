# Risk register

Updated: 2026-10-20

| Risk | Likelihood | Impact | Mitigation | Status |
|---|---|---|---|---|
| Full brief exceeds the available 96 hours | High | High | Finish and evaluate Mode 1 first; keep Mode 2 and integrations behind later gates | Active |
| Docker is not installed in the current development environment | High | High | Worker and sandbox are implemented; install Docker Desktop before verifying container execution or running submissions | Active |
| Free hosting cannot safely support a public arbitrary-code sandbox | High | High | Keep execution local; use precomputed reports in any public demo unless a suitable isolated host is available | Active |
| Defects4J and BugsInPy setup, licensing, and leakage constraints reduce time for ML | Medium | Medium | Verify setup and licenses before committing to Track A; make ML a gated phase | Open |
| Mode 1 evaluation has no independently curated gold set yet | High | High | Keep scoring tools ready, but report no accuracy or detection rates until at least 50 reviewed solutions and known-correct controls/mutants are labeled | Active |
| Frontend visual designs arrive after the API contract is established | Medium | Medium | Keep a documented, versioned API contract and use a minimal placeholder UI until designs arrive | Managed |
| Generated boundary and adversarial inputs have no correctness oracle by themselves | High | High | Label generated strategies, revalidate every candidate against declared constraints, keep candidates separate from pass/fail claims, and run differential checks only against a user reference that first matches the declared samples | Managed |
| User-supplied reference may be wrong even when it matches samples or exhaustive checks | High | High | Label it as user supplied, compare only as differential evidence, and require an independently reviewed or second implementation before calling an oracle trusted | Active |
| Mutation score depends on a small set of generated mutants and an unproven reference | High | Medium | Report per-mutant outcomes and counts, exclude invalid/not-run mutants from the score denominator, and label the claim low confidence | Managed |
| Constraint-scale estimates may miss interacting input dimensions and constants | Medium | Medium | Use only declared collection maxima, state the one-dimension assumption, and label the output a rough low-confidence scale rather than a runtime prediction | Managed |
| Python line-event comparisons may not reflect wall-clock performance | Medium | Medium | Report raw per-size counts with low confidence, measure only equivalent variants, and avoid claiming speedup or asymptotic improvement | Managed |
| Python opcode counts may be confused with CPU instructions or complete work | Medium | Medium | Name them as CPython opcode dispatch counts, report raw counts separately, document omitted helpers/native code, and disclose that submitted code can disable tracing | Managed |
| Java microbenchmarks may be dominated by reflection, JVM warmup, or host scheduling noise | Medium | Medium | Warm both variants, use repeated trials and medians, report raw nanoseconds and low confidence, and restrict claims to the supplied inputs | Managed |
| User-supplied property predicates may encode an incorrect assumption | Medium | High | Require true results on declared examples before generated checks, keep claims low confidence, and show the predicate source and finite input outcomes | Managed |

