import { importRuntimeModule } from 'file:///C:/Users/Abhinav%20Goel/.codex/plugins/cache/openai-primary-runtime/presentations/26.1030.10813/skills/presentations/container_tools/runtime_helpers.mjs';
const { FileBlob, PresentationFile } = await importRuntimeModule('@oai/artifact-tool');
const p = await PresentationFile.importPptx(await FileBlob.load('C:/Users/Abhinav Goel/OneDrive/Desktop/Axioma_Hackathon_Presentation_v2.pptx'));
const x = await p.inspect({kind:'textbox', search:'Gemma 4', maxChars:5000});
console.log(x.ndjson);
