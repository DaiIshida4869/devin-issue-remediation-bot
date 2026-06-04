# Devin Issue Remediation Bot

An event-driven automation that turns a GitHub issue into a remediation pull request by
delegating the work to a [Devin](https://docs.devin.ai/api-reference/overview) session, then
tracks every delegated task so an engineering leader can see whether the workflow is working.

## Problem

Engineering teams accumulate a steady stream of small maintenance work: documentation gaps,
missing tests, minor code-quality issues, dependency bumps. Each item is low-risk but
collectively it drains senior-engineer time. This bot lets a team express such work as a
GitHub issue and hands it to Devin as an autonomous remediation worker, leaving humans to
review the result instead of doing the busywork.

## Solution

```text
GitHub Issue (labeled "devin-remediate")
  -> Event payload
  -> Python orchestrator
  -> Devin API session
  -> Devin remediation (branch + checks + PR)
  -> tasks.json + report.md
```

The orchestrator builds a tightly scoped prompt from the issue, opens a Devin session, and
records the session. A `poll` step later refreshes each session's status and captures the PR
URL, keeping `tasks.json` and `report.md` current.

## Architecture

| Component                                  | Responsibility                                                |
| ------------------------------------------ | ------------------------------------------------------------- |
| [app/event.py](app/event.py)               | Parse a GitHub `issues` webhook payload into a domain `Issue` |
| [app/prompt.py](app/prompt.py)             | Build the scoped remediation prompt and session title         |
| [app/devin_client.py](app/devin_client.py) | Wrap the Devin v3 sessions API (create / get / message)       |
| [app/task_store.py](app/task_store.py)     | Persist tasks to `data/tasks.json`                            |
| [app/report.py](app/report.py)             | Render `data/report.md` from tasks                            |
| [app/orchestrator.py](app/orchestrator.py) | Tie the pieces together: delegate, poll, report               |
| [app/cli.py](app/cli.py)                   | `remediate` / `poll` / `report` subcommands                   |

## Event trigger

The automation fires when a GitHub issue is labeled `devin-remediate`. This is wired as a
GitHub Actions workflow (`.github/workflows/remediate.yml`) that runs `on: issues: [labeled]`.
Because the `issues` event only fires in the repository that owns the issues, the workflow
lives in the **Superset fork** (not in this repo); it checks out this bot and runs it against
the live event payload GitHub provides at `$GITHUB_EVENT_PATH`.

That payload has the exact shape of [fixtures/issue_labeled_event.json](fixtures/issue_labeled_event.json),
so the same `remediate --event` code path runs identically whether it is driven by the live
Action or replayed locally from the fixture for a reproducible demo.

To deploy the trigger on the fork:

1. Add `.github/workflows/remediate.yml` to the fork's default branch, with its `repository:`
   field set to this bot's repo.
2. Add `DEVIN_API_KEY` and `DEVIN_ORG_ID` as Actions secrets on the fork.
3. Create the `devin-remediate` label and apply it to an issue — the workflow auto-fires.

## How Devin is used

Devin is the remediation worker, not a helper. Given a repository and an issue URL, it inspects
the code, makes the smallest safe change, runs checks when practical, and opens a pull request.
The Python service is only an orchestrator: it decides _what_ to delegate and records _what
happened_. The prompt is built in [app/prompt.py](app/prompt.py).

## Setup

```bash
uv sync
cp .env.example .env   # fill in DEVIN_API_KEY + DEVIN_ORG_ID
```

Environment variables (see [.env.example](.env.example)):

- `DEVIN_API_KEY` — Devin v3 service-user token (`cog_*`), created under Settings -> Devin API
- `DEVIN_ORG_ID` — organization id (`org-*`) shown on the same Devin API settings page
- `DEVIN_BASE_URL` — defaults to `https://api.devin.ai` (v3 paths are scoped per organization)
- `DATA_DIR` — output directory for `tasks.json` / `report.md` (defaults to `data`)

## Run locally (uv)

[fixtures/issue_labeled_event.json](fixtures/issue_labeled_event.json) is a saved copy of the
`issues.labeled` event for a real issue in the fork. The live Action uses the payload GitHub
provides automatically, so this file is only for local replay. To replay a different issue,
regenerate it from that issue rather than editing the body by hand:

```bash
gh issue view <N> --repo <owner>/superset --json number,title,body,url \
  | python3 -c 'import json,sys; s=json.load(sys.stdin); json.dump({"action":"labeled","label":{"name":"devin-remediate"},"issue":{"number":s["number"],"title":s["title"],"html_url":s["url"],"body":s["body"],"labels":[{"name":"devin-remediate"}]},"repository":{"full_name":"<owner>/superset"}}, open("fixtures/issue_labeled_event.json","w"), indent=2)'
```

```bash
# Simulate the production event from a fixture
uv run python main.py remediate --event fixtures/issue_labeled_event.json --require-label

# Refresh active sessions and update tasks.json / report.md
uv run python main.py poll

# Print the current report
uv run python main.py report
```

## Run with Docker

The image uses a multi-stage build (uv resolves dependencies in the builder stage; the runtime
stage carries only the virtualenv and app code).

```bash
docker build -t devin-remediation-bot .

# Smoke test — no credentials needed; prints an empty report
docker run --rm devin-remediation-bot report

# Delegate an issue to Devin (needs DEVIN_API_KEY + DEVIN_ORG_ID in .env)
docker run --rm --env-file .env -v "$PWD/data:/app/data" \
  devin-remediation-bot remediate --event fixtures/issue_labeled_event.json

# Refresh session status, then print the updated report
docker run --rm --env-file .env -v "$PWD/data:/app/data" \
  devin-remediation-bot poll
docker run --rm -v "$PWD/data:/app/data" devin-remediation-bot report
```

The `data` volume mount persists `tasks.json` and `report.md` on the host. The `report`
smoke test needs no secrets, so a reviewer can verify the image builds and runs immediately.

## Observability

- **`data/tasks.json`** — machine-readable state per delegated task: issue, status,
  Devin session id/url, PR url, timestamps.
- **`data/report.md`** — a human-readable table with a status summary line
  (e.g. `Completed: 2 | Failed: 1`) so a leader can see throughput and what needs attention.

A task is marked **completed once Devin opens a pull request** — the session often lingers in
`waiting_for_user` ("awaiting instructions") after the work is done, so the PR, not the session
state, is the success signal. Until a PR exists the status reflects the Devin session
(`session_created -> working / blocked`, or `failed` if it ends without one), mapped from v3's
`status` / `status_detail` in [app/models.py](app/models.py).

## Tests

```bash
uv run pytest
```

Tests cover event parsing, prompt construction, the task store, report rendering, the Devin
client (mocked HTTP), and the orchestrator (mocked Devin client) — 41 cases.

## Limitations

- This is a demo, not a production GitHub App. The event trigger is a GitHub Actions
  workflow on the fork (issue labeled `devin-remediate`), not a standalone hosted webhook
  receiver; the bundled fixture replays the same payload locally.
- No scheduler or dashboard; `poll` is run on demand.
- PR extraction relies on Devin reporting the PR on the session; complex multi-PR flows are out
  of scope.
- Scope was intentionally kept small to fit the 2–3 hour constraint.
