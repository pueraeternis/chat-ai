# Plan 10 - final repository quality cleanup

**Status:** Completed.
**Goal:** Resolve the remaining repository-quality issues before declaring the repository complete as a public flagship reference implementation.

**Scope:** Quality gates, status documentation, lightweight CI, and local developer verification only. No new product features, API behavior, architecture refactoring, deployment automation, or security scope.

**References:** [pyproject.toml](../../pyproject.toml), [uv.lock](../../uv.lock), [README.md](../../README.md), [docs/PROGRESS.md](../PROGRESS.md), [docs/INDEX.md](../INDEX.md), [docs/plans/07-public-reference-documentation.md](07-public-reference-documentation.md), [docs/plans/08-security-and-platform-boundaries.md](08-security-and-platform-boundaries.md), [docs/plans/09-api-contract-and-request-validation.md](09-api-contract-and-request-validation.md).

---

## 1. Objective

Finish the repository-quality cleanup needed after Plans 07, 08, and 09.

The target final state is:

- local quality gates are clean and reproducible;
- type-check tooling metadata is consistent;
- project status documentation reflects the implemented repository;
- a small public CI workflow verifies the same checks contributors run locally;
- local developer documentation explains the quality checks without adding process weight;
- no further planned engineering work remains after this cleanup.

This is a final acceptance plan, not a feature wave.

---

## 2. Motivation

The major engineering work is complete and the architecture audit found no blockers. The remaining issues are repository-quality issues rather than product or platform gaps.

At plan time, the repository is close to final portfolio quality but still has a few inconsistencies that can make it look unfinished:

- quality gate commands are referenced in plans and docs, but not fully aligned across dependencies, docs, and metadata;
- `basedpyright` has configuration in `pyproject.toml` and is referenced by plan validation commands, but is not listed in the dev dependency group or lockfile;
- status documentation lags behind completed work;
- there is no `.github/` workflow directory for public CI;
- README local development instructions only show `uv run pytest`, not the full local verification path.

These are small, high-signal cleanup items. Fixing them should make the repository easier to evaluate and safer to maintain without expanding scope.

---

## 3. Current state

Captured at plan time before implementation.

### Facts verified from the codebase

| Area | Current state |
|------|---------------|
| Architecture | The current architecture remains chat-proxy as the public FastAPI boundary, with vLLM, web-search MCP, and SearXNG treated as internal services. Plan 10 does not change this architecture. |
| Ruff | `pyproject.toml` configures Ruff with Python 3.12, line length 100, and lint rules under `[tool.ruff]`. |
| pytest | `pyproject.toml` configures pytest with `testpaths = ["tests"]` and `pythonpath = ["src", "open_webui"]`. |
| basedpyright config | `pyproject.toml` contains `[tool.basedpyright]` with Python 3.12 and project `.venv` settings. |
| basedpyright dependency | The dev dependency group includes `pytest`, `pytest-asyncio`, `ruff`, and `openai`, but not `basedpyright`. `uv.lock` contains `pytest` and `ruff`, but no `basedpyright` entry. |
| README local checks | `README.md` local development currently shows `uv sync`, `uv run pytest`, and `uv run chat-proxy`; it does not list Ruff or basedpyright verification. |
| CI | No `.github/` directory exists at plan time. |
| Plan 07 | `docs/plans/07-public-reference-documentation.md` is marked completed. |
| Plan 08 | `docs/plans/08-security-and-platform-boundaries.md` is marked completed. |
| Plan 09 | `docs/plans/09-api-contract-and-request-validation.md` is still marked planned, while Plan 09 test files such as `tests/test_http_api_contract.py`, `tests/test_vllm_inference.py`, and `tests/test_web_search_response_contract.py` exist. |
| Progress docs | `docs/PROGRESS.md` still says the active plan is none because Plan 07 is complete and summarizes Plan 07 as the latest shipped plan. |
| Index docs | `docs/INDEX.md` lists plans 01-07, but not plans 08, 09, or 10. |

### Decision for this plan

Keep `basedpyright` as part of the repository quality gate.

Rationale:

- the repository already has `[tool.basedpyright]` configuration;
- completed plan validation commands already include `basedpyright`;
- Plans 08 and 09 already used `uv run basedpyright` in validation commands;
- removing it would weaken the final quality signal and require more documentation churn than installing/configuring it consistently.

---

## 4. Scope

### In scope

- Run and inspect current Ruff results.
- Fix remaining Ruff violations without broad refactors.
- Keep Ruff as the only lint/format tool.
- Add `basedpyright` to the dev dependency group and lockfile.
- Review and tune `[tool.basedpyright]` only enough for consistent repository checks.
- Fix legitimate type-check findings with small, typed, maintainable changes.
- Use narrow ignores or config excludes only when a third-party typing issue is impractical to fix cleanly.
- Update `docs/PROGRESS.md` so Plans 08 and 09 are accurately reflected as completed.
- Update `docs/INDEX.md` to include Plans 08, 09, and 10.
- Update completed plan statuses where they lag implementation, especially Plan 09.
- Review documentation tracking completed work for stale plan-state language.
- Add a small GitHub Actions workflow if it stays simple and useful.
- Document local quality checks in README or a concise developer-facing location.

