from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

OUT = Path.cwd() / 'Axioma_Hackathon_QA_Playbook.docx'
NAVY, BLUE, INK, MUTED, LIGHT = '102A43', '2F80ED', '243B53', '52606D', 'F0F4F8'

def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr(); shd = tcPr.find(qn('w:shd'))
    if shd is None: shd = OxmlElement('w:shd'); tcPr.append(shd)
    shd.set(qn('w:fill'), fill)

def margins(cell):
    tcPr = cell._tc.get_or_add_tcPr(); tcMar = tcPr.first_child_found_in('w:tcMar')
    if tcMar is None: tcMar = OxmlElement('w:tcMar'); tcPr.append(tcMar)
    for side in ['top','start','bottom','end']:
        node = tcMar.find(qn('w:'+side))
        if node is None: node = OxmlElement('w:'+side); tcMar.append(node)
        node.set(qn('w:w'), '120'); node.set(qn('w:type'), 'dxa')

def setup(doc):
    sec = doc.sections[0]
    sec.top_margin = Inches(0.68); sec.bottom_margin = Inches(0.65)
    sec.left_margin = Inches(0.78); sec.right_margin = Inches(0.78)
    for name, size, color in [('Normal',10.5,INK),('Title',25,NAVY),('Heading 1',17,NAVY),('Heading 2',12.5,BLUE)]:
        s = doc.styles[name]; s.font.name='Aptos'; s._element.rPr.rFonts.set(qn('w:ascii'),'Aptos'); s._element.rPr.rFonts.set(qn('w:hAnsi'),'Aptos'); s.font.size=Pt(size); s.font.color.rgb=RGBColor.from_string(color)
    doc.styles['Normal'].paragraph_format.space_after = Pt(6)
    doc.styles['Normal'].paragraph_format.line_spacing = 1.08
    p=doc.add_paragraph(style='Title'); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.add_run('Axioma Hackathon Q and A Playbook')
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; r=p.add_run('Important questions, deeper technical replies, and safe answers'); r.font.size=Pt(10); r.font.color.rgb=RGBColor.from_string(MUTED)
    f=sec.footer.paragraphs[0]; f.alignment=WD_ALIGN_PARAGRAPH.CENTER; r=f.add_run('Axioma project team  |  Keep answers evidence-based'); r.font.size=Pt(8); r.font.color.rgb=RGBColor.from_string(MUTED)

def p(doc, text):
    q=doc.add_paragraph(); q.add_run(text); return q

def bullets(doc, items):
    for x in items:
        q=doc.add_paragraph(style='List Bullet'); q.paragraph_format.space_after=Pt(2); q.add_run(x)

def qa(doc, question, short, deep, follow=None):
    doc.add_heading(question, level=2)
    q=doc.add_paragraph(); r=q.add_run('Short answer: '); r.bold=True; q.add_run(short)
    q=doc.add_paragraph(); r=q.add_run('Deeper answer: '); r.bold=True; q.add_run(deep)
    if follow:
        q=doc.add_paragraph(); r=q.add_run('If they go deeper: '); r.bold=True; q.add_run(follow)

def table(doc, headers, rows, widths=None):
    t=doc.add_table(rows=1, cols=len(headers)); t.alignment=WD_TABLE_ALIGNMENT.CENTER; t.style='Table Grid'
    for i,h in enumerate(headers):
        c=t.rows[0].cells[i]; c.text=h; shade(c,NAVY); margins(c); c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
        for r in c.paragraphs[0].runs: r.bold=True; r.font.color.rgb=RGBColor(255,255,255); r.font.size=Pt(9)
    for ri,row in enumerate(rows):
        cs=t.add_row().cells
        for i,v in enumerate(row):
            cs[i].text=str(v); margins(cs[i]); cs[i].vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            if ri%2==0: shade(cs[i],LIGHT)
            for pp in cs[i].paragraphs:
                for rr in pp.runs: rr.font.size=Pt(9); rr.font.color.rgb=RGBColor.from_string(INK)
    if widths:
        for row in t.rows:
            for i,w in enumerate(widths): row.cells[i].width=Inches(w)
    doc.add_paragraph()

