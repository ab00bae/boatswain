# boatswain

A CLI that pulls issues and pull requests from a GitHub repository and writes a
sprint status report — what closed, what is still open, and what has gone quiet.
It automates a status roundup that is otherwise done by hand every two weeks.

```
boatswain report --repo fastapi/typer --sprint-days 14

fastapi/typer  2026-08-01 → 2026-08-15  (14 days)

 Metric              │         Count
─────────────────────┼───────────────
 Issues opened       │             0
 Issues closed       │             0
 Net change          │ 0 (unchanged)
 Issues still open   │             1
─────────────────────┼───────────────
 PRs opened          │            13
 PRs merged          │            14
 PRs closed unmerged │             2
 PRs still open      │            40
 Merge rate          │           88%

 Stale — open, untouched
      for 14+ days
   # │ Title      │ Idle
─────┼────────────┼──────
 678 │ 🚀 Roadmap │ 364d

Most active  tiangolo (10), wterrr (1)
```

## What this demonstrates

| Practice | Where to look |
| --- | --- |
| Third-party REST integration, with pagination | [`boatswain/github.py`](boatswain/github.py) |
| Credential handling with sensible fallbacks | [`github.py`](boatswain/github.py) — `resolve_token` |
| Aggregation logic isolated from I/O and the clock | [`boatswain/aggregate.py`](boatswain/aggregate.py) |
| Actionable error messages per failure mode | [`github.py`](boatswain/github.py) — `_raise_for_status` |
| Tests against a mock transport — no live network | [`tests/test_github.py`](tests/test_github.py) |
| Clean CLI UX: subcommands, flags, help text | [`boatswain/cli.py`](boatswain/cli.py) |

## Design decisions

**It takes two requests, not one.** GitHub's `/issues` endpoint accepts a
`since` filter, but that filter matches on *updated* time. A single filtered
call therefore returns only recently-touched items — silently omitting the open
issues nobody has looked at in months, which are exactly the ones a staleness
report exists to find. So `boatswain` asks for every open item, plus everything
closed inside the window, and merges the two.

The sample output above shows why: issue #678 has been idle for 364 days. Any
`since`-filtered request for a two-week sprint would have missed it.

**Pull requests are not issues.** GitHub returns both from `/issues`, with pull
requests distinguished only by the presence of a `pull_request` key. Treating
them as one inflates every issue count in the report. They are split at the
boundary and counted separately, and a test pins that behaviour.

**A merge rate of "no data" is not 0%.** A repository with nothing closed yet
has an undefined merge rate, so the row is omitted rather than printed as 0%,
which would read as "everything was rejected".

**Staleness is idleness, not age.** An issue opened two years ago and commented
on yesterday is alive. The report ranks by how long an issue has been untouched.

**Bots are excluded from contributor counts.** Otherwise `dependabot[bot]` tops
every ranking and the number says nothing about the team.

**Output is forced to UTF-8.** GitHub titles routinely contain emoji. On Windows
a redirected stdout defaults to cp1252, so the tool would work interactively and
then crash the moment anyone piped it into a file — which is the main thing a
report generator gets used for.

## Quickstart

Requires Python 3.11+.

```bash
git clone https://github.com/ab00bae/boatswain.git
cd boatswain

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

boatswain report --repo fastapi/typer
```

### Authentication

Unauthenticated requests work against public repositories but hit a low rate
limit. A token is found in this order:

1. `--token`
2. `GITHUB_TOKEN`, then `GH_TOKEN`
3. `gh auth token` — so anyone already signed in with the GitHub CLI needs no
   setup at all

## CLI demo

`demo.sh` runs against a saved payload with a pinned date, so it needs no token,
no network, and produces identical output on every machine.

```bash
./demo.sh
```

```
Issues and pull requests are counted separately
  PASS  13 pull requests opened in the window
  PASS  0 issues opened — PRs are not miscounted as issues

Stale detection reaches outside the window
  PASS  the year-old open issue is surfaced
  PASS  its idle time is reported

Summary
  16/16 checks passed
```

## Usage

| Flag | Purpose |
| --- | --- |
| `--repo owner/name` | Repository to report on (required) |
| `--sprint-days N` | Length of the reporting window (default 14) |
| `--stale-days N` | Idle days before an open issue counts as stale (default 14) |
| `--out PATH` | Also write the report as markdown |
| `--token TOKEN` | GitHub token, overriding the environment and `gh` |
| `--now ISO8601` | Treat this instant as the present, to reproduce a past sprint |
| `--fixture PATH` | Read a saved payload instead of calling the API |

Writing a report to a file:

```bash
boatswain report --repo ab00bae/quartermaster --sprint-days 7 --out sprint.md
```

## Tests

```bash
pytest
```

59 tests, none of which touch the network — the client is exercised against
`httpx.MockTransport`, and every date is pinned so the counts are exact rather
than relative to when the suite happens to run.

## Project layout

```
boatswain/
  cli.py          Typer command, argument handling, UTF-8 output
  github.py       the only module that makes network calls
  models.py       Item and Report — plain dataclasses
  aggregate.py    pure summarisation over Items
  render.py       terminal tables and markdown, from one Report
data/
  sample-issues.json   saved payload for the offline demo
tests/            59 tests, all offline
demo.sh           scripted end-to-end demo
```

## License

[MIT](LICENSE)