### Scope guardrails

- Prefer small metadata and documentation updates over process expansion.
- Prefer fixing code that violates current gates over relaxing gates.
- Keep CI aligned with local commands.
- Keep CI CPU-only and dependency-only; it must not require a running model stack.
- Do not add new linters, pre-commit frameworks, coverage gates, dependency bots, release automation, or deployment workflows.

---

## 5. Non-goals

- New API features.
- Security improvements.
- Request limits.
- Rate limiting.
- Architecture refactoring.
- Web-search behavior changes.
- OpenAI compatibility expansion.
- Docker redesign.
- Kubernetes.
- GitHub release automation.
- Dependabot.
- Renovate.
- Pre-commit hooks.
- Coverage enforcement.
- Benchmark automation.
- GPU CI.
- Integration environments.
- Docker build matrices.
- Deployment workflows.
- New documentation systems.
- Broad rewrites of historical plans.

---

## 6. Implementation steps

### 6.1 Establish the quality baseline

- [x] Run `uv sync` to ensure the local environment matches the lockfile before changing gates.
- [x] Run `uv run ruff check .` and capture the remaining violations.
- [x] Run `uv run ruff format --check .` to detect formatting drift.
- [x] Run `uv run pytest` to confirm functional tests before cleanup.
- [x] Run `uv run basedpyright` after dependency metadata is fixed, or confirm the current failure mode if it is missing.
- [x] Separate real code issues from stale tool configuration and documentation mismatches.

### 6.2 Fix Ruff violations

- [x] Fix remaining Ruff violations with the smallest safe code changes.
- [x] Keep type annotations on all new or changed Python signatures.
- [x] Preserve existing module boundaries and behavior.
- [x] Use lazy logging formatting if any logging lines are touched.
- [x] Avoid broad formatting churn beyond what `ruff format` requires.
- [x] Do not add new Ruff rule families or replace Ruff with another tool.

### 6.3 Make basedpyright a real quality gate

- [x] Add `basedpyright` to the `dev` dependency group in `pyproject.toml`.
- [x] Update `uv.lock` through the normal `uv` workflow.
- [x] Review `[tool.basedpyright]` for consistency with the repository layout.
- [x] Confirm `extraPaths` covers the repository import roots required by the quality gate.
- [x] Include `open_webui` in type-check configuration only if current imports require it and the change remains simple.
- [x] Fix actionable type errors in source, tests, and examples where they affect the intended quality gate.
- [x] Use targeted configuration only for generated, external, or dynamically typed surfaces where precise typing would create noise.
- [x] Do not downgrade the type checker into an IDE-only note after choosing to retain it.

### 6.4 Update repository status documentation

- [x] Mark Plan 09 as completed if implementation and tests are present and validation passes.
- [x] Update `docs/PROGRESS.md` so the active plan reflects Plan 10 during implementation and then no active plan after completion.
- [x] Add concise journal entries for Plans 08 and 09 if they are missing from `docs/PROGRESS.md`.
- [x] Add Plan 10 to `docs/INDEX.md`.
- [x] Add Plans 08 and 09 to `docs/INDEX.md` if still missing.
- [x] Review completed plan statuses for stale "Planned" or unchecked implementation language that conflicts with actual repository state.
- [x] Keep historical context intact; do not rewrite old plan rationale unless it is factually misleading as status metadata.

### 6.5 Add lightweight CI

- [x] Add `.github/workflows/quality.yml`.
- [x] Trigger on pull requests and pushes to the default branch.
- [x] Use one Python version matching the repository target, Python 3.12.
- [x] Install `uv` with a standard setup action.
- [x] Run `uv sync --locked`.
- [x] Run `uv run ruff format --check .`.
- [x] Run `uv run ruff check .`.
- [x] Run `uv run basedpyright`.
- [x] Run `uv run pytest`.
- [x] Keep the workflow CPU-only and independent of Docker, vLLM, SearXNG, Open WebUI, Playwright browser installation, and live network services.
- [x] Do not add matrix builds unless a future need is proven.

### 6.6 Document local developer verification

- [x] Update README local development instructions with the final local verification commands.
- [x] Keep the section short enough to remain usable.
- [x] Ensure commands match CI exactly where practical:
  - `uv run ruff format --check .`;
  - `uv run ruff check .`;
  - `uv run basedpyright`;
  - `uv run pytest`.
- [x] Mention smoke tests separately as optional live-stack validation, not part of the default quality gate.

### 6.7 Final repository acceptance pass