def main():
    doc=Document(); setup(doc)
    p(doc,'Use this playbook as a speaking aid. Start with the short answer, then add the deeper answer only if the judge asks for more detail. Never claim that Axioma proves correctness, proves asymptotic complexity, uses a trained model in Mode 1, or is ready for public code execution.')
    doc.add_heading('Answering pattern', level=1)
    bullets(doc,['Answer the exact question first.', 'Separate what exists today from the roadmap.', 'Name the evidence source: executed check, static heuristic, measurement, or unverified gap.', 'State the limitation before the judge has to discover it.', 'If you do not know, say what you would measure or test next.'])
    doc.add_heading('Quick reference', level=1)
    table(doc,['Topic','Safe one sentence'],[
        ('What is it?','Axioma is an evidence-first code intelligence platform for Python and Java DSA solutions.'),
        ('What is novel?','It makes evidence provenance and uncertainty visible instead of collapsing review into pass or fail.'),
        ('Is it AI?','Current Mode 1 is rule-based and measurement-based; future ML or LLM use is a planned, evaluated extension.'),
        ('Does it prove correctness?','No. It reports what the configured checks support and what remains unverified.'),
        ('Status?','An early-stage working prototype with a focused Mode 1 and a roadmap toward repository analysis.'),
    ],[1.35,5.25])

    doc.add_heading('Product and value', level=1)
    qa(doc,'What exactly does Axioma do?', 'It accepts a problem and a Python or Java solution, runs supported checks, analyzes complexity signals, and returns an evidence-rich report.', 'Axioma first matches the problem to a compatible local catalog pack. It then queues the work, runs the submission in a restricted Docker worker, stores individual test outcomes and evidence claims, and streams job status back to the frontend. The report separates correctness observations, static complexity clues, optional measurements, optimization proposals, and unsupported cases.', 'Describe it as a code review workbench, not as a replacement for a judge or an expert engineer.')
    qa(doc,'Who is the primary user?', 'DSA learners and developers who want more explanation than a pass or fail result.', 'Learners can see edge cases, complexity reasoning, and why a solution may be risky. Developers can use the same evidence model when reviewing a solution or comparing an optimization candidate. The long-term audience includes teams reviewing repositories and pull requests, but that is future scope.', 'The first product wedge is deliberately narrow so the team can validate trust and evaluation before expanding.')
    qa(doc,'Why is this better than an online judge?', 'An online judge tells you whether selected tests passed; Axioma explains the evidence behind the result and its limits.', 'An online judge is optimized for verdicts. Axioma is optimized for inspectability. It records the source of each claim, exposes test counts and individual outcomes, labels static and statistical signals differently, and can compare a proposed optimization only after checking it. It complements a judge rather than replacing one.', 'Do not claim that Axioma has hidden tests comparable to every commercial platform.')
    qa(doc,'Why start with DSA problems?', 'DSA problems provide structured inputs, known examples, and useful complexity questions, which makes them a controlled starting point.', 'A focused DSA workflow lets the team test matching, sandbox execution, generated inputs, complexity estimation, and evidence reporting without the huge variability of arbitrary repositories. Once the evidence model is reliable, the same ideas can extend to repository review and verified repair.', 'The scope is a deliberate product wedge, not the final limit of the vision.')

    doc.add_heading('Technical architecture', level=1)
    qa(doc,'Walk us through one request from browser to result.', 'The browser submits to FastAPI, FastAPI queues a durable job, the worker runs it in Docker, and the frontend renders the stored report through streamed updates.', 'React and TypeScript send a typed request to FastAPI. Pydantic validates the shape and size. SQLAlchemy stores the job and status events in SQLite locally or PostgreSQL when configured. A worker claims the job from the database-backed queue, executes Python or Java in a sandbox, stores test records and evidence claims, and marks the job terminal. The frontend listens over Server-Sent Events and can reconnect using the last event ID.', 'The key design choice is that the API does not compile or execute submitted code inside the request process.')
    qa(doc,'Why use a database-backed queue instead of a separate queue service?', 'It keeps the early-stage system small while still providing durable state, leases, and recovery.', 'A database-backed queue avoids adding Kafka, Redis, or another service before the product needs it. Jobs have explicit states and identifiers, workers claim leases, and expired work can be recovered. If scale or throughput later requires a specialized broker, the job contract can remain stable.', 'This is an early-stage tradeoff for maintainability, not a claim that a database queue fits every production scale.')
    qa(doc,'Why use Server-Sent Events?', 'SSE gives the browser one-way live job updates with a simple HTTP-compatible connection.', 'The server owns the job state, so the frontend mainly needs a stream of status changes. Persisted event IDs allow reconnection and reduce the chance of losing a terminal update. WebSockets could be useful for richer two-way interaction, but SSE is enough for the current workflow.', 'The stream is tied to the job and should be authorized before a future multi-user deployment.')
    qa(doc,'Why Docker, and what does Docker not solve?', 'Docker separates submitted code from the API process and provides configurable resource controls, but it is not automatically a complete public security boundary.', 'Axioma runs untrusted code in containers with no network by default, non-root execution, read-only roots, output limits, and time, memory, process, and temporary-disk controls. Containers still share the host kernel, and the worker has access to the Docker daemon in the local setup. That is why the repository explicitly treats the current configuration as local development and demonstration infrastructure until security hardening and review are complete.', 'A public deployment would need stronger isolation, careful daemon separation, monitoring, cleanup, and an independent security review.')

    doc.add_heading('Correctness, complexity, and evidence', level=1)
    qa(doc,'Does a passing result prove that the code is correct?', 'No. It proves that the configured checks passed for the cases that ran.', 'Imported samples, generated inputs, references, and properties all have different strengths. A generated input without an independent oracle tests robustness but cannot independently prove the expected answer. A reference implementation can provide useful differential evidence, but agreement does not prove that the reference itself is correct. The report therefore shows which checks ran, their outcomes, and what was not checked.', 'Use the phrase “evidence for these cases” instead of “proof of correctness.”')
    qa(doc,'How does Axioma estimate time complexity?', 'It combines visible code-structure signals with optional empirical measurements, and labels the result as an estimate.', 'The Python and Java analyzers inspect patterns such as loop nesting, recursion, sorting, collection operations, and recognized binary-search shapes. Where supported, Python line-event and opcode counts or Java JVM timing are collected over declared benchmark sizes. The system compares signals and can mark disagreement. Static analysis is syntax-level reasoning, while benchmarks are machine- and input-dependent observations.', 'A benchmark can support a trend but cannot establish an asymptotic bound.')
    qa(doc,'Why not just use an LLM to explain the complexity?', 'Because a fluent explanation is not the same as reliable evidence.', 'The current Mode 1 intentionally uses deterministic rules and measurements so the team can inspect behavior, reproduce results, and evaluate failure categories. A future model could help with a defined task such as ranking review risk or summarizing evidence, but it would need provenance, a baseline, a leakage-resistant split, model versioning, and documented limitations. Adding an AI label without that discipline would reduce trust.', 'This answer is a strength: the team is avoiding unsupported AI claims.')
    qa(doc,'What happens when the analyzer is unsure?', 'It should return unknown, unsupported, low confidence, or methods disagree instead of inventing a precise answer.', 'The product treats abstention as a valid outcome. The API schema keeps evidence type, confidence category, method, estimate, and disagreement separate. This lets users distinguish “the tool found a signal” from “the tool has enough evidence to support a conclusion.”', 'The next evaluation milestone should measure coverage and conditional accuracy separately.')
    qa(doc,'How are optimization suggestions handled safely?', 'They are narrow proposals, not silent edits, and they must pass configured checks before any comparison is reported.', 'The original code remains visible. A rule-based candidate is generated only for supported patterns. The candidate is run against the relevant samples and generated or benchmark inputs. Equivalence evidence and any measured difference are stored separately, and the UI discloses that measurements are low confidence and environment-dependent.', 'If evidence is inconclusive, the correct result is no improvement claim.')

    doc.add_heading('Security and privacy', level=1)
    qa(doc,'Can users safely submit secrets or private code?', 'The design treats source code as private and untrusted, but the current local prototype should not be presented as a public service.', 'The intended design avoids sending source code to external AI services in Mode 1 and executes code outside the API process. A production service would still need authentication, access control, encryption, retention and deletion policies, isolation review, audit logging, and clear disclosure about what is stored. The current repository explicitly lists hosted deployment and accounts as not built.', 'Recommend using sample or non-sensitive code during the hackathon demo.')
    qa(doc,'Can submitted code escape the container?', 'The system reduces risk with restrictions, but no local container setup should be described as risk-free.', 'The worker disables outbound network access, avoids broad host mounts, uses non-root execution and a read-only root filesystem, limits resources, truncates output, and cleans temporary artifacts. The remaining risk comes from the shared host kernel, Docker daemon exposure to the worker, runtime vulnerabilities, and configuration mistakes. Those are reasons for a separate threat model and security gate.', 'If asked for a public launch date, say security hardening is a prerequisite, not a solved detail.')
    qa(doc,'What data does Axioma store?', 'It stores jobs, status events, test records, evidence claims, and reports needed for the workflow; the local browser history stores summaries rather than source code.', 'The API contract makes the report structured so the frontend can render it without inventing results. A future hosted product needs explicit ownership, retention, deletion, and access controls. The current local history is descriptive and browser-local; it is not a multi-user account system.', 'Do not imply cross-device history, account-level deletion, or production privacy guarantees exist today.')

    doc.add_heading('Evaluation and evidence', level=1)
    qa(doc,'What evidence shows that the prototype works?', 'The repository contains implementation tests, catalog checks, sandbox checks, and evaluator tooling, but these are development evidence rather than a universal accuracy claim.', 'The current documentation records a 1,000-pack compatible local catalog, API and worker test coverage, deterministic matching checks, and controlled smoke evaluations. The project also records limitations: the historical complexity result was diagnostic, the current calibration replay is not a held-out score, and broader independent evaluation remains open. We present the numbers with their sample size and denominator.', 'A strong answer is “we know what has been tested and what has not.”')
    qa(doc,'What is the next evaluation milestone?', 'Freeze a fresh human-reviewed holdout before running the analyzer, then report accuracy, coverage, abstention, and failure categories.', 'The team should separate development data from final evaluation data, pin the analyzer version and manifest, review labels and rationales before execution, and keep per-case evidence. If further tuning happens, a new untouched split is required. This prevents the team from presenting a tuned-on set as a final score.', 'Mention that coverage and selective accuracy matter because abstention is part of the product behavior.')
    qa(doc,'How would you prove this scales?', 'We would measure queue throughput, worker concurrency, job latency, sandbox resource usage, and database behavior under representative workloads.', 'The current prototype is not a public scale claim. A scale plan would define workload shapes, warm-up policy, runtime versions, hardware, sample size, percentile latency, failure recovery, and cost per job. We would load-test the API and queue separately from sandbox execution, then evaluate whether a database queue remains appropriate.', 'Do not turn one local latency sample into an SLA.')

    doc.add_heading('Roadmap and business questions', level=1)
    qa(doc,'What is the long-term vision?', 'Move from single-solution DSA analysis to repository review and verified repair while preserving transparent evidence.', 'Mode 2 could ingest a repository or commit, run deterministic static checks, rank likely defects, propose a visible patch, and execute regression checks before acceptance. Optional ML or LLM components would be added only for specific evaluated tasks. The user would always see the original code, the proposed diff, the checks that ran, and the uncertainty.', 'The roadmap follows evidence maturity: reliability before expansion.')
    qa(doc,'Who would pay for or adopt this?', 'The first users are learners, mentors, and developers who need a richer review record; teams could later use it for pull-request analysis.', 'A student or individual workflow can use local Mode 1 for feedback. Education teams could use it to teach testing and complexity reasoning. Engineering teams could use repository mode to triage risk and validate proposed fixes. The project needs user research and a deployment model before making a commercial claim.', 'Frame this as a product hypothesis, not validated market traction.')
    qa(doc,'What is the strongest reason to choose Axioma?', 'It makes the reasoning behind a code-analysis result inspectable.', 'Many tools optimize for a verdict or a generated explanation. Axioma combines execution evidence, static signals, measurements, provenance, confidence categories, and explicit gaps. That makes it easier for a developer to decide what to trust, what to investigate, and what to test next.', 'The differentiator is evidence discipline, not an unsupported claim of general intelligence.')

    doc.add_heading('Difficult judge follow-ups', level=1)
    qa(doc,'Why should we trust your generated tests?', 'We should not treat every generated test as independently trusted unless it has an oracle.', 'The generator is useful for boundary coverage, adversarial shapes, and robustness. When an expected output comes from a trusted reference or a declared property, the source of that expected output must be labeled. Without an oracle, the generated run can reveal crashes, timeouts, or disagreement, but it cannot prove semantic correctness.', 'This distinction is central to the project’s evidence model.')
    qa(doc,'What if the reference implementation is wrong?', 'Then differential agreement can repeat the same mistake, so references are evidence rather than absolute truth.', 'A stronger workflow uses reviewed examples, independent references, property checks, mutation testing, and disagreement detection. None of those alone creates proof, but independent signals can expose errors. The report should retain the provenance of the reference and avoid calling it a ground truth unless it has been independently reviewed.', 'The roadmap includes stronger evaluation and independent review rather than pretending the oracle problem is solved.')
    qa(doc,'What if the code uses a pattern you do not recognize?', 'Axioma should abstain or return an unsupported estimate.', 'The current heuristics cover selected Python and Java shapes, not arbitrary algorithms, helper-call costs, hidden data structures, or every recurrence. A safe analyzer reports the missing coverage. Future versions can expand pattern support and use reviewed evaluation cases to measure whether an expansion helps.', 'Abstention protects trust and gives the team a measurable roadmap.')
    qa(doc,'Why not support every language and framework now?', 'Because broad support would make the evidence and security boundary harder to validate.', 'Language adapters, runtimes, compilers, input harnesses, and sandbox rules all have different failure modes. Java and Python provide a manageable first boundary. Once the contract, evaluation discipline, and worker isolation are stronger, other languages can be added behind separate adapters.', 'Narrow scope is a reliability choice.')
    qa(doc,'What would you build next if given more time?', 'First strengthen held-out evaluation and sandbox hardening, then widen analysis coverage and add repository review.', 'The order matters. Better metrics and security evidence should come before adding a model, more languages, or public deployment. The next development loop should turn observed failure categories into generalizable fixes with regression tests, then repeat evaluation on a new untouched set.', 'End with one concrete next step rather than a long feature wish list.')
    qa(doc,'What can you show in a live demo?', 'Show a familiar problem, submit a solution, run it in the worker, and open the evidence and limitations sections.', 'A reliable demo path is Binary Search or Two Sum. Show the catalog match, imported samples, job state updates, individual outcomes, complexity signals, and the explanation that benchmarks are observations. Keep a pre-recorded or saved report available in case Docker is unavailable during judging.', 'Never fabricate a successful result if the demo environment fails; show the failure state and explain it.')

    doc.add_heading('Closing answer', level=1)
    p(doc,'Axioma is an early-stage but working foundation for evidence-based code intelligence. Its central promise is modest and useful: show developers what was checked, how it was checked, what the signals suggest, and what remains uncertain. That promise is broad enough to grow into repository review and verified repair, but disciplined enough to be tested honestly today.')
    doc.core_properties.title='Axioma Hackathon Q and A Playbook'; doc.core_properties.subject='Deep judge questions and safe answers for Axioma'; doc.core_properties.author='Axioma project team'
    doc.save(OUT); print(f'Wrote {OUT}')

if __name__=='__main__': main()
