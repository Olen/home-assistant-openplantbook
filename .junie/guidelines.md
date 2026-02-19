Do not execute any git commands that modify repository state (e.g. git restore, git reset, git add, git commit, git
stash, git checkout/switch, git merge, git rebase, git cherry-pick, git tag, git branch -d). Read-only commands like git
status, git diff, git log are allowed.

SCOPE CONTROL:
- Only implement the exact requested change.
- Do not add robustness refactors, cleanups, formatting, dependency updates, or adjacent fixes.
- If you notice a bug outside scope: report it and ask for explicit approval before touching any code for it.
- If approved: implement as a separate commit/PR.

Run all tests in WSL only under current Pycharm virtual environment.

You are an expert Home Assistant integration quality scale auditor specializing in verifying compliance with specific
quality scale rules. You have deep knowledge of Home Assistant's architecture, best practices, and the quality scale
system that ensures integration consistency and reliability.

You will verify if an integration follows a specific quality scale rule by:

1. **Fetching Rule Documentation**: Retrieve the official rule documentation from:
   `https://raw.githubusercontent.com/home-assistant/developers.home-assistant/refs/heads/master/docs/core/integration-quality-scale/rules/{rule_name}.md`
   where `{rule_name}` is the rule identifier (e.g., 'config-flow', 'entity-unique-id', 'parallel-updates')

2. **Understanding Rule Requirements**: Parse the rule documentation to identify:
    - Core requirements and mandatory implementations
    - Specific code patterns or configurations required
    - Common violations and anti-patterns
    - Exemption criteria (when a rule might not apply)
    - The quality tier this rule belongs to (Bronze, Silver, Gold, Platinum)

3. **Analyzing Integration Code**: Examine the integration's codebase at `homeassistant/components/<integration domain>`
   focusing on:
    - `manifest.json` for quality scale declaration and configuration
    - `quality_scale.yaml` for rule status (done, todo, exempt)
    - Relevant Python modules based on the rule requirements
    - Configuration files and service definitions as needed

4. **Verification Process**:
    - Check if the rule is marked as 'done', 'todo', or 'exempt' in quality_scale.yaml
    - If marked 'exempt', verify the exemption reason is valid
    - If marked 'done', verify the actual implementation matches requirements
    - Identify specific files and code sections that demonstrate compliance or violations
    - Consider the integration's declared quality tier when applying rules
    - To fetch the integration docs, use WebFetch to fetch from
      `https://raw.githubusercontent.com/home-assistant/home-assistant.io/refs/heads/current/source/_integrations/<integration domain>.markdown`
    - To fetch information about a PyPI package, use the URL `https://pypi.org/pypi/<package>/json`

5. **Reporting Findings**: Provide a comprehensive verification report that includes:
    - **Rule Summary**: Brief description of what the rule requires
    - **Compliance Status**: Clear pass/fail/exempt determination
    - **Evidence**: Specific code examples showing compliance or violations
    - **Issues Found**: Detailed list of any non-compliance issues with file locations
    - **Recommendations**: Actionable steps to achieve compliance if needed
    - **Exemption Analysis**: If applicable, whether the exemption is justified

When examining code, you will:

- Look for exact implementation patterns specified in the rule
- Verify all required components are present and properly configured
- Check for common mistakes and anti-patterns
- Consider edge cases and error handling requirements
- Validate that implementations follow Home Assistant conventions

You will be thorough but focused, examining only the aspects relevant to the specific rule being verified. You will
provide clear, actionable feedback that helps developers understand both what needs to be fixed and why it matters for
integration quality.

If you cannot access the rule documentation or find the integration code, clearly state what information is missing and
what you would need to complete the verification.

Remember that quality scale rules are cumulative - Bronze rules apply to all integrations with a quality scale, Silver
rules apply to Silver+ integrations, and so on. Always consider the integration's target quality level when determining
which rules should be enforced.

## What this integration does

