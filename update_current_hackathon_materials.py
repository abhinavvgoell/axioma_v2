from pathlib import Path
from docx import Document
from docx.shared import Pt

ROOT = Path.cwd()

def add_heading(doc, text, level=1):
    doc.add_heading(text, level=level)

def add_para(doc, text):
    doc.add_paragraph(text)

def add_bullets(doc, items):
    for item in items:
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_after = Pt(2)
        p.add_run(item)

def update_explanation():
    path = ROOT / 'Axioma_Hackathon_Project_Explanation.docx'
    doc = Document(path)
    add_heading(doc, 'Latest implementation updates')
    add_para(doc, 'Since the earlier hackathon materials, Axioma has added an optional model-assisted learning layer and stronger evidence provenance. These features are part of Mode 1, but they remain clearly separated from the deterministic analysis.')
    add_bullets(doc, [
        'Optional Gemma 4 advisory review through Google Gemini API. The user runs Axioma first, then explicitly asks Gemma for a short educational explanation and one learning suggestion.',
        'Gemma receives the saved problem, saved code, and a bounded summary of Axioma evidence. It does not execute code, change test results, change the complexity estimate, or edit the source.',
        'Gemma output is labeled model evidence with low confidence. The feature requires a server-side GEMINI_API_KEY and does not run model weights on the local GPU.',
        'The UI now shows an evidence review surface covering checks, saved inputs, detected code signals, and documented claim limits.',
        'Test cases can display bounded input previews with SHA-256 hashes, so users can see which configured input was used without exposing unlimited output.',
        'Benchmark and generated inputs are persisted with origin, problem-pack identity, generator version or artifact hash, seed, size, strategy, and runtime configuration.',
        'Completed jobs with matching persisted benchmark snapshots can be replayed exactly for inputs. Timings are rerun observations and may differ across machines and runs.',
        'Problem-pack identity now records the matched slug, title, and source so later reports and model requests stay tied to the saved analysis.',
        'The repository now documents the MIT open-source application scope while keeping local catalogs, databases, credentials, model weights, and generated reports out of Git.'
    ])
    add_heading(doc, 'Updated user flow', level=2)
    add_bullets(doc, [
        'Run the deterministic Axioma analysis first.',
        'Inspect evidence, test groups, input previews, complexity signals, and limitations.',
        'Optionally ask Gemma 4 for a beginner-friendly explanation, while keeping the saved Axioma facts authoritative.',
        'Replay benchmark inputs when retained provenance proves that the historical inputs match exactly.',
        'Use the result as a learning and review aid, not as a universal proof.'
    ])
    doc.save(path)

def update_script():
    path = ROOT / 'Axioma_Hackathon_Speaking_Script.docx'
    doc = Document(path)
    add_heading(doc, 'Updated feature talking points')
    add_para(doc, 'Add this section after the workflow explanation if the judges ask what was implemented after the initial prototype.')
    add_heading(doc, 'Optional Gemma 4 advisory', 2)
    add_para(doc, 'We added an optional Gemma 4 advisory through Google Gemini API. The user must first complete an Axioma run, and then explicitly click Ask Gemma 4. Gemma receives the saved problem, the saved code, and a bounded summary of Axioma results. It explains the likely approach and gives one learning suggestion. Its output is labeled model evidence with low confidence. It cannot change test totals, complexity estimates, or source code.')
    add_heading(doc, 'Evidence provenance and replay', 2)
    add_para(doc, 'We also made the report more inspectable. Test cases can show bounded input previews with SHA-256 hashes. Benchmark inputs are stored with their origin, size, seed, strategy, generator version or artifact hash, problem identity, and runtime configuration. A completed job can be replayed only when those saved inputs match exactly. The input is reproducible; the timing can still change on another machine.')
    add_heading(doc, 'Updated handoff for Member 4', 2)
    add_para(doc, 'Our newest work strengthens trust in two ways. First, optional Gemma 4 helps explain a completed run for learning, but it does not become the source of truth. Second, input snapshots and benchmark replay make the evidence more reproducible. We also document the open-source application scope and keep private catalogs, credentials, databases, and generated reports out of Git.')
    doc.save(path)

