import fs from 'node:fs/promises';
import { importRuntimeModule } from 'file:///C:/Users/Abhinav%20Goel/.codex/plugins/cache/openai-primary-runtime/presentations/26.1030.10813/skills/presentations/container_tools/runtime_helpers.mjs';

const { FileBlob, PresentationFile } = await importRuntimeModule('@oai/artifact-tool');
const input = 'C:/Users/Abhinav Goel/OneDrive/Desktop/Axioma_Hackathon_Presentation_v2.pptx';
const output = 'C:/Users/Abhinav Goel/OneDrive/Desktop/Axioma_Hackathon_Presentation_v2_Gemma4.pptx';
const presentation = await PresentationFile.importPptx(await FileBlob.load(input));

const replace = (id, from, to) => {
  const target = presentation.resolve(id);
  target.text.replace(from, to);
};

replace('sh/03ix43e5', 'Return test evidence, complexity signals, input provenance, replayable benchmarks, and limitations. Optional Gemma 4 adds a learning explanation after the run.', 'Evidence, complexity, and proposals. Optional Gemma 4 gives a learning explanation after the run.');
replace('sh/03ix43e5', 'Return test evidence, complexity signals, proposals, and limitations. Optional Gemma 4 adds a learning explanation after the run.', 'Evidence, complexity, and proposals. Optional Gemma 4 gives a learning explanation after the run.');
replace('sh/f29gbyx0', 'Explain + Gemma 4', 'Explain');
replace('sh/f29gbyx0', 'Explain', 'Explain');
replace('sh/ah8nu54b', 'Catalog-assisted Python and Java analysis with sandbox execution and transparent reports.', 'Catalog-assisted Python and Java analysis with sandbox execution, input provenance, benchmark replay, and an optional Gemma 4 advisory.');
replace('sh/f2d0b6lc', 'UNVERIFIED', 'MODEL / UNVERIFIED');
replace('sh/eh4jil4r', 'Unsupported or missing oracle cases', 'Gemma advisory or unsupported cases are labeled separately from executed evidence.');
replace('sh/50v2pgna', 'The report makes the answer inspectable instead of hiding uncertainty behind one score.', 'The report makes the answer inspectable. Gemma is advisory and cannot change test outcomes or the complexity estimate.');

const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(output);
console.log(`Wrote ${output}`);
