# Apartment Search Bot v1

Lean Python core for an apartment-search workflow driven by n8n, with business logic kept outside n8n.

## Proposed File Tree

```text
.
├── .env.example
├── README.md
├── pyproject.toml
├── data/
│   └── geo/
│       ├── peninsula_gyms.csv
│       ├── sf_gyms.csv
│       └── sf_polygons.geojson
├── src/
│   └── apartment_bot/
│       ├── __init__.py
│       ├── adapters/
│       │   ├── apartments_com.py
│       │   ├── base.py
│       │   ├── craigslist.py
│       │   └── zillow.py
│       ├── config.py
│       ├── api.py
│       ├── core/
│       │   ├── decisioning.py
│       │   ├── filtering.py
│       │   ├── models.py
│       │   ├── normalize.py
│       │   ├── presentation.py
│       │   ├── scoring.py
│       │   ├── sms.py
│       │   └── state.py
│       │   └── store.py
│       ├── geo/
│       │   ├── loader.py
│       │   └── logic.py
│       ├── integrations/
│       │   ├── google_sheets.py
│       │   ├── outreach.py
│       │   ├── twilio.py
│       │   └── twilio_webhook.py
│       └── orchestration/
│           ├── cli.py
│           ├── handlers.py
│           └── pipeline.py
│           ├── sample_data.py
│           └── server.py
└── tests/
```

## What Is Implemented

- Typed dataclass-based models for listings, geo inputs, scoring, decisioning, SMS commands, dashboard rows, and multi-user state.
- Pure-Python geo loading from `sf_polygons.geojson`, `sf_gyms.csv`, and `peninsula_gyms.csv`.
- SF qualification logic:
  - listing must be inside one of the SF polygons
  - and either within `SF_GYM_THRESHOLD_MILES` of an SF gym or have `has_fitness_center=True`
- Peninsula qualification logic:
  - listing must be within `PENINSULA_GYM_THRESHOLD_MILES` of a Peninsula gym
  - threshold is config-driven so a routing API can replace straight-line distance later
- Hard-filter logic for must-haves and hard exclusions.
- Score model with configurable score-band decisioning:
  - `high` -> SMS + dashboard
  - `medium` -> dashboard only
  - `low` -> ignore
- SMS command parsing for `1/schedule`, `2/save`, `3/pass`, `4/more`, including whitespace trimming and case-insensitive handling.
- Shared-state logic with explicit per-user actions and derived overall status:
  - schedule beats save
  - pass beats save
  - duplicate scheduling is blocked
- Lean orchestration entrypoints so n8n can call Python rather than reimplementing rules.
- Minimal HTTP API for n8n:
  - `POST /evaluate-listings`
  - `POST /handle-reply`
- Local JSON-backed state store for v1 under `data/runtime/`.
- Seed-listing mode for the provided sample URLs so the workflow can be exercised before real scraping is implemented.

## What Is Stubbed

- Zillow adapter
- Craigslist adapter
- Apartments.com adapter
- Twilio outbound delivery
- Twilio webhook signature validation and listing-reply correlation
- Direct Google Sheets persistence from Python
- Outreach delivery path selection and actual contact send

These stubs are intentional. The integration seams exist, but production wiring is left behind clear TODOs where credentials, selectors, sheet IDs, webhook URLs, and contact-path details are still unknown.

## Setup

1. Create a virtualenv and install the package:

```bash
cd "/Users/shanewilson/Documents/New project"
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

2. Copy `.env.example` to `.env` and fill in the real values.

3. Put the geo input files here:

```text
/Users/shanewilson/Documents/New project/data/geo/sf_polygons.geojson
/Users/shanewilson/Documents/New project/data/geo/sf_gyms.csv
/Users/shanewilson/Documents/New project/data/geo/peninsula_gyms.csv
```

Expected CSV columns:

- `name`
- `lat` or `latitude`
- `lng` or `longitude` or `lon`

## Run

Use the simple CLI to confirm the geo files load:

```bash
cd "/Users/shanewilson/Documents/New project"
python -m apartment_bot.orchestration.cli
```

It prints counts for the polygons and gym points it loaded.

Run the local API for n8n:

```bash
cd "/Users/shanewilson/Documents/New project"
python -m apartment_bot.orchestration.server
```

Available endpoints:

- `GET /health`
- `POST /evaluate-listings`
- `POST /handle-reply`

`/handle-reply` returns a `dashboard_row` object after each valid action so n8n can immediately append/update the shared Google Sheet with the latest `status`, `shane_action`, and `wife_action`.

The current API uses seed fixtures for the sample Zillow, Craigslist, and Apartments.com URLs you provided. This is intentional for v1 wiring. Real scraping and normalization for those sources are still TODO.

## n8n Fit

Recommended v1 split:

1. n8n source trigger or cron invokes Python fetch/evaluate step.
2. Python returns:
   - listings to alert
   - listings to write to dashboard
   - filtered-out listings with reasons if desired
3. n8n handles transport:
   - call Twilio send node or Python Twilio client
   - call Google Sheets node or Python sheets writer
4. Twilio webhook routes inbound replies back into the Python reply handler.

This keeps n8n as the orchestrator, while Python owns the apartment logic.

## Notes

- The geo asset files were not present in the accessible workspace during scaffolding, so the loader is implemented against the expected filenames and will raise a clear `FileNotFoundError` until those files are placed in `data/geo/`.
- No Facebook Marketplace, Supabase, or routing API support has been added.
