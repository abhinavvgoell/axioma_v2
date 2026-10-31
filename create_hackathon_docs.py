from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path.cwd()

NAVY = '102A43'
BLUE = '2F80ED'
INK = '243B53'
MUTED = '52606D'
LIGHT = 'F0F4F8'
PALE = 'EAF2FF'

def set_cell_shading(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = tcPr.find(qn('w:shd'))
    if shd is None:
        shd = OxmlElement('w:shd')
        tcPr.append(shd)
    shd.set(qn('w:fill'), fill)

def set_cell_margins(cell, top=100, start=120, bottom=100, end=120):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcMar = tcPr.first_child_found_in('w:tcMar')
    if tcMar is None:
        tcMar = OxmlElement('w:tcMar')
        tcPr.append(tcMar)
    for m, v in [('top', top), ('start', start), ('bottom', bottom), ('end', end)]:
        node = tcMar.find(qn('w:' + m))
        if node is None:
            node = OxmlElement('w:' + m)
            tcMar.append(node)
        node.set(qn('w:w'), str(v))
        node.set(qn('w:type'), 'dxa')

def style_doc(doc, title):
    section = doc.sections[0]
    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.78)
    section.right_margin = Inches(0.78)
    styles = doc.styles
    for name, size, color in [('Normal', 10.5, INK), ('Title', 25, NAVY), ('Heading 1', 17, NAVY), ('Heading 2', 12.5, BLUE)]:
        st = styles[name]
        st.font.name = 'Aptos'
        st._element.rPr.rFonts.set(qn('w:ascii'), 'Aptos')
        st._element.rPr.rFonts.set(qn('w:hAnsi'), 'Aptos')
        st.font.size = Pt(size)
        st.font.color.rgb = RGBColor.from_string(color)
    styles['Normal'].paragraph_format.space_after = Pt(6)
    styles['Normal'].paragraph_format.line_spacing = 1.08
    p = doc.add_paragraph(style='Title')
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run(title)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run('Axioma  |  Hackathon preparation material')
    r.font.size = Pt(10); r.font.color.rgb = RGBColor.from_string(MUTED)
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = footer.add_run('Axioma project team')
    r.font.size = Pt(8); r.font.color.rgb = RGBColor.from_string(MUTED)

def add_heading(doc, text, level=1):
    doc.add_heading(text, level=level)

def add_para(doc, text, bold_lead=None):
    p = doc.add_paragraph()
    if bold_lead and text.startswith(bold_lead):
        r = p.add_run(bold_lead); r.bold = True
        p.add_run(text[len(bold_lead):])
    else:
        p.add_run(text)
    return p

def add_bullets(doc, items):
    for item in items:
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_after = Pt(2)
        p.add_run(item)

def add_table(doc, headers, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = 'Table Grid'
    for i, h in enumerate(headers):
        c = table.rows[0].cells[i]
        c.text = h
        set_cell_shading(c, NAVY)
        c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        set_cell_margins(c)
        for r in c.paragraphs[0].runs:
            r.bold = True; r.font.color.rgb = RGBColor(255,255,255); r.font.size = Pt(9)
    for ri, row in enumerate(rows):
        cells = table.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = str(val)
            cells[i].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cells[i])
            if ri % 2 == 0: set_cell_shading(cells[i], LIGHT)
            for p in cells[i].paragraphs:
                for r in p.runs: r.font.size = Pt(9); r.font.color.rgb = RGBColor.from_string(INK)
    if widths:
        for row in table.rows:
            for i, w in enumerate(widths): row.cells[i].width = Inches(w)
    doc.add_paragraph()
    return table

