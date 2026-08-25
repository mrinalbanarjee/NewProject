# ALA Reconciliation Assistant

Agentic assistant covering two separate jobs, never blended in one request - a chat
guided by a two-level clickable menu, running on **OpenAI, Google (Gemini), or
Anthropic**, bring-your-own-token. Package/directory name (`compare-triage-agent` /
`compare_triage_agent`) is unchanged - only the app's display name (browser tab,
page header, CLI greeting, API title) is "ALA Reconciliation Assistant".

- **Reconciliation** - diagnosing Hogan/Alfa customer-sync issues.
- **Feature Management** - reading and changing the LoanBoarding, CustomerSync, and
  AccountSync app-config sections (`TriageApi.Api/appsettings.json`).

Reconciliation tools:
- `list_customer_compare_mismatches` - every attribute that doesn't match between
  Hogan and Alfa, from a customer compare run (`customercompareresults.json`).
- `get_account_compare_root_cause` - **ACCOUNT_COMPARE only**. Primary boarding status
  and dependent failures, narrated, with no reprocessability verdict.
- `classify_account_compare_failures` - everything `get_account_compare_root_cause`
  returns, plus a `canBeReprocessed` verdict and a recommendation for every dependent
  failure (see "Reprocess classification" below).
- `generate_reprocess_script` - builds the targeted Mongo reprocess script once the
  user has settled on which correlationIds to reprocess.

Feature Management tools (`config_tools.py` - see below):
- `get_app_config_value` - reads a config section, or one key within it.
- `generate_config_update_script` - builds the Mongo script to change one key -
  never edits the file directly.

Other compare categories (`PHONE_COMPARE`, `ADDRESS_COMPARE`, `NAME_COMPARE`, ...)
are visible in the mismatch list but intentionally have no root-cause tool yet;
the agent is instructed to say so rather than improvise one.

These are three separate, deliberately-scoped answers, not stages of one pipeline -
each only fires on the matching, specific ask, and none of them auto-chains into the
next:
- "what's not in sync for ecn X" / "any Hogan sync issues for ecn X" -> mismatch
  summary only, even if some of the mismatches are ACCOUNT_COMPARE. Stops there.
- "check root cause for ACCOUNT_COMPARE on ecn X" -> `get_account_compare_root_cause`
  only - boarding status + dependent failures, no reprocessability verdict, no script offer.
- "give me a reprocess recommendation for ecn X" -> `classify_account_compare_failures`
  - the canBeReprocessed verdicts, the checkbox picker (see below), and the eventual
  script all live behind this explicit ask, not the two narrower ones above.

## Guided menu

The welcome message has two clickable buttons - **Reconciliation** and **Feature
Management** - purely client-side, no round trip to the model. Clicking Feature
Management renders a second-level submenu (**Loan Boarding** / **Customer Sync** /
**Account Sync**), also client-side. Only a leaf pick composes and sends a plain chat
message through the normal pipeline (e.g. "I'd like to do Feature Management for
LoanBoarding. Show me the current configuration.") - the menu is just a shortcut for
typing that sentence yourself; free-form chat works identically at any point.

## Feature Management

`config_tools.py` reads directly from the live `TriageApi.Api/appsettings.json`
(path overridable via `TRIAGE_API_APPSETTINGS_PATH`) - both tools are pure/
deterministic, no LLM call needed, same as `reprocess.py`.

- **Get** (`get_app_config_value`): returns a whole section or one key's current
  value. "list of dealers set for loan boarding" -> `config=LoanBoarding,
  key=Dealers`. Each tool's description embeds every known key per section, so the
  model maps colloquial wording onto the real key without guessing blindly.
- **Update** (`generate_config_update_script`): never edits the file - returns a
  Mongo script instead, same copy/download-rendered block the reprocess flow uses
  (`ChatResponse.mongo_script` - the field is provider-agnostic now, populated by
  *any* tool result carrying a `script` key, not just the reprocess one; see
  `providers.py`). Each section has its own explicit collection name, distinct from
  the section name - `LoanBoarding` -> `LoanBoardingConfig`, `CustomerSync` ->
  `CustomerAppConfig`, `AccountSync` -> `AccountSyncSummaryConfig` (`config_tools.
  _COLLECTION_NAMES`) - targeting a `{"_id": "<Section>"}` document in each.
  `operation` is `set` for a scalar/boolean key, or `add_to_list`/`remove_from_list`
  for one item in a list-typed key (e.g. `Dealers`).
- **Type safety**: the tool's `value` parameter is always a plain string (keeps the
  schema simple across providers), but the script's Mongo literal is rendered to
  match the *existing* value's type, not guessed from the string's own shape - dealer
  codes like `"93159"` are strings in the data despite looking numeric, so `"add
  dealer 12345"` renders `$addToSet: { "Dealers": "12345" }` (quoted), not a bare
  number. Guessing from the string alone would've been a real, silent bug here: a
  later `remove_from_list` "93159" wouldn't match a differently-typed array entry.

