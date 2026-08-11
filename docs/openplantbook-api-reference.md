# Open Plantbook API — reference notes

Notes on the upstream API as **its author** documents it, for use when adding
to or debugging this integration. Not part of the integration itself.

Source: the *Open Plantbook* agent skill published by Slava Pisarevskiy
(@slaxor505), the Open Plantbook author, at
<https://clawhub.ai/slaxor505/skills/openplantbook> (v1.0.3, MIT-0, 2026-07).
Retrieved 2026-08-11. It is a skill for agents rather than a client library, so
it describes the HTTP surface directly and is worth reading as documentation
regardless of the packaging.

## Keeping up with API changes

The cloud's **release notes live in the README of
<https://github.com/slaxor505/OpenPlantbook-client>** — that repository is the
service's home ("Open Plantbook clients and UI"), not a client library, and its
frequent commits change nothing but that README. Releases are dated the same way
the API is versioned: `202605-25`, `202606-28`, `202607-08`, `202607-27`. Its
`python/`, `dotnet/` and `postman/` folders are example clients and are years
old; ignore them, they are unrelated to the SDK we depend on.

**Watch that README.** They are not tagged GitHub releases, so release
notifications do not cover them — watch the repository's commits. The notes say
in prose whether integrations need to do anything, which is more useful than
diffing the schema.

The **SDK pin** is already watched from the other side: `manifest-deps.yml`
checks the `manifest.json` requirements against PyPI daily and keeps a single
tracking issue (see
`docs/superpowers/specs/2026-06-19-manifest-dependency-monitoring-design.md`).
So a new SDK release finds us. What nothing watches is the **cloud** changing
underneath a stable SDK — which is what the README above is for.

`openplantbook-sdk-py` moving slowly is not neglect: recent cloud releases have
been additive or internal (the 202607-27 platform upgrade states outright that
existing client IDs and secrets keep working and no integration changes are
required), so there has been nothing for the SDK to do. It does mean the SDK
will not surface newly added endpoints on its own.

## The authoritative source is the live schema

```
https://open.plantbook.io/api/schema/
```

OpenAPI 3.0.3, API version `202606` as of the skill's last update. The skill's
own first rule is to consult this before anything that depends on the shape of
an endpoint or its payload — worth doing here too rather than inferring shapes
from our own call sites. Nothing in this repository references it today.

## Endpoints

| Method | Path | Used by this integration |
|---|---|---|
| `GET` | `/api/v1/plant/search` — by scientific/common name; `alias`, `userplant`, `limit`, `offset` | yes |
| `GET` | `/api/v1/plant/detail/{pid}/` — `lang`, `include` | yes |
| `POST` | `/api/v1/plant/create` — requires `display_pid` | **no** |
| `PATCH` | `/api/v1/plant/update` — requires `pid` + ≥1 attribute | **no** |
| `DELETE` | `/api/v1/plant/delete` — requires `pid` | **no** |
| `POST` | `/api/v1/sensor-data/instance` — register a plant instance | yes (`uploader.py`) |
| `POST` | `/api/v1/sensor-data/upload` — timeseries; supports `dry_run=true` | yes (`uploader.py`) |

`dry_run=true` on the upload endpoint is worth knowing about for testing.

**User-plant CRUD is the gap.** We read plants and push sensor data, but never
create or amend a user plant. An HA service that wrote thresholds back — from
what a plant has actually tolerated — would fit the plant ecosystem, and the
credentials for it are already configured.

## Authentication

- `OPENPLANTBOOK_API_KEY` — read-only.
- OAuth2 client credentials (`client_id` + `client_secret`) — what this
  integration asks for and what write operations require.

## Create/update fields

`display_pid` (≤100 chars) is the only required one. Everything else is
nullable with schema-specified bounds: `alias`, `category`, `sunlight`,
`watering`, `fertilization`, `pruning`, `soil`, `origin`, plus temperature,
light, humidity, soil moisture, electrical conductivity and PPFD ranges. Take
the exact constraints from the live schema, not from this table.

## Units the API validates against

temperature °C · soil EC µS/cm · humidity % · soil moisture % · light lux.

## House rules from the skill

- Honour HTTP 429 and its `Retry-After`.
- Never log or echo credentials.
- No HTML scraping or browser automation as an API fallback.
- Plant data is informational, not toxicity or medical advice.