def make_explanation():
    doc = Document(); style_doc(doc, 'Axioma Project Explanation')
    add_para(doc, 'This document explains the full Axioma idea for a hackathon audience. It separates the current working Mode 1 from the longer-term product vision so the team can present ambition without overstating what exists today.')
    add_heading(doc, 'One minute explanation')
    add_para(doc, 'Axioma is an evidence-first code intelligence platform for developers and DSA learners. A user submits a problem and a Python or Java solution. Axioma matches the problem to a compatible local pack, runs the solution inside a restricted Docker worker, checks the available examples and generated cases, estimates complexity using visible static and measurement signals, and returns a report that explains what happened and how strong the evidence is. The product is designed around a simple rule: a green check is useful, but it is not the same as a proof.')
    add_heading(doc, 'The problem')
    add_para(doc, 'Most coding platforms reduce review to pass or fail. That leaves several questions unanswered: Which cases ran? Were edge cases covered? Did the solution compile? What code pattern led to the complexity estimate? Did the benchmark measure an actual trend or only reflect machine noise? If a tool suggests an optimization, did the candidate preserve behavior? Axioma makes these questions visible in one reviewable report.')
    add_heading(doc, 'The product idea')
    add_table(doc, ['Layer', 'What it does', 'Evidence label'], [
        ('Problem matching', 'Finds a compatible catalog pack and rejects ambiguous matches', 'Catalog match'),
        ('Correctness checks', 'Runs imported examples, bounded generated inputs, references, and optional predicates', 'Executed'),
        ('Complexity analysis', 'Uses language-specific code signals and optional measurements', 'Static or statistical'),
        ('Optimization review', 'Offers narrow rule-based candidates and checks them before measuring', 'Proposal plus executed checks'),
        ('Trust and limits', 'Shows unsupported cases, disagreement, and confidence category', 'Unverified or low confidence'),
    ], [1.45, 4.15, 1.55])
    add_heading(doc, 'How the complete product can grow')
    add_para(doc, 'The long-term vision extends the same evidence model from a single DSA solution to repository-level code intelligence. Later modes can inspect a repository or commit, rank likely defects with a task-specific model if evaluation justifies it, propose a patch as a visible diff, and run regression checks before a developer accepts it. The future system should preserve human review, never silently mutate source code, and only claim what the evidence supports.')
    add_table(doc, ['Stage', 'Scope', 'Status for the presentation'], [
        ('Mode 1', 'Catalog-assisted DSA analysis for Python and Java', 'Working early-stage implementation'),
        ('Reliability milestone', 'Fresh held-out evaluation and broader coverage', 'Next evidence milestone'),
        ('Mode 2', 'Repository review, defect-risk ranking, and verified repair', 'Planned future direction'),
    ], [1.6, 4.15, 1.4])
    add_heading(doc, 'Technology stack')
    add_table(doc, ['Area', 'Technology', 'Why it is used'], [
        ('Frontend', 'React 19, TypeScript, Vite', 'Fast interactive workspace with typed API integration'),
        ('API', 'Python, FastAPI, Pydantic', 'Validation, stable REST routes, and structured contracts'),
        ('Persistence', 'SQLAlchemy, Alembic, SQLite or PostgreSQL', 'Durable jobs, reports, migrations, and local development'),
        ('Queue and updates', 'Database-backed worker queue, Server-Sent Events', 'Reliable job states and live progress updates'),
        ('Execution', 'Docker Desktop Linux containers', 'Runs untrusted Java and Python code outside the API process'),
        ('Runtimes', 'Python 3.13 and Java 21', 'Separate language adapters and reproducible execution targets'),
        ('Quality', 'Pytest, Ruff, Vitest, Oxlint', 'Backend, worker, evaluator, frontend tests, and linting'),
    ], [1.35, 2.25, 3.55])
    add_heading(doc, 'Architecture in plain language')
    add_bullets(doc, [
        'The React frontend submits a job and listens for status updates.',
        'The FastAPI API validates the request and stores a durable job record.',
        'A worker claims the job from the database queue and runs the code in Docker.',
        'The worker records test outcomes, evidence claims, complexity details, and limitations.',
        'The frontend renders the report without inventing scores or recalculating evidence.',
    ])
    add_heading(doc, 'Security and trust story')
    add_para(doc, 'Submitted code is untrusted. The intended boundary keeps execution out of the request process and applies no-network execution, non-root processes, read-only roots, output limits, and time, memory, process, and temporary-disk controls. The current local setup is suitable for development and demonstrations, not a public code execution service until the security review and deployment hardening are complete.')
    add_heading(doc, 'What exists today')
    add_bullets(doc, [
        'Mode 1 supports Python and Java function or stdin/stdout submissions.',
        'The API, worker, evaluator, catalog matching, evidence schema, and frontend workspace are implemented in the repository.',
        'The local catalog contains 1,000 compatible problem packs according to the current repository documentation.',
        'Current analysis is deterministic and measurement-based. There is no trained ML model or LLM in Mode 1.',
        'Current evaluation evidence is useful for development but should not be presented as a final general accuracy claim.',
    ])
    add_heading(doc, 'What we will say in the hackathon')
    add_para(doc, 'Axioma is an early-stage working prototype with a clear path from a focused DSA workflow to broader evidence-based code intelligence. The differentiator is not an AI label. It is the decision to separate executed checks, static heuristics, statistical measurements, proposed improvements, and unverified gaps so developers can understand how much to trust a result.')
    add_heading(doc, 'Likely judge questions')
    add_table(doc, ['Question', 'Answer'], [
        ('Is this using an LLM?', 'Not in current Mode 1. The prototype uses deterministic rules, catalog data, and measurements. Future ML or LLM components would need a defined task and evaluation.'),
        ('Does passing prove correctness?', 'No. It proves only that the configured checks passed. The report shows coverage and limitations.'),
        ('Why Docker?', 'To keep submitted code outside the API process and apply execution limits.'),
        ('Why not just use benchmarks?', 'Benchmarks are observations, not mathematical proof of asymptotic complexity. Axioma keeps them separate from static reasoning.'),
        ('What is next?', 'Freeze a fresh held-out evaluation set, widen analysis coverage, then move toward repository review and verified repair.'),
    ], [2.0, 5.15])
    add_heading(doc, 'Suggested demo path')
    add_bullets(doc, ['Choose a familiar problem such as Binary Search or Two Sum.', 'Show the submitted Python or Java solution.', 'Show the matched problem pack and imported samples.', 'Run the analysis and point out job states and evidence provenance.', 'Open the complexity section and explain why the result is an estimate.', 'End with the limits panel and the planned roadmap.'])
    doc.core_properties.title = 'Axioma Project Explanation'
    doc.core_properties.subject = 'Hackathon overview of the Axioma project'
    doc.save(ROOT / 'Axioma_Hackathon_Project_Explanation.docx')

