# Axioma Mode 1 frontend

This React and TypeScript app is the Mode 1 workspace. It submits Python or Java function and stdin/stdout problems to the local API, streams job status, and displays the report returned by the API. For function problems, you can provide a reference and an independent second reference; both must match the declared examples and each other before differential inputs are compared. This is corroboration, not proof. A static rule endpoint can suggest a candidate for one recognized integer-array accumulation pattern; you choose whether to place it in the optimization panel and run checks. You can also enter an alternate implementation and optional benchmark inputs; Axioma checks equivalence before it reports measurements. It does not calculate evidence, test totals, complexity, or gate states in the browser, and it never silently rewrites the original source.

## Run locally

Start the API from `services/api` in one terminal using the repository's Windows setup instructions. Start the worker in another terminal if you want jobs to execute. The worker requires Docker Desktop with Linux containers and the images listed in the root README.

Start the frontend from this directory:

```powershell
npm ci
npm run dev
```

Open <http://127.0.0.1:5173/>. The Vite development server forwards `/api/...` requests to `http://127.0.0.1:8000/...`. The UI can show submitted job status with only the API running; a worker and Docker sandbox are needed to produce a completed analysis report.

## Build and lint

```powershell
npm run build
npm run lint
```

The current implementation is deliberately limited to Mode 1. Repository review, authentication, accounts, and hosted deployment are outside this frontend phase. `frontend-prototype/` at the repository root is a separate visual reference and is not imported by this app.
