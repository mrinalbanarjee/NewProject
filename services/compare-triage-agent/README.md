# compare-triage-agent

Agentic assistant for diagnosing Hogan/Alfa customer-sync issues. Wraps two tools
around Gemini's function-calling loop (`google-genai`):

- `list_customer_compare_mismatches` - every attribute that doesn't match between
  Hogan and Alfa, from a customer compare run (`customercompareresults.json`).
- `get_account_compare_root_cause` - **ACCOUNT_COMPARE only** for now. For each
  mismatched account under an ECN, joins the Hogan account boarding status
  (`HoganAccountBoardingStatusResponse.json`) as the primary failure, then pulls
  every `FailureListResponse.json` entry for that same ECN + account whose
  `eventTimeStamp` falls *after* the boarding response's `eventTime` - the
  downstream failures the boarding problem caused.

Other compare categories (`PHONE_COMPARE`, `ADDRESS_COMPARE`, `NAME_COMPARE`, ...)
are visible in the mismatch list but intentionally have no root-cause tool yet;
the agent is instructed to say so rather than improvise one.

## Project layout

```
data/                                    Sample fixtures the tools read by default
src/compare_triage_agent/
  data_sources.py    Loads + caches the three JSON exports (paths overridable via env)
  tools.py           The two tool functions + their JSON-schema tool declarations
  models.py          Pydantic shapes returned by the tools
  agent.py           The Gemini function-calling loop (system prompt + dispatch)
  cli.py             Interactive REPL entry point
tests/test_tools.py  Unit tests against the bundled fixtures
```

## Setup

```bash
cd services/compare-triage-agent
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"
cp .env.example .env   # then fill in GEMINI_API_KEY
```

## Running

```bash
.venv/Scripts/python.exe -m compare_triage_agent.cli
```

Example session:

```
> list all the attributes that don't match between hogan and alfa
> check the root cause for ACCOUNT_COMPARE on ecn 0444769043821
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