## Bring your own token

The chat UI has a provider dropdown (OpenAI / Google / Anthropic) and an API key
field. The key is stored only in the browser's `localStorage` (one per provider,
so switching providers doesn't lose the others) and sent with each chat request -
it's never written to disk or logged server-side. Leave the field blank to fall
back to that provider's key in the server's `.env`, if one is configured there
(handy for local dev so you don't have to paste a key every time).

## Model routing

Each provider has two model tiers - `fast` and `reasoning` - and every query is
classified into one before it runs (`router.classify_query`): a flat "what
doesn't match" lookup only needs `fast`; anything that smells like "why", "root
cause", "resolve", or "walk me through" gets `reasoning`, since that path chains
a tool call, cross-references timestamps across two data sources, and narrates a
resolution. The chat UI shows which model and tier actually served each reply.

If a provider reports the tier's model doesn't exist (renamed, retired - this
happened mid-project with a Gemini model), the dispatcher retries once on that
provider's `fast`-tier model automatically rather than failing the turn outright.

Tier models are hardcoded defaults, all overridable via env var (see
`.env.example`) - `OPENAI_FAST_MODEL`, `GOOGLE_REASONING_MODEL`, etc.

## Reprocess classification

**Classify** (`classifier.py`): for an ECN (+ optional account number), every
dependent failure on every mismatched ACCOUNT_COMPARE account is classified by
the LLM into exactly one of two categories, using a JSON schema *forced* on
the response (not just prompted) - `response_format=json_schema` on OpenAI,
`response_json_schema` on Gemini, and a single pinned tool call on Anthropic
(which has no native structured-output mode):
- **Collateral / Dependency Failure** (`canBeReprocessed: true`) - blocked by
  the account not being boarded yet; should clear once the primary boarding
  issue is fixed.
- **Inherent Data Validation Failure** (`canBeReprocessed: false`) - the
  payload itself is bad; reprocessing without a source-data fix will fail again.

The primary boarding status (succeeded/failed, its summary) is given to the model
as context, but the classification hinges on what each failure's own text says - a
bad phone number is still `false` even if boarding also failed. Same fast-tier
fallback as the chat path if the reasoning-tier model doesn't exist.

Entirely conversational, no separate screen: `toolset.py` wires
`classify_account_compare_failures` and `generate_reprocess_script` into the same
tool-calling loop as the other two tools - see "Bring your own token" above for the
one and only chat entry point. Since only a turn's *final text* persists across
turns (see providers.py), the model is instructed to always show each failure's
full correlationId in its reply - that text is the only place it can recover those
ids from on a later turn.

Whenever a turn calls `classify_account_compare_failures`, the backend also hands
the raw result to the frontend (`ChatResponse.classification`, alongside the
model's own prose), which renders a compact checkbox list under that message - one
row per dependent failure, pre-checked exactly where the model said
`canBeReprocessed: true`, editable before reprocessing. Clicking "Generate Reprocess
Script" doesn't call a separate endpoint - it just composes a plain chat message
naming the checked correlationIds and sends it through the normal pipeline, so the
model calls `generate_reprocess_script` itself and the whole thing stays one
conversation. When that tool runs, its result (`ChatResponse.mongo_script`)
renders as a dedicated block with **Copy** and **Download** buttons - the model's
own reply is instructed not to repeat the full script text, to avoid showing it twice.

**Generate script** (`reprocess.py`): pure templating, no LLM - builds a
`db.customerevent.updateMany(...)` targeting the primary boarding correlationId
plus whatever's selected, setting `status: "Reprocess"`.

## Project layout

```
data/                                    Sample fixtures the tools read by default
src/compare_triage_agent/
  data_sources.py    Loads + caches the three JSON exports (paths overridable via env)
  tools.py           The plain data tools (mismatches, root cause) + JSON-schema declarations
  classifier.py      Forced-JSON-schema canBeReprocessed classification, per provider
  reprocess.py       Mongo reprocess-script template generator (no LLM)
  config_tools.py    Feature Management: get/update-script tools for LoanBoarding /
                     CustomerSync / AccountSync app config (no LLM)
  toolset.py         Combines tools.py + classifier.py + reprocess.py + config_tools.py
                     into the one registry the chat loop dispatches against
  models.py          Pydantic shapes returned by the tools
  message_catalog.py Turns raw Hogan/failure-feed codes into plain-English summaries
  prompts.py         The one system prompt shared by every provider
  router.py          Query -> tier classification, tier -> model resolution
  providers.py       One tool-calling turn-runner per provider SDK, same signature
  agent.py           Top-level dispatcher: resolves the API key, tier, and model,
                     runs the provider, retries on a stale model id
  cli.py             Interactive REPL entry point
  web.py             FastAPI backend (BYOT-aware) - one endpoint: /api/chat
  static/            The chat UI (index.html / style.css / app.js)
tests/               Unit tests against the bundled fixtures and the router/agent logic
```

## Setup

```bash
cd services/compare-triage-agent
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"
cp .env.example .env   # optional - only needed if you want a server-side fallback key
```

## Running

Web chat UI (has the provider/API-key picker):

```bash
.venv/Scripts/python.exe -m compare_triage_agent.web
```

Then open `http://127.0.0.1:8000`.

CLI (reads `COMPARE_AGENT_PROVIDER` / `COMPARE_AGENT_API_KEY` env vars, defaults to Google):

```bash
.venv/Scripts/python.exe -m compare_triage_agent.cli
```

Example queries either way:

```
list all the attributes that don't match between hogan and alfa for ecn 0444769043821
check the root cause for ACCOUNT_COMPARE on ecn 0444769043821
give me a reprocess recommendation for ecn 0444769043821
reprocess the ones you said were safe

show me the list of dealers set for loan boarding
add dealer 12345 to loan boarding
remove dealer 93159 from loan boarding
set the customer sync max retry count to 5
turn off day 1 throttling for loan boarding
```

## Testing

```bash
.venv/Scripts/python.exe -m pytest
```

## Swapping in live data

The three JSON exports are read through `data_sources.py`. Point `COMPARE_RESULTS_PATH`,
`BOARDING_STATUS_PATH`, and `FAILURE_LIST_PATH` at fresher files (or replace the loader
functions with real API calls, e.g. against `TriageApi`) without touching `tools.py` -
the tool contracts stay the same either way.

## Known gaps

- Root-cause lookup only covers `ACCOUNT_COMPARE`. Extending to `PHONE_COMPARE` etc.
  needs the equivalent "what's the primary source-of-truth failure for this category"
  join defined first - there's no boarding-status-shaped signal for those the way
  there is for accounts.
- Reads flat JSON files rather than calling `TriageApi` (see `../../README.md`) -
  intentional for now per the current ask; the tool functions are the seam to swap
  in real API calls later.
- The `reasoning`-tier defaults for OpenAI (`gpt-4o`) and Google (`gemini-3.6-pro`)
  are best-effort guesses, not live-verified the way `gpt-4o-mini`/`gemini-3.6-flash`
  were - the fast-tier fallback (see above) covers for this if either is wrong, but
  expect that fallback to fire until someone confirms/updates the real model id.
- In-memory session store (`_sessions` in `web.py`) - fine for one local process,
  not for multiple workers or surviving a restart.
- The primary boarding event has no `requestMessageType` in this data (it's a
  Hogan boarding response, not an OXCU customer-maintenance message) - the
  reprocess script labels its line "Primary Boarding Message" by comment only,
  it doesn't claim an OXCU code for it the way the dependent failures have one.
- `config_tools.py` reads `TriageApi.Api/appsettings.json` directly, a file that
  lives outside this package - an intentional cross-project read (the whole point
  is to reflect that live file), but it does mean this service isn't fully
  self-contained the way `data_sources.py`'s bundled fixtures are.
- Feature Management's update tool only supports changing one existing key at a
  time (`set` on a scalar/boolean, or one item in/out of an existing list) - it
  won't add a brand-new config key or replace a whole list in one call.
