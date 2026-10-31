from pathlib import Path
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from pptx import Presentation
from pptx.util import Inches, Pt as PPTPt
from pptx.dml.color import RGBColor as PPTRGB

root = Path.cwd()

def set_doc_font(run, name='Aptos', size=10, bold=False, color='6B7280'):
    run.font.name = name
    run._element.rPr.rFonts.set(qn('w:ascii'), name)
    run._element.rPr.rFonts.set(qn('w:hAnsi'), name)
    run.font.size = Pt(size)
    run.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)

doc_path = root / 'Axioma_Project_Abstract.docx'
doc = Document(doc_path)
meta = doc.paragraphs[3]
team = doc.add_paragraph()
team.alignment = WD_ALIGN_PARAGRAPH.CENTER
team.paragraph_format.space_before = Pt(2)
team.paragraph_format.space_after = Pt(8)
r = team.add_run('Team Leader: Prince Yadav   |   Members: Abhinav Goel, Rohit Saini')
set_doc_font(r, size=9, color='6B7280')
doc.save(doc_path)

ppt_path = root / 'Axioma_Project_Presentation.pptx'
prs = Presentation(ppt_path)
slide = prs.slides[0]
box = slide.shapes.add_textbox(Inches(0.63), Inches(5.95), Inches(6.8), Inches(0.35))
tf = box.text_frame
tf.clear()
p = tf.paragraphs[0]
p.text = 'Team Leader: Prince Yadav   |   Members: Abhinav Goel, Rohit Saini'
p.font.name = 'Aptos'
p.font.size = PPTPt(10)
p.font.color.rgb = PPTRGB(167, 175, 176)
prs.save(ppt_path)
print('Updated team details in both deliverables.')