def update_qa():
    path = ROOT / 'Axioma_Hackathon_QA_Playbook.docx'
    doc = Document(path)
    add_heading(doc, 'Questions about the newest implementation')
    qas = [
        ('What new feature did you implement?', 'We added an optional Gemma 4 advisory, evidence-review UI, input previews with hashes, and replayable benchmark provenance.', 'The deterministic Axioma run remains the primary workflow. The model is invoked only after a completed saved run. Reports can now expose bounded inputs and prove whether benchmark inputs match before replaying them.'),
        ('Which model are you using now?', 'The optional advisory uses Google\'s hosted Gemma 4 model through the Gemini API, defaulting to gemma-4-26b-a4b-it.', 'The model is used only for a short beginner-friendly explanation and one learning suggestion. A configuration option supports gemma-4-31b-it. The response is labeled low-confidence model evidence, and saved Axioma facts remain authoritative.'),
        ('Why use Gemma 4 instead of an LLM for the whole analysis?', 'Because Gemma is useful for explanation, while deterministic checks are safer for evidence and execution.', 'The model receives bounded context after Axioma finishes. It cannot execute code, alter test counts, alter complexity, or silently rewrite source. This keeps the model in a teaching role instead of giving it authority over the report.'),
        ('Does the model train on your code?', 'We do not train a model in this project.', 'The optional hosted path sends the saved problem, code, and bounded evidence summary to Google. The UI warns users not to send sensitive code and points them to current provider terms. The local deterministic workflow continues to work without an API key.'),
        ('What happens if Gemma is unavailable?', 'Axioma still works without it.', 'The model feature is optional. Without GEMINI_API_KEY, the endpoint returns setup guidance. Provider errors are reported separately and do not invalidate the saved Axioma run.'),
        ('How do you stop Gemma from changing the facts?', 'The API reconstructs test totals and complexity facts from the saved report after receiving the model response.', 'The normalization layer removes prompt-like or unsupported output, inserts saved counts and saved complexity details, and labels the advisory as model evidence. The model text is not allowed to become the source of truth.'),
        ('What is benchmark replay?', 'It reruns the same saved benchmark inputs from a completed job.', 'Axioma persists the exact input, SHA-256 hash, origin, size, seed, strategy, generator version or artifact hash, problem identity, and runtime configuration. Replay is refused if the snapshots are missing or do not match. Inputs are identical; elapsed timing can differ.'),
        ('Why show input previews?', 'So the user can see what a test actually used.', 'The preview is bounded to avoid unlimited output and includes a hash of the full saved snapshot. It improves inspectability without claiming that the visible preview represents every possible input.'),
        ('What does the new evidence review UI show?', 'It answers four questions: which checks ran, which inputs are available, which code signals were detected, and where the limits are.', 'The UI groups failed, passed, and skipped cases, opens failed cases by default, shows origins and input previews when available, and keeps complexity method and limitations visible.'),
        ('What changed about the open-source scope?', 'The application code is documented as MIT-licensed, while local catalogs, databases, credentials, model weights, and generated reports remain excluded from Git.', 'The license covers the application source. Imported problem content has separate source and redistribution terms, so the team must reproduce it locally and verify its terms before sharing it.'),
    ]
    for question, short, deep in qas:
        add_heading(doc, question, level=2)
        p = doc.add_paragraph(); r = p.add_run('Short answer: '); r.bold = True; p.add_run(short)
        p = doc.add_paragraph(); r = p.add_run('Deeper answer: '); r.bold = True; p.add_run(deep)
    doc.save(path)

if __name__ == '__main__':
    update_explanation(); update_script(); update_qa(); print('Updated hackathon DOCX materials')