- [x] Run the full local quality gate after all cleanup.
- [x] Confirm docs no longer imply Plans 08 or 09 are unfinished.
- [x] Confirm CI workflow commands are the same checks documented for local developers.
- [x] Confirm no new feature, security, deployment, or architecture scope was introduced.
- [x] Confirm no untracked runtime artifacts or local environment files were added.

---

## 7. Affected files

| Path | Planned purpose |
|------|-----------------|
| `pyproject.toml` | Add `basedpyright` to dev dependencies; minimally adjust type-check config only if needed. |
| `uv.lock` | Lock the retained `basedpyright` dev dependency. |
| Source/test/example Python files | Fix only the Ruff and basedpyright findings required for clean gates. |
| `.github/workflows/quality.yml` *(new)* | Lightweight public CI for Ruff, basedpyright, and pytest. |
| `README.md` | Add concise local quality gate commands. |
| `docs/PROGRESS.md` | Reflect completed Plans 08 and 09; track and close Plan 10. |
| `docs/INDEX.md` | Add missing plan entries for Plans 08, 09, and 10. |
| `docs/plans/09-api-contract-and-request-validation.md` | Mark completed and update checkboxes/status only where implementation is verified. |
| `docs/plans/10-final-repository-quality-cleanup.md` | Final cleanup plan and acceptance criteria. |

No runtime configuration, Docker topology, API contract, MCP server behavior, Open WebUI behavior, or deployment documentation should change unless required to correct stale quality-check wording.

---

## 8. Validation strategy

Run the final local quality gate:

```bash
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run basedpyright
uv run pytest
```

Review documentation consistency:

```bash
rg -n "Plan 08|Plan 09|Plan 10|Planned|Completed|Active plan|basedpyright|ruff|pytest|quality" README.md docs pyproject.toml
```

Review CI shape:

```bash
uv run ruff format --check .
uv run ruff check .
uv run basedpyright
uv run pytest
```

The CI workflow should run the same checks. It must not require:

- GPU hardware;
- a running Docker stack;
- live vLLM;
- live SearXNG;
- live Open WebUI;
- deployed secrets;
- networked integration services.

Optional live-stack smoke validation remains separate:

```bash
./tests/smoke/run_proxy_contract_smoke.sh
```

Smoke validation requires the stack to be running and healthy. It is not part of the lightweight public CI gate.

---

## 9. Completion criteria

1. `uv sync --locked` succeeds.
2. `uv run ruff format --check .` succeeds.
3. `uv run ruff check .` succeeds.
4. `uv run basedpyright` succeeds.
5. `uv run pytest` succeeds.
6. `basedpyright` is either fully retained as a dev dependency and documented quality gate, or all stale references are removed. This plan chooses retention.
7. `docs/PROGRESS.md` accurately reflects completed Plans 08 and 09 and closes Plan 10 when implemented.
8. `docs/INDEX.md` lists Plans 08, 09, and 10.
9. Completed plan status metadata matches implementation reality.
10. README or equivalent developer docs show the local quality gate commands.
11. A lightweight GitHub Actions workflow exists and runs Ruff, pytest, and basedpyright.
12. CI remains CPU-only and does not require integration infrastructure.
13. No new product features, architecture changes, security scope, Docker redesign, release automation, or dependency bot configuration is introduced.
14. The repository is ready for final acceptance as a flagship GitHub portfolio project with no further planned engineering work.

---

## 10. Risks and trade-offs

| Risk / trade-off | Mitigation |
|------------------|------------|
| Type checking may surface noisy issues in dynamic test or MCP code | Fix high-value findings directly; use narrow config only for unavoidable dynamic surfaces. |
| Adding basedpyright increases contributor setup cost | It is already referenced by plan validation commands; adding it to dev dependencies makes the existing expectation reproducible. |
| CI can become too slow if it grows beyond local gates | Keep a single Python version and no Docker/GPU/integration matrix. |
| Ruff fixes can accidentally change behavior | Prefer mechanical, local fixes and rely on pytest after changes. |
| Documentation cleanup can drift into historical rewriting | Update status metadata and current tracking only; preserve historical rationale. |
| README can become process-heavy | Add a compact local verification block and keep smoke tests separate. |
| Lockfile updates may be noisy | Limit dependency changes to `basedpyright` and its transitive requirements. |

Operationally, the main failure mode is turning final cleanup into a new engineering wave. The implementation should stay bounded to quality gates, status metadata, CI, and local verification.

---

## 11. Expected engineering impact

Plan 10 should make the repository feel finished.

After implementation, an evaluator or contributor should be able to clone the repository, install dependencies, run one small set of local checks, and see the same checks represented in public CI. The documentation history should show that Plans 07, 08, 09, and 10 are complete, with no stale metadata suggesting unfinished work.

The project should remain architecturally unchanged: a self-hosted AI platform reference implementation with chat-proxy as the public API boundary, internal vLLM/MCP/SearXNG services, and focused tests around the implemented contract.
