from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

OUT = Path.cwd() / 'output' / 'pdf' / 'Axioma_Concept_and_Architecture_Rationale.pdf'
OUT.parent.mkdir(parents=True, exist_ok=True)

NAVY = colors.HexColor('#102A43')
BLUE = colors.HexColor('#2F80ED')
PURPLE = colors.HexColor('#6C63FF')
GREEN = colors.HexColor('#2D9D78')
ORANGE = colors.HexColor('#D97706')
INK = colors.HexColor('#243B53')
MUTED = colors.HexColor('#52606D')
PALE = colors.HexColor('#F0F4F8')
PALE_BLUE = colors.HexColor('#EAF2FF')
LINE = colors.HexColor('#CBD5E1')

styles = getSampleStyleSheet()
styles.add(ParagraphStyle('CoverTitle', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=26, leading=32, textColor=NAVY, alignment=TA_CENTER, spaceAfter=10))
styles.add(ParagraphStyle('CoverSub', parent=styles['Normal'], fontName='Helvetica', fontSize=12, leading=18, textColor=MUTED, alignment=TA_CENTER, spaceAfter=6))
styles.add(ParagraphStyle('H1A', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, leading=23, textColor=NAVY, spaceBefore=8, spaceAfter=8, keepWithNext=True))
styles.add(ParagraphStyle('H2A', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=12.5, leading=16, textColor=BLUE, spaceBefore=8, spaceAfter=4, keepWithNext=True))
styles.add(ParagraphStyle('BodyA', parent=styles['BodyText'], fontName='Helvetica', fontSize=9.7, leading=14, textColor=INK, spaceAfter=6))
styles.add(ParagraphStyle('SmallA', parent=styles['BodyText'], fontName='Helvetica', fontSize=8.3, leading=11, textColor=MUTED, spaceAfter=4))
styles.add(ParagraphStyle('BulletA', parent=styles['BodyText'], fontName='Helvetica', fontSize=9.4, leading=13, leftIndent=14, firstLineIndent=-8, textColor=INK, spaceAfter=3))
styles.add(ParagraphStyle('CalloutA', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=10.5, leading=15, textColor=NAVY, backColor=PALE_BLUE, borderColor=BLUE, borderWidth=0.7, borderPadding=8, spaceBefore=6, spaceAfter=8))
styles.add(ParagraphStyle('TableHeadA', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=8.5, leading=11, textColor=colors.white))
styles.add(ParagraphStyle('TableA', parent=styles['BodyText'], fontName='Helvetica', fontSize=8.2, leading=10.5, textColor=INK))

def P(text, style='BodyA'):
    return Paragraph(text, styles[style])

def bullet(text):
    return P('- ' + text, 'BulletA')

def table(headers, rows, widths):
    data = [[P(h, 'TableHeadA') for h in headers]]
    for row in rows:
        data.append([P(str(cell), 'TableA') for cell in row])
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1, hAlign='LEFT')
    commands = [
        ('BACKGROUND', (0,0), (-1,0), NAVY),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.35, LINE),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]
    for i in range(1, len(data)):
        if i % 2 == 1: commands.append(('BACKGROUND', (0,i), (-1,i), PALE))
    t.setStyle(TableStyle(commands))
    return t