def make_script():
    doc = Document(); style_doc(doc, 'Axioma Hackathon Speaking Script')
    add_para(doc, 'Recommended length: 8 to 10 minutes. Each member has a clear section and a handoff sentence. Replace the member labels with your names before presenting.')
    add_heading(doc, 'Presentation map')
    add_table(doc, ['Member', 'Time', 'Owns'], [
        ('Member 1', '2 minutes', 'Problem, users, and product idea'),
        ('Member 2', '2 minutes', 'Architecture and technology stack'),
        ('Member 3', '2 to 3 minutes', 'Analysis workflow and evidence model'),
        ('Member 4', '2 to 3 minutes', 'Roadmap, limitations, and closing pitch'),
    ], [1.25, 1.0, 4.9])
    sections = [
        ('Member 1  Problem and product idea', 'Hello everyone. We are presenting Axioma, an evidence-first code intelligence platform for Python and Java DSA solutions. The problem is simple: most coding tools give us a green check or a red cross, but they do not explain which checks ran, how edge cases were covered, what complexity signals were detected, or how much confidence we should place in the result. Axioma is built to answer those questions.\n\nA user gives us a problem statement and a solution. We match it to a compatible problem pack, run the solution in a controlled environment, and return a report that separates observed evidence from estimates. That means a passing sample is shown as an executed check, a complexity result is shown as a static or statistical estimate, and unsupported cases are shown instead of hidden.\n\nOur larger vision is to grow from DSA analysis into repository-level code intelligence. A future version can inspect commits, suggest a repair as a visible diff, and run regression checks before a developer accepts it. Today we are presenting an early-stage working implementation of the first mode.\n\nHandoff: Now that the problem and product idea are clear, Member 2 will explain how the system is built.'),
        ('Member 2  Architecture and stack', 'Axioma uses a small, modular architecture. The frontend is React with TypeScript and Vite. It submits a job to a FastAPI backend. The API validates the request and writes a durable job record to SQLite for local development or PostgreSQL for a shared deployment. A separate worker claims the job from the database-backed queue.\n\nThe worker is the trust boundary. It runs submitted Python or Java code in Docker containers instead of inside the API process. The design applies limits such as no outbound network, non-root execution, read-only roots, output caps, and time, memory, process, and temporary-disk limits. The worker stores the results and the frontend receives live status updates through Server-Sent Events.\n\nThe backend uses Pydantic contracts, SQLAlchemy models, and Alembic migrations. We use Pytest and Ruff for Python services and Vitest and Oxlint for the frontend. The supported execution targets are Python 3.13 and Java 21.\n\nHandoff: The architecture keeps execution separate from the API. Member 3 will now show what happens inside an analysis and how the evidence is presented.'),
        ('Member 3  Workflow and evidence model', 'The user journey has four steps. First, the user submits a problem and solution. Second, Axioma matches the problem against the local catalog and rejects an ambiguous match instead of silently choosing one. Third, the worker runs imported samples and, when constraints allow it, bounded seeded inputs or benchmark cases. Fourth, the interface shows a report.\n\nThe report has layers. Correctness checks show individual cases and expected outcomes. Static analysis looks for code signals such as loop nesting, sorting, collection operations, recursion, and recognized binary-search shapes. Optional measurements use Python line or opcode events and Java JVM observations. These measurements help us compare behavior at selected sizes, but they do not prove asymptotic complexity.\n\nAxioma can also check a narrow optimization proposal. The original code stays visible, the candidate must pass the relevant checks, and only then can the system record a comparison. The report labels each claim by provenance, such as executed, static, statistical, or unverified. This is the core idea: the system does not hide uncertainty behind one score.\n\nHandoff: We have shown how the prototype works today. Member 4 will close with the roadmap, the honest limitations, and why this is a strong foundation for the next stage.'),
        ('Member 4  Roadmap and closing', 'Axioma is in an early development stage, so we want to be precise about both progress and limits. The repository already contains the Mode 1 API, worker, frontend, catalog matching, Docker execution path, evidence schema, and evaluation tools. The local documentation records a 1,000-pack compatible catalog and working checks across the API, worker, and evaluator paths. These are development results, not a claim that the platform proves correctness or is ready for public execution.\n\nOur next milestone is evaluation integrity. We will freeze a fresh human-reviewed holdout, run the analyzer without tuning on it, report exact accuracy and coverage, and analyze failure categories. After that we can broaden complexity support, test more optimization patterns, and begin the repository-review mode. Any future ML or LLM component will be added only for a defined task with labeled data, a baseline, and a leakage-resistant evaluation.\n\nThe value of Axioma is trust through visibility. Developers still make the final decision, but they receive a better record of what happened, what was measured, and what remains uncertain. We are building a code analysis assistant that earns trust by showing its work. Thank you.\n\nOptional final sentence if time allows: We would love feedback on which evidence developers need most when reviewing a solution: correctness coverage, complexity reasoning, optimization comparison, or repository-level risk.'),
    ]
    for heading, body in sections:
        add_heading(doc, heading)
        for para in body.split('\n\n'):
            p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(8); p.add_run(para)
    add_heading(doc, 'Fast answers for the Q and A')
    add_bullets(doc, ['Current AI status: Mode 1 is rule-based and measurement-based; no trained model or LLM is required.', 'Correctness: passing configured tests is evidence for those cases, not proof for all inputs.', 'Security: submitted code runs in a separate restricted Docker worker; public deployment needs further hardening.', 'Business or user value: students learn from evidence and developers review code with more context than pass or fail.', 'Next step: fresh held-out evaluation, then broader repository analysis and verified repair.'])
    doc.core_properties.title = 'Axioma Hackathon Speaking Script'
    doc.core_properties.subject = 'Four-member presentation script for Axioma'
    doc.save(ROOT / 'Axioma_Hackathon_Speaking_Script.docx')

if __name__ == '__main__':
    make_explanation(); make_script()
    print('Wrote hackathon DOCX files')
