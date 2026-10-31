from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from pathlib import Path

OUT = Path.cwd() / 'Axioma_Project_Abstract.docx'

def set_font(run, name='Aptos', size=11, bold=False, color='1F2933'):
    run.font.name = name
    run._element.rPr.rFonts.set(qn('w:ascii'), name)
    run._element.rPr.rFonts.set(qn('w:hAnsi'), name)
    run.font.size = Pt(size)
    run.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)

doc = Document()
section = doc.sections[0]
section.top_margin = Inches(0.8)
section.bottom_margin = Inches(0.75)
section.left_margin = Inches(0.9)
section.right_margin = Inches(0.9)
styles = doc.styles
styles['Normal'].font.name = 'Aptos'
styles['Normal']._element.rPr.rFonts.set(qn('w:ascii'), 'Aptos')
styles['Normal']._element.rPr.rFonts.set(qn('w:hAnsi'), 'Aptos')
styles['Normal'].font.size = Pt(11)

p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('AXIOMA'); set_font(r, size=12, bold=True, color='9B6D53')
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('Evidence-first Code Analysis Platform'); set_font(r, name='Aptos Display', size=22, bold=True, color='111827')
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('Project Abstract'); set_font(r, size=12, color='6B7280')
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('Mode 1  |  Python + Java  |  Local dashboard and Docker sandbox'); set_font(r, size=9, color='6B7280')
doc.add_paragraph()

h = doc.add_paragraph(); h.paragraph_format.space_before = Pt(8); h.paragraph_format.space_after = Pt(6)
r = h.add_run('Abstract'); set_font(r, name='Aptos Display', size=15, bold=True, color='111827')

paragraphs = [
    'Axioma is an evidence-first code analysis platform designed to help developers review Python and Java solutions with more context than a single pass or fail result. The system accepts a problem statement and a candidate solution, identifies a compatible local test pack, executes the submission in a Docker-backed worker sandbox, and returns a structured report. Each report records the checks that ran, the resulting evidence claims, the strength of those claims, and the limits that remain. This design treats uncertainty as part of the user experience rather than as an implementation detail.',
    'The Mode 1 implementation combines correctness checks, generated inputs, optional reference-guided differential checks, property predicates, bounded mutation testing, static complexity analysis, and user-controlled optimization verification. Complexity estimates use language-specific signals such as loop structure, recursion, sorting and collection operations, Python line or opcode counts, and Java JVM measurements. Optimization proposals are intentionally narrow and rule-based. A proposal must pass configured equivalence checks before Axioma records any measurement, and the interface keeps the original and candidate sources visible for review. The worker isolates untrusted execution with resource limits, no network access, a read-only root filesystem, and non-root execution.',
    'Local evidence shows that the current Mode 1 paths are operational: the API, worker, and evaluator suite passed 147 tests; the starter catalog contains 1,000 compatible problem packs; a self-retrieval smoke check matched 987 of 1,000 imported descriptions to their own slugs and abstained on the remainder; and a controlled mutation smoke set detected 3 of 3 reviewed faulty variants while flagging 0 of 1 correct controls. These results demonstrate implementation progress, but they do not establish general accuracy, public-service reliability, or proof of correctness. The main remaining evidence gap is a held-out evaluation set with at least 50 independently reviewed complexity solutions, alongside broader detection and optimization coverage. Axioma therefore presents analysis as inspectable evidence that supports engineering judgment, not as an authority that replaces it.'
]
for text in paragraphs:
    p = doc.add_paragraph(); p.paragraph_format.line_spacing = 1.15; p.paragraph_format.space_after = Pt(9)
    r = p.add_run(text); set_font(r, size=11, color='1F2933')

h = doc.add_paragraph(); r = h.add_run('Keywords'); set_font(r, size=11, bold=True, color='111827')
p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(2)
r = p.add_run('code analysis; software testing; complexity estimation; mutation testing; optimization verification; sandboxed execution; evidence claims'); set_font(r, size=10, color='6B7280')

footer = section.footer.paragraphs[0]; footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = footer.add_run('Axioma project abstract'); set_font(r, size=8, color='9CA3AF')
doc.core_properties.title = 'Axioma Project Abstract'
doc.core_properties.subject = 'Evidence-first code analysis platform'
doc.core_properties.author = 'Axioma project team'
doc.save(OUT)
print(f'Wrote {OUT}')
