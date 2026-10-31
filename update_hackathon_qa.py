from docx import Document
from docx.shared import Pt
from pathlib import Path

path = Path.cwd() / 'Axioma_Hackathon_QA_Playbook.docx'
doc = Document(path)

def heading(text, level=1):
    doc.add_heading(text, level=level)

def para(text):
    doc.add_paragraph(text)

def bullets(items):
    for item in items:
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_after = Pt(2)
        p.add_run(item)

heading('Project approach and reasoning')
para('The team did not start by adding a large AI model or by trying to support every type of software repository. We started with a narrow, testable workflow: a coding problem, a Python or Java solution, a local problem pack, controlled execution, and a report that explains the evidence. This lets us validate the trust boundary and the evidence model before expanding the product.')
heading('The problems we faced', 2)
bullets([
    'Pass or fail was too shallow. A solution can pass a few examples and still fail on an edge case, use excessive memory, or have poor scalability.',
    'Executing submitted code is dangerous. Code must not run inside the API request process or on the host without a sandbox, timeouts, resource limits, and cleanup.',
    'Problem matching can be ambiguous. A wrong catalog match would make every later test result misleading, so low-confidence matches must be rejected.',
    'Generated tests need an oracle. An input generator can create useful stress cases, but without a trusted expected output it cannot prove semantic correctness.',
    'Complexity is difficult to infer automatically. Syntax patterns are incomplete, benchmarks are machine-dependent, and neither should be presented as mathematical proof.',
    'Optimization can change behavior. A faster-looking candidate must be checked against the same relevant cases before any improvement claim is made.',
    'Evaluation can become biased. If we tune on the same cases used to measure success, the result is no longer a fair final evaluation.',
    'The scope could expand too quickly. Repository analysis, ML, LLMs, multiple languages, hosted accounts, and public deployment are valuable directions, but each adds new reliability and security risks.'
])
heading('The logic behind our design', 2)
para('Our central logic is to separate facts, estimates, proposals, and unknowns. The system first records what happened, then explains what the signals may mean, and finally states what cannot be concluded. This is why the API keeps evidence types such as executed, static, statistical, model, and unverified separate, and why confidence is categorical rather than a fabricated percentage.')
bullets([
    'If a test actually ran, label it as executed and show its individual outcome.',
    'If a conclusion comes from code structure, label it as static and include the detected signals.',
    'If a conclusion comes from timing, line events, opcode counts, or mutation results, label it as statistical and disclose the measurement limits.',
    'If no reliable oracle or supported pattern exists, return unverified, unknown, or unsupported instead of guessing.',
    'If methods disagree, expose the disagreement rather than averaging it into a misleading score.',
    'If an optimization is proposed, preserve the original source, validate the candidate, and keep measured comparison separate from correctness evidence.'
])
heading('End-to-end analysis logic', 2)
bullets([
    'Input boundary: validate the problem definition, language, source size, interface, examples, constraints, and optional references.',
    'Matching: compare the problem statement with the local catalog and reject ambiguous or low-confidence matches.',
    'Preparation: derive only bounded, reproducible inputs that fit the declared constraints and record their provenance.',
    'Execution: queue the job and run the submission in a restricted Docker worker, outside the API process.',
    'Evidence collection: store compiler results, runtime outcomes, test records, static findings, measurements, and failures separately.',
    'Reconciliation: calculate test totals from individual records and preserve queued, running, completed, failed, timed-out, and cancelled states.',
    'Explanation: show the best-supported result, its method, confidence category, reasoning, and limitations.',
    'Evaluation: compare predictions against a frozen review set and report accuracy together with coverage and abstention.'
])
heading('Why we are building in stages', 2)
para('The direction is deliberately staged because trust is a dependency for every later feature. A repository repair assistant that produces a polished but unreliable patch is more dangerous than a smaller tool that clearly says what it knows. We therefore prioritize evaluation integrity and sandbox security before adding broad automation.')

