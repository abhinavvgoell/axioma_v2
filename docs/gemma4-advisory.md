# Optional Gemma 4 advisory

Axioma can optionally ask Google's hosted Gemini API to produce an educational code-review advisory using the open-weight Gemma 4 model `gemma-4-26b-a4b-it`. This does not replace Mode 1's deterministic checks or static complexity heuristic. The response is labeled `model` evidence with low confidence, is not executed or independently verified, and never edits the user's code.

## Enable locally

1. Create a Gemini API key in Google AI Studio.
2. Set `GEMINI_API_KEY` in the API process environment or the API's `.env` file. Never expose the key to the browser or commit it.
3. Optionally set `GEMMA_MODEL` to `gemma-4-31b-it` instead of the default `gemma-4-26b-a4b-it`.
4. Restart the API and use **Check efficiency** beside the completed analysis.

When no API key is configured, the feature returns HTTP 503 with setup guidance; the rest of Axioma continues to work.

## Data and evidence

The button is available beside a completed Axioma report. Clicking it sends the saved problem statement, numbered source code, and a bounded evidence summary to Google's Gemini API. The summary includes recorded pass/fail/skip totals, selected detected code signals, and up to five failing cases with their diagnostic, exact runtime location when captured, saved input, and expected/observed values. Don't send private code or personal data unless you are comfortable with Google's current API terms and data handling. The API key remains on the server. This hosted API path needs network access and an API key; it does not run model weights on the local GPU. Google states that free-tier content may be used to improve its products. Review the current official terms before using it with sensitive code.

Gemma now compares the submitted approach with Axioma's saved time-complexity estimate and returns one of three verdicts: improvement recommended, no improvement needed, or unable to assess. When it recommends an improvement, it explains the alternative idea and gives expected time and auxiliary-space complexity (for example, replacing a pairwise Two Sum scan with a hash map for expected O(n) time and O(n) auxiliary space). It may also report the current approach's auxiliary-space complexity when the code supports an estimate. Auxiliary-space estimates exclude input and returned output, and remain unverified model advice; they are distinct from Axioma's optional measured-memory observation. Axioma's own time estimate is already displayed in the report, so Gemma does not repeat it. The response omits generic no-evidence filler and shows alternative complexity only when Gemma recommends an improvement.

For failed runs, Gemma may also return a likely cause, location, small fix to try, and why. Axioma-captured compiler/runtime locations are shown as exact execution evidence. For logical wrong answers, any line suggested by Gemma is explicitly unverified because a test mismatch does not uniquely identify a faulty line. Gemma's suggestions are not executed or verified, and the existing local analysis remains available without any model provider.

Gemma 4 model weights are published under Apache 2.0 according to Google's model card. Hosted Gemini API service conditions are separate from redistributing or running those weights. Axioma's own application source is covered by the repository's MIT license.
