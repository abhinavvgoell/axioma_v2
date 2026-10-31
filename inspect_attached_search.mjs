import { importRuntimeModule } from 'file:///C:/Users/Abhinav%20Goel/.codex/plugins/cache/openai-primary-runtime/presentations/26.1030.10813/skills/presentations/container_tools/runtime_helpers.mjs';
const { FileBlob, PresentationFile } = await importRuntimeModule('@oai/artifact-tool');
const p = await PresentationFile.importPptx(await FileBlob.load('C:/Users/Abhinav Goel/OneDrive/Desktop/Axioma_Hackathon_Presentation_v2.pptx'));
for (const term of ['What can I safely','The report makes']) { const x=await p.inspect({kind:'textbox',search:term,maxChars:5000}); console.log('TERM',term); console.log(x.ndjson); }