heading('Direction of the project')
para('The project is moving through three connected stages. Each stage reuses the same evidence model instead of replacing the architecture.')
heading('Stage 1  Current Mode 1', 2)
bullets([
    'Focus: catalog-assisted analysis of Python and Java DSA solutions.',
    'Input: problem statement, language, source code, examples, constraints, and optional references or optimization candidate.',
    'Output: test evidence, job state, complexity estimate, detected signals, optional measurements, and visible limitations.',
    'Status: early-stage working implementation. The current analysis is rule-based and measurement-based, not trained ML or LLM powered.'
])
heading('Stage 2  Reliability milestone', 2)
bullets([
    'Freeze a fresh human-reviewed evaluation set before running the analyzer.',
    'Separate development cases from the final holdout to avoid tuning leakage.',
    'Report exact accuracy, coverage, selective accuracy, abstention rate, and per-pattern failure categories.',
    'Expand only the analysis patterns that show generalizable failures, and add regression tests for each fix.',
    'Harden and independently review the sandbox before any public execution claim.'
])
heading('Stage 3  Mode 2 repository review and verified repair', 2)
para('Mode 2 is the longer-term direction. Instead of receiving one isolated DSA solution, Axioma would receive a repository, branch, commit, or pull request and analyze the change in context. The goal is not to silently rewrite code. The goal is to find likely risks, explain them, propose a visible repair, and verify the proposal before a human accepts it.')
bullets([
    'Repository ingestion: identify supported languages, build files, changed files, tests, and dependency boundaries.',
    'Deterministic review: run static checks, type or compile checks, and repository-aware rules with file and line provenance.',
    'Risk ranking: prioritize findings by evidence, reproducibility, affected code path, and likely impact.',
    'Optional ML or LLM assistance: use a future model only for a defined task such as risk ranking or explanation, with labeled data, a baseline, versioning, and leakage-resistant evaluation.',
    'Patch proposal: generate a visible diff that preserves the original source and explains the reason for each change.',
    'Verification: compile the candidate, run regression tests, run relevant generated or property checks, and report passed, failed, skipped, or inconclusive gates.',
    'Human decision: the developer reviews and accepts or rejects the proposal. Axioma never commits or applies a change silently.'
])
heading('Mode 2 example flow', 2)
para('A developer opens a pull request that changes a graph traversal. Mode 2 identifies the changed method, notices that a visited-set guard was removed, runs static checks, and flags a possible repeated traversal. It proposes a diff that restores the guard. The candidate is compiled and run against existing regression tests plus bounded graph cases. If the evidence passes, the report says that the candidate passed those checks. It still does not claim a universal proof, and the developer remains in control of the merge.')
heading('What Mode 2 is not', 2)
bullets([
    'It is not a fully autonomous coding agent that changes repositories without review.',
    'It is not a guarantee that every defect will be found.',
    'It is not a reason to add an LLM before a concrete task and evaluation exist.',
    'It is not a public execution service until the sandbox, authentication, privacy, and operational controls are ready.'
])

heading('Our product principles')
bullets([
    'Evidence before confidence: every claim should point to what produced it.',
    'Abstention before invention: unsupported analysis should be visible.',
    'Human control: suggestions remain proposals and source changes remain visible.',
    'Security by boundary: untrusted code stays outside the API process and away from host secrets.',
    'Evaluation before expansion: new capabilities need a defined task, a fair split, a baseline, and measured limitations.',
    'Modular growth: language adapters, analysis methods, and future model components should be replaceable without breaking the job and report contracts.'
])

heading('Strong closing response for judges')
para('We are building Axioma in the direction of verified code intelligence, but we are starting with a focused and honest foundation. Mode 1 proves the workflow: match a problem, execute safely, collect evidence, estimate complexity, and explain limitations. Our next step is to strengthen held-out evaluation and sandbox security. Mode 2 then extends the same evidence discipline to repositories, risk ranking, visible repair proposals, and regression verification. The direction is ambitious, but every expansion has to earn trust through measurable evidence.')

doc.save(path)
print(f'Updated {path}')