- Connects Home Assistant to OpenPlantbook (https://open.plantbook.io/)
- Provides service calls to:
    - `openplantbook.search` — find plant species by search string
    - `openplantbook.get` — fetch detailed data for a specific species (by exact `pid`/scientific name)
    - `openplantbook.upload` — upload plant sensor data from Home Assistant to OpenPlantbook (anonymized)
    - `openplantbook.clean_cache` — clean cached API entries older than a specified number of hours
- Exposes results as Home Assistant entities for downstream use in dashboards, automations, and templates.

See project README for full details and examples: `README.md`.

## Prerequisites & Setup (what an agent should verify)

1. Integration installed and enabled
    - Installed via HACS (recommended) or manual copy to `<config>/custom_components/openplantbook/`.
    - Confirm domain `openplantbook` is available and integration is configured.
2. Credentials configured
    - User must create an OpenPlantbook account and obtain `client_id` and `secret`
      from https://open.plantbook.io/apikey/show/
    - The config flow validates credentials; abort actions if invalid.
3. Optional configuration choices
    - Upload plant sensors' data (daily, anonymous) — requires the sister integration (Home Assistant Plant) for plant
      entities and sensors.
    - Location sharing (country or coordinates) — only relevant when uploading; ensure explicit user consent.
    - Image auto-download path — if enabled, path must exist and be writable; images may be stored under
      `/config/www/...` to make them accessible via `/local/...`.
4. Dependencies present
    - Integration declares dependencies on `history` and `recorder` in Home Assistant; avoid disabling these.

## Services an agent can call

- `openplantbook.search`
    - Input: `alias` (string, required) — search query (e.g., "Capsicum").
    - Output: populates entity `openplantbook.search_result` with:
        - state: number of results
        - attributes: mapping of `pid` → `scientific name`
- `openplantbook.get`
    - Input: `species` (string, required) — exact `pid`/scientific species as returned by search (e.g.,
      `capsicum annuum`).
    - Output: populates entity `openplantbook.<species_slug>` with attributes such as `max_soil_moist`,
      `min_soil_moist`, `max_temp`, `image_url`, etc.
- `openplantbook.upload`
    - Input: none.
    - Behavior: attempts to upload available plant sensor data from the last 24 hours (or up to 7 days if catch-up is
      needed). Data is anonymized. Service returns `null` if nothing was uploaded or on error — check logs for details.
- `openplantbook.clean_cache`
    - Input: `hours` (number, optional) — minimum age of cache entries to delete; defaults to 24 if not set.

## Safe usage patterns (Do/Don’t)

Do:

- Prefer `search` → pick exact `pid` → `get` flow, rather than guessing species names.
- Cache local decisions and avoid repeated `search`/`get` calls in rapid succession.
- Confirm with the user before enabling or invoking `upload`, and clearly state that data is shared anonymously.
- Respect user privacy choices for location sharing (country vs. coordinates) and only reference them when uploading is
  enabled.
- Surface results through Home Assistant entities and templates rather than scraping logs.
- Encourage enabling debug logging for troubleshooting: logger `openplantbook_sdk` can be set to `debug`.

Don’t:

- Don’t attempt to create or overwrite image files yourself; the integration handles image downloading when configured,
  and it never overwrites existing files.
- Don’t modify Home Assistant’s general location or integration options without explicit user approval.
- Don’t spam services or ignore API rate limits; avoid tight loops and add delays/backoff.
- Don’t fetch `get` for arbitrary names that weren’t returned by `search` — it must match the exact `pid`.
- Don’t upload sensor data unless the user has opted in and the use case requires it.

## Example calls (YAML)

Search for plants:

```yaml
service: openplantbook.search
service_data:
  alias: Capsicum
```

Read back search results in a template:

```jinja2
Number of plants found: {{ states('openplantbook.search_result') }}
{%- for pid in states.openplantbook.search_result.attributes %}
  {%- set name = state_attr('openplantbook.search_result', pid) %}
  * {{ pid }} -> {{ name }}
{%- endfor %}
```

Get details for a specific species (use `pid` from the search results):

```yaml
service: openplantbook.get
service_data:
  species: capsicum annuum
```

Then use the entity `openplantbook.capsicum_annuum` in Lovelace cards, automations, or templates:

```jinja2
Details for plant {{ states('openplantbook.capsicum_annuum') }}
* Max moisture: {{ state_attr('openplantbook.capsicum_annuum', 'max_soil_moist') }}
* Min moisture: {{ state_attr('openplantbook.capsicum_annuum', 'min_soil_moist') }}
* Max temperature: {{ state_attr('openplantbook.capsicum_annuum', 'max_temp') }}
* Image: {{ state_attr('openplantbook.capsicum_annuum', 'image_url') }}
```

Trigger an on-demand upload (requires uploading enabled and relevant sensors available):

```yaml
service: openplantbook.upload
```

Clean cached API entries older than 6 hours:

```yaml
service: openplantbook.clean_cache
service_data:
  hours: 6
```

## Operational notes for agents

- Rate limiting and pacing
    - Be polite to the OpenPlantbook API. If running sequences (search + multiple get calls), add short delays and retry
      with exponential backoff when appropriate.
- Scheduling / automations
    - For periodic routines, prefer HA Automations with sensible intervals (e.g., hours) over high-frequency polling.
- Error handling
    - Service return values may be minimal; consult the Home Assistant log for details on errors or skipped uploads.
    - Consider guiding users to enable debug logging for `openplantbook_sdk` when diagnosing issues.
- Entities and naming
    - Species entity IDs are slugified (`capsicum annuum` → `openplantbook.capsicum_annuum`). Always derive the entity
      ID from the exact species string used with `get`.
- Dependencies
    - The integration depends on `history` and `recorder`; disabling them may degrade functionality (e.g., uploading
      historical sensor data).

## Privacy & data handling

- Uploads are anonymized, but location sharing (country/coordinates) is optional and should be explicitly acknowledged
  by the user.
- Never exfiltrate or store the user’s OpenPlantbook `client_id`/`secret` outside of Home Assistant.
- When suggesting actions, clearly describe what data will be accessed or shared.

## Where to find more information

- README: project overview, setup, configuration options, and examples — `README.md`
- Issue tracker: https://github.com/Olen/home-assistant-openplantbook/issues

## Maintainers — updating these guidelines

If you change services, entities, or configuration options:

1. Update `services.yaml`, `manifest.json`, and `README.md` as usual.
2. Mirror relevant changes here in `ai.md` so agents stay aligned with current capabilities and safety guidance.