def header_footer(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setStrokeColor(LINE); canvas.setLineWidth(0.5)
    canvas.line(18*mm, 14*mm, w-18*mm, 14*mm)
    canvas.setFont('Helvetica', 7.5); canvas.setFillColor(MUTED)
    canvas.drawString(18*mm, 9*mm, 'Axioma - Concept and Architecture Rationale')
    canvas.drawRightString(w-18*mm, 9*mm, f'{doc.page}')
    canvas.restoreState()

story = []
story += [Spacer(1, 28*mm), P('Axioma', 'CoverTitle'), P('Concept and Architecture Rationale', 'CoverTitle'), P('What we used, where we used it, why we chose it, and what we are deliberately not using yet', 'CoverSub'), Spacer(1, 12*mm), P('Hackathon reference document', 'CoverSub'), P('Current scope: Mode 1 for Python and Java DSA analysis | Future direction: Mode 2 repository review and verified repair', 'CoverSub'), PageBreak()]

story += [P('1. Executive summary', 'H1A'), P('Axioma is an evidence-first code intelligence platform. It accepts a coding problem and a Python or Java solution, matches the problem to a compatible local catalog pack, executes the solution inside a restricted Docker worker, checks available examples and bounded generated cases, estimates complexity using visible signals, and returns a report that explains what happened and how strong the evidence is.', 'BodyA'), P('The project is intentionally in an early development stage. Mode 1 is working around deterministic rules, language-specific heuristics, measurements, and structured evidence. There is no trained ML model or LLM in the current workflow. The larger product direction is Mode 2: repository-level review, risk ranking, visible patch proposals, and regression verification under human control.', 'BodyA'), P('Core product promise: show what was checked, how it was checked, what the signals suggest, and what remains uncertain.', 'CalloutA'), P('This document is designed to answer the question judges often ask: why did the team choose this concept or technology instead of another one?', 'BodyA'), PageBreak()]

story += [P('2. Product problem and design response', 'H1A'), table(['Problem we faced', 'Design response', 'Why this response'], [
    ('Pass or fail is too shallow', 'Return individual evidence claims and limitations', 'A user can inspect coverage instead of trusting a single verdict.'),
    ('Submitted code is untrusted', 'Execute outside the API process in a restricted worker', 'A crash, timeout, or exploit attempt should not take down the request process.'),
    ('Catalog matching can be wrong', 'Reject ambiguous or low-confidence matches', 'A wrong match would invalidate all later test results.'),
    ('Generated inputs may lack an oracle', 'Label provenance and distinguish robustness from correctness proof', 'An input without a trusted expected output cannot prove semantics.'),
    ('Complexity signals are incomplete', 'Expose method, estimate, confidence, and disagreement', 'The tool can abstain or qualify rather than invent certainty.'),
    ('Optimizations can change behavior', 'Validate candidates before measuring them', 'A faster candidate is useful only if it preserves the tested behavior.'),
    ('Evaluation can leak', 'Freeze fresh reviewed cases before scoring', 'Tuning and final evaluation must remain separate.'),
], [47, 55, 55]), Spacer(1, 4), P('Our reasoning is to narrow the first product boundary until it is testable, then expand only when new evidence supports the expansion.', 'CalloutA'), PageBreak()]

story += [P('3. Architecture and technology choices', 'H1A'), P('The architecture is a modular monolith with a separate worker. This keeps local development understandable while preserving a clean boundary between request coordination and untrusted execution.', 'BodyA'), table(['Layer', 'Chosen technology', 'Where it is used', 'Why this choice'], [
    ('Frontend', 'React 19 + TypeScript + Vite', 'Submission form, job stream, report UI', 'Typed components and fast iteration without introducing a heavier frontend framework.'),
    ('API', 'Python + FastAPI + Pydantic', 'Validation, routes, job creation, report contracts', 'Python matches the analysis domain; FastAPI and Pydantic give explicit request and response contracts.'),
    ('Persistence', 'SQLAlchemy + Alembic', 'Jobs, events, tests, reports, migrations', 'Keeps schema changes explicit and supports SQLite locally and PostgreSQL when needed.'),
    ('Database', 'SQLite locally; PostgreSQL supported', 'Queue state and durable reports', 'SQLite reduces local setup; PostgreSQL provides a stronger shared development path.'),
    ('Queue', 'Database-backed worker queue', 'Queued, running, recovery, cancellation', 'Avoids a second queue service before scale requires it while still supporting durable state and leases.'),
    ('Live updates', 'Server-Sent Events', 'Browser receives job status changes', 'The server owns state and the browser mainly needs one-way updates with reconnect support.'),
    ('Execution', 'Docker Linux containers', 'Python and Java sandbox', 'Separates code execution from the API process and enables resource and network restrictions.'),
    ('Quality', 'Pytest, Ruff, Vitest, Oxlint', 'Services, evaluator, frontend', 'Covers behavior, linting, and the typed UI without adding unnecessary dependencies.'),
], [24, 38, 50, 45]), PageBreak()]

story += [P('4. Why we are not training or calling a model in Mode 1', 'H1A'), P('Current truth: Mode 1 does not use a trained ML model or an LLM. Its outputs come from catalog matching, deterministic input generation, language-specific static heuristics, bounded measurements, and rule-based optimization proposals.', 'CalloutA'), P('Why not train a model yet?', 'H2A'), bullet('The project does not yet have a sufficiently large, reviewed, task-specific dataset for the questions we want to answer.'), bullet('A model would need a clear target such as complexity class, defect risk, or explanation quality. “Use AI” is not a task definition.'), bullet('The evaluation must prevent leakage by splitting by solution, repository, problem family, or time where appropriate.'), bullet('A baseline is required. If a simple rule or static tool performs as well, a model may not add enough value to justify its cost and opacity.'), bullet('Model versioning, calibration, failure analysis, privacy handling, and reproducibility would add responsibilities before the current evidence gate is complete.'), P('Why use deterministic analysis first?', 'H2A'), bullet('It is inspectable: the report can name the detected loop, recursion, sort, collection operation, or recognized shape.'), bullet('It is reproducible: the same code, inputs, runtime, and method can produce the same class of evidence.'), bullet('It makes abstention practical: unsupported patterns can return unknown instead of a confident guess.'), bullet('It creates a baseline and evaluation harness for any future model to beat.'), P('This is not an anti-ML position. It is a sequencing decision: first define the task and evidence, then add a model only where it produces measured value.', 'CalloutA'), PageBreak()]

story += [P('5. Future model plan: which model, for what, and why', 'H1A'), P('If future evidence shows that a model would help, the team should choose the model by task, data, latency, privacy, and explainability requirements. The model should not replace executed evidence or silently change code.', 'BodyA'), table(['Possible task', 'Candidate approach', 'Why this approach', 'Why not the alternative'], [
    ('Complexity classification', 'Start with rules and structured features; evaluate a small classifier only if coverage gaps remain', 'Structured features are easier to audit and compare with a baseline.', 'A general LLM may produce fluent but unsupported complexity explanations and can be hard to calibrate.'),
    ('Defect-risk ranking in Mode 2', 'A supervised ranking model trained on reviewed repository changes', 'Ranking can prioritize human attention without claiming that the top item is definitely a defect.', 'A generative model alone does not provide a reliable ranking objective or evaluation denominator.'),
    ('Patch explanation', 'Optional LLM or code model constrained to explain an existing diff', 'Explanation is a bounded assistance task that can cite the diff and checks.', 'Using a model to invent a patch before static and regression checks would increase risk.'),
    ('Patch generation', 'Optional code model behind a visible diff and strict verification gates', 'The candidate remains a proposal and is judged by compilation and tests.', 'Autonomous modification or automatic commit would violate human-control and safety goals.'),
    ('Natural-language report summary', 'Small optional language model with no authority over evidence fields', 'It can improve readability while preserving structured facts as the source of truth.', 'A model-generated score or confidence number could confuse interpretation with evidence.'),
], [34, 45, 48, 48]), P('Selection rule: use the simplest method that meets the measured task requirement. The structured report remains authoritative even when a model is added.', 'CalloutA'), PageBreak()]

story += [P('6. Execution, sandbox, and security concepts', 'H1A'), P('The security design follows a boundary-first approach because submitted source, filenames, problem text, test output, and suggestions are untrusted inputs.', 'BodyA'), table(['Concept', 'What we use', 'Why it matters', 'Current limitation'], [
    ('Process isolation', 'Run code in a worker container, not inside FastAPI', 'Keeps compilation and runtime failures away from the request process.', 'Containers share the host kernel.'),
    ('Network isolation', 'Disable outbound network by default', 'Prevents submitted code from reaching internal services, metadata endpoints, or external systems.', 'Public deployment still needs defense-in-depth review.'),
    ('Least privilege', 'Non-root process, read-only root, narrow mounts', 'Reduces what code can modify or access.', 'Misconfiguration can weaken the boundary.'),
    ('Resource limits', 'Time, CPU, memory, process, output, temporary-disk, and wall-clock limits', 'Prevents infinite loops, forks, memory exhaustion, and output floods.', 'Limits need continuous testing across runtimes.'),
    ('Cancellation and cleanup', 'Terminate process trees and clean temporary artifacts', 'Avoids orphaned work and leftover source or output.', 'Worker restart and cancellation remain important operational test cases.'),
    ('Privacy', 'No external AI service in current Mode 1; local reports and browser-local history', 'Reduces source-code exposure during the early stage.', 'Authentication, hosted retention, and account deletion are not built yet.'),
], [32, 48, 55, 45]), P('The honest deployment statement is: suitable for local development and demonstration, not yet a public code execution service.', 'CalloutA'), PageBreak()]

story += [P('7. Testing, oracles, and evidence semantics', 'H1A'), P('Axioma treats a test passing as evidence for that test, not as a universal proof. The report preserves the source and strength of each claim.', 'BodyA'), table(['Evidence type', 'Example', 'What it supports', 'What it does not support'], [
    ('Executed', 'Imported sample or sandbox run', 'The submission produced the expected result for that configured case.', 'All possible inputs are correct.'),
    ('Static', 'Loop depth, recursion, sort, binary-search signal', 'A visible code pattern suggests a possible complexity class.', 'The runtime cost of every helper or data structure.'),
    ('Statistical', 'Timing, Python line or opcode events, mutation results', 'An observed trend or test-quality signal for the measured sample.', 'A mathematical asymptotic proof or a universal reliability guarantee.'),
    ('Model', 'Future reviewed model output', 'Only the defined model task under its evaluation conditions.', 'Authority over executed evidence or a reason to hide uncertainty.'),
    ('Unverified', 'Missing oracle, unsupported pattern, ambiguous match', 'A clear statement that the workflow could not support a conclusion.', 'A reason to invent a score.'),
], [29, 45, 55, 50]), P('Oracle logic: a generated input without an expected-output oracle can reveal crashes, timeouts, or disagreement, but it cannot independently prove semantic correctness. References and properties must also be treated as evidence with provenance, not unquestionable truth.', 'CalloutA'), PageBreak()]

story += [P('8. Complexity and benchmarking concepts', 'H1A'), P('Complexity is handled as a layered estimate because static code signals and empirical measurements answer different questions.', 'BodyA'), table(['Signal', 'Used for', 'Why chosen', 'Important limitation'], [
    ('Static AST or token analysis', 'Recognize loop nesting, recursion, sorting, collections, and selected algorithm shapes', 'Fast, inspectable, and reproducible.', 'Does not expand arbitrary helper costs or prove behavior for every input.'),
    ('Python line events', 'Count traced source-line execution in selected function frames', 'Provides a repeatable work proxy for supported Python runs.', 'Not CPU instructions; tracing can be disabled and native work may be omitted.'),
    ('Python opcode events', 'Count interpreter bytecode dispatches', 'More fine-grained than source lines for Python-level work.', 'Not total program work or hardware instructions.'),
    ('Java JVM timing', 'Observe warmed reflective wall-time growth', 'Provides a runtime signal for Java at declared sizes.', 'Includes JVM and reflection overhead and depends on host conditions.'),
    ('Space measurements', 'Estimate traced Python allocation or Java heap-pool increases', 'Adds a separate memory signal when positive observations exist.', 'Not process RSS; native or off-heap allocation can be missing.'),
], [33, 49, 50, 47]), P('Benchmarks are measurements, not proof of asymptotic complexity. The report must keep the selected sizes, input family, runtime, warm-up policy, repetitions, raw observations, and uncertainty visible.', 'CalloutA'), PageBreak()]

story += [P('9. Optimization logic', 'H1A'), P('Optimization is intentionally narrow and rule-based in Mode 1. The product does not silently rewrite user code.', 'BodyA'), table(['Step', 'Logic', 'Reason'], [
    ('Detect', 'Recognize a supported pattern such as a nested Two Sum search.', 'Avoid proposing changes for arbitrary code where the rule is not reliable.'),
    ('Propose', 'Return a candidate source and explanation while keeping the original visible.', 'The user remains in control and can inspect the change.'),
    ('Validate', 'Run the candidate against the same relevant samples and generated cases.', 'A performance idea is not useful if behavior changes.'),
    ('Measure', 'Optionally compare observed signals at the same benchmark sizes.', 'A fair comparison needs the same input family and environment.'),
    ('Report', 'Separate equivalence counts, measurements, and limitations.', 'No improvement claim should be inferred from a single noisy run.'),
], [30, 83, 66]), P('If evidence is inconclusive, the correct output is “no measured improvement” or “not enough evidence,” not a fabricated percentage.', 'CalloutA'), PageBreak()]

story += [P('10. Mode 1 to Mode 2 direction', 'H1A'), table(['Stage', 'Scope', 'Why this order'], [
    ('Mode 1 current', 'Catalog-assisted Python and Java DSA analysis', 'Creates a controlled workflow for matching, sandboxing, testing, and evidence.'),
    ('Reliability milestone', 'Fresh reviewed holdout, coverage analysis, failure categories, sandbox review', 'Builds the evidence needed before making broader accuracy or deployment claims.'),
    ('Mode 2 future', 'Repository review, risk ranking, visible repair proposals, regression verification', 'Extends the same evidence discipline to real code changes without silent mutation.'),
], [32, 75, 72]), P('Mode 2 workflow', 'H2A'), bullet('Ingest a repository, branch, commit, or pull request and identify supported build context.'), bullet('Run deterministic static checks, type or compile checks, and repository-aware rules with file and line provenance.'), bullet('Rank risks by evidence, reproducibility, affected path, and likely impact.'), bullet('Create a visible patch proposal or diff, never a hidden edit.'), bullet('Compile and run regression, generated, or property checks against the candidate.'), bullet('Report passed, failed, skipped, or inconclusive verification gates.'), bullet('Let the developer accept or reject the proposal.'), P('Mode 2 is not an autonomous agent that silently changes repositories, and it is not a guarantee that every defect will be found. It is a controlled proposal-and-verification workflow.', 'CalloutA'), PageBreak()]

story += [P('11. What we will say about future ML or LLM use', 'H1A'), P('The team can say: “Mode 1 does not use a trained ML model or an LLM. We intentionally built a deterministic baseline first so we can inspect evidence, measure failure modes, and define the tasks where a model would add real value.”', 'CalloutA'), P('If a future model is introduced, the project should document:', 'H2A'), bullet('The exact task and output field the model owns.'), bullet('Data provenance, labeling process, and privacy constraints.'), bullet('A baseline without the model.'), bullet('A leakage-resistant split and frozen evaluation manifest.'), bullet('Coverage, conditional accuracy, calibration, abstention, and failure categories.'), bullet('Model version, prompt or feature version, runtime, and rollback behavior.'), bullet('What the model is not allowed to override, especially executed test evidence and security gates.'), P('This keeps the product honest: future AI is a measured component inside an evidence system, not a replacement for evidence.', 'BodyA'), PageBreak()]

story += [P('12. Decision summary for judges', 'H1A'), table(['Question', 'Answer'], [
    ('Why no model now?', 'No task-specific reviewed dataset, baseline, and fair evaluation are complete yet. Deterministic analysis is the correct first baseline.'),
    ('Why Docker?', 'Submitted code is untrusted and must execute outside the API process with resource and network controls.'),
    ('Why SQLite and PostgreSQL?', 'SQLite keeps local development simple; PostgreSQL supports a stronger shared deployment path.'),
    ('Why a database queue?', 'It gives durable job state and recovery without adding a second infrastructure service too early.'),
    ('Why SSE?', 'The browser needs one-way, reconnectable job updates and the server owns the state.'),
    ('Why not claim proof?', 'Examples, generated tests, heuristics, and benchmarks each support limited conclusions.'),
    ('Why Mode 2 later?', 'Repository review and repair need a stronger evaluation and security foundation than the early Mode 1 scope.'),
], [43, 136]), P('Recommended closing statement', 'H2A'), P('Axioma is an early-stage but working foundation for evidence-based code intelligence. We start with a focused DSA workflow because it lets us validate the trust boundary and evidence model. We then move toward Mode 2 repository review and verified repair, but only with visible proposals, regression checks, human control, and measured limits. The project is ambitious in direction and conservative in claims.', 'CalloutA'), P('Repository references used for this rationale: README.md, docs/api-contract.md, docs/threat-model-v1.md, docs/risk-register.md, docs/release-candidate-v1.md, docs/specifications/Axioma_PRD_v1.1.docx, docs/specifications/Axioma_TRD_v1.1.docx, and the current API, worker, frontend, and evaluator code.', 'SmallA')]

story += [P('13. Latest implementation updates', 'H1A'), P('The current checkout now includes an optional model-assisted learning layer and stronger provenance for evidence. These features extend Mode 1 without replacing its deterministic core.', 'BodyA'), table(['New capability', 'What it does', 'Important boundary'], [
    ('Optional Gemma 4 advisory', 'After a completed run, the user can ask Google\'s hosted Gemma 4 model for a short approach explanation and one learning suggestion.', 'Low-confidence model evidence only. It cannot execute code, alter test totals, alter complexity, or edit source.'),
    ('Evidence review surface', 'The UI summarizes recorded checks, saved inputs, detected code signals, and documented claim limits.', 'It reports available evidence; it does not infer complete edge-case coverage.'),
    ('Input previews and hashes', 'Test cases can show a bounded preview and SHA-256 hash of the saved input snapshot.', 'The preview is bounded; the hash identifies the full saved snapshot.'),
    ('Benchmark replay', 'Completed jobs with matching persisted snapshots can rerun the exact benchmark inputs.', 'Inputs are replayed exactly; elapsed timings can differ across environments.'),
    ('Problem-pack identity', 'Reports retain matched slug, title, and source identity.', 'Later review stays tied to the saved analysis rather than a newly edited problem.'),
    ('Open-source scope', 'Application code is documented under MIT.', 'Local catalogs, databases, credentials, model weights, and generated reports remain excluded from Git.'),
], [32, 72, 75]), P('14. Why the new model feature is optional', 'H1A'), P('Gemma 4 is used as a teaching and explanation layer because language models can summarize a completed analysis in accessible language. It is not used as the authority for correctness or complexity because the project already has stronger structured evidence for those fields. The API reconstructs saved Axioma facts and labels the advisory separately, so a model claim cannot overwrite a test result.', 'BodyA'), P('The hosted path requires a server-side GEMINI_API_KEY and sends the saved problem, code, and bounded evidence summary to Google. Users should avoid sensitive code and review current provider terms. When the key is absent or the provider fails, the local deterministic workflow continues to work.', 'BodyA'), P('Repository references used for this rationale: README.md, docs/api-contract.md, docs/threat-model-v1.md, docs/risk-register.md, docs/release-candidate-v1.md, docs/gemma4-advisory.md, docs/specifications/Axioma_PRD_v1.1.docx, docs/specifications/Axioma_TRD_v1.1.docx, and the current API, worker, frontend, and evaluator code.', 'SmallA')]

doc = SimpleDocTemplate(str(OUT), pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=17*mm, bottomMargin=18*mm, title='Axioma Concept and Architecture Rationale', author='Axioma project team')
doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
print(f'Wrote {OUT}')
