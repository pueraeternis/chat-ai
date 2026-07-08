# Plan 07 - public reference documentation alignment

**Status:** Completed.
**Goal:** Align current-facing documentation so the repository reads as a reusable open-source reference implementation for a self-hosted AI platform, with clear architecture, deployment patterns, compatibility boundaries, and operational guidance.

**Scope:** Documentation only. No code changes. No Docker changes. No runtime behavior changes.

**References:** [README.md](../../README.md), [ARCHITECTURE.md](../ARCHITECTURE.md), [PRODUCTION.md](../PRODUCTION.md), [INDEX.md](../INDEX.md), [examples/python/README.md](../../examples/python/README.md), [tests/smoke/README.md](../../tests/smoke/README.md), [open_webui/README.md](../../open_webui/README.md).

---

## 1. Objective

Create a consistent public-facing engineering story for the repository:

- Present the project as a reusable self-hosted AI platform reference implementation.
- Explain the architecture, engineering decisions, and deployment patterns rather than one particular deployment environment.
- Make **chat-proxy** the clearly documented public API boundary for SDK clients and Open WebUI.
- Represent compatibility as **OpenAI Chat Completions-compatible**, not full OpenAI Platform-compatible.
- Replace deployment-specific infrastructure assumptions with reusable, configurable documentation.
- Preserve concrete engineering value: component boundaries, traffic flow, configuration knobs, operational checks, and known limitations.

---

## 2. Motivation

The repository should be understandable and adoptable by engineers building their own self-hosted AI platform. Documentation should teach the reusable system design:

- local development profile;
- reference deployment profile;
- Open WebUI + chat-proxy + vLLM + MCP + SearXNG topology;
- OpenAI Chat Completions API compatibility boundary;
- public versus internal service exposure;
- operational concerns such as health checks, logs, model loading, and web search setup.

The documentation must remain specific enough to be useful, but the specifics should be expressed as configurable deployment choices rather than fixed infrastructure facts.

---

## 3. Documentation principles

| Principle | Guidance |
|-----------|----------|
| Architecture over environment | Documentation should describe the architecture, engineering decisions, and deployment patterns rather than one particular deployment environment. |
| Public reference posture | Current-facing docs should read as reusable open-source documentation, not environment notes copied from a specific production host. |
| Compatibility precision | Use "OpenAI Chat Completions-compatible backend" or equivalent; do not imply support for the full OpenAI Platform. |
| Explicit boundaries | Identify public interfaces and internal services consistently. |
| Configurable deployment | Use environment variables, deployment profiles, and operator-selected values instead of hard-coded infrastructure assumptions. |
| Honest limitations | Document unsupported APIs and current constraints directly. |

---

## 4. Current architecture facts

| Component | Current role |
|-----------|--------------|
| **Open WebUI** | Public browser UI, chat sessions, RAG UI features, OpenAI client pointed at chat-proxy |
| **chat-proxy** | Public API boundary: `/v1/chat/completions`, `/v1/models`; validation, routing, system-tool orchestration |
| **vLLM** | Internal inference backend serving an OpenAI-compatible model API to chat-proxy |
| **web-search MCP** | Internal MCP HTTP service for search/fetch tools used by chat-proxy |
| **SearXNG** | Internal metasearch dependency used by web-search MCP |
| **MCP stdio** | Local development / external MCP client path, not the production proxy hot path |

SDK clients and Open WebUI target **chat-proxy**. vLLM, MCP services, and SearXNG are implementation details for normal application use.

Supported public API surface:

- `POST /v1/chat/completions`
- `GET /v1/models`

Known non-goals / current limitations:

- `/v1/responses`
- Assistants API
- Images API
- Files API
- multiple system tools per request
- mixing hosted/system `web_search` with client `function` tools in one request

---

## 5. Decisions summary

| Topic | Decision |
|-------|----------|
| Repository positioning | Public open-source reference implementation for a self-hosted AI platform |
| Production wording | Prefer **reference deployment** over one canonical production environment |
| Local profile | Document as the default path for development and smoke validation |
| Reference deployment profile | Document scalable deployment patterns, not a fixed host, model, port, path, or hardware layout |
| Model wording | Use "OpenAI-compatible model served by vLLM" / "model supported by the deployed vLLM backend" unless a concrete model is needed as an example |
| Hardware wording | Describe capacity and scaling patterns; avoid tying architecture to one GPU configuration |
| Public API | chat-proxy only |
| Internal services | vLLM, web-search MCP, SearXNG |
| Historical plans | Do not rewrite completed plans unless they are presented as current-facing user guidance |
| Tests | No runtime tests required; validation is documentation review and consistency checks |

---

## 6. Deployment profile contract

### 6.1 Local development

Purpose:

- quick start for a single machine;
- local development and smoke tests;
- portfolio/demo workflow;
- default Compose profile.

Documentation requirements:

- Use `.env.example` and `docker-compose.yml` as the source of configurable values.
- Show `CHAT_PROXY_PORT`, `OPEN_WEBUI_PORT`, `VLLM_PORT`, and model id as configurable, not universal.
- Explain that direct vLLM access is for smoke/debug use; SDK clients should use chat-proxy.
- Keep local setup concise in `README.md`; link to detailed architecture docs.

### 6.2 Reference deployment

Purpose:

- reusable production-oriented deployment pattern;
- operator guidance for sizing, ports, model selection, service exposure, health checks, and logs.

Documentation requirements:

- Rename and reframe production guidance around **reference deployment**.
- Describe deployment dimensions: model size, context length, GPU/accelerator capacity, tensor parallelism, storage/cache paths, service ports, and network exposure.
- Treat all infrastructure values as operator-selected configuration.
- Avoid presenting one model, hardware layout, path, host, or port as canonical.
- Keep operational guidance concrete: start/stop, health checks, logs, Open WebUI setup, web search setup, and model loading behavior.

---

## 7. Infrastructure assumption audit

Review current-facing documentation for deployment-specific assumptions and rewrite them as reusable engineering documentation where appropriate.

The audit should identify categories, not only exact strings:

| Category | Replace with |
|----------|--------------|
| Fixed hardware topology | Hardware-agnostic capacity guidance and scaling patterns |
| Specific production model choice | Operator-selected vLLM-supported model; optional examples clearly marked as examples |
| Host-specific filesystem paths | Configurable cache/data paths |
| Fixed hostnames or private addresses | Placeholder hostnames or environment variables |
| Environment-specific ports | Configurable service ports and clear public/internal port roles |
| One-server operational notes | Generic reference deployment operations |
| Legacy deployment references | Current architecture guidance, unless retained only in historical plan files |
| Ownership language | Neutral public documentation language |

Examples may be used, but examples must be labeled as examples and must not become the implementation strategy.

---

## 8. Implementation steps

### 8.1 `README.md`

- [ ] Reframe the opening as a reusable self-hosted AI platform reference implementation.
- [ ] Use precise compatibility wording: OpenAI Chat Completions-compatible backend.
- [ ] Add or refine a deployment profile summary: local development and reference deployment.
- [ ] Keep quick start local-first and based on configurable `.env` values.
- [ ] State that chat-proxy is the public API for Open WebUI and SDK clients.
- [ ] State that vLLM, MCP services, and SearXNG are internal services.
- [ ] Avoid deployment-specific production model, hardware, host, path, or port assumptions.
- [ ] Preserve screenshots and concise feature overview.

### 8.2 `docs/ARCHITECTURE.md`

- [ ] Replace plan-era headings and wording with current-state architecture language.
- [ ] Add a clear "Public interfaces and internal services" section.
- [ ] Add a "Compatibility boundary" section listing supported and unsupported API surfaces.
- [ ] Explain request flows for plain chat, client functions, reasoning, and `web_search`.
- [ ] Describe local development and reference deployment profiles generically.
- [ ] Generalize model descriptions to the vLLM-served model role unless a model is only an example.
- [ ] Generalize hardware descriptions to capacity/scaling patterns.
- [ ] Remove stale legacy/cutover wording from current-facing architecture content.

### 8.3 `docs/PRODUCTION.md`

- [ ] Reframe as **Reference deployment** documentation.
- [ ] Describe deployment patterns rather than one infrastructure environment.
- [ ] Replace fixed hardware assumptions with capacity planning guidance.
- [ ] Replace fixed production model assumptions with operator-selected vLLM model guidance.
- [ ] Replace host-specific paths with configurable cache/data path descriptions.
- [ ] Replace fixed port assumptions with configurable public/internal port descriptions.
- [ ] Keep operational sections for start/stop, health checks, logs, Open WebUI setup, and web search setup.
- [ ] Make clear that chat-proxy remains the public API and vLLM remains internal.

### 8.4 `examples/python/README.md`

- [ ] Generalize examples for a typical self-hosted deployment.
- [ ] Default examples to `localhost` and configurable chat-proxy settings.
- [ ] Avoid private IPs, host-specific values, and deployment-specific production model ids.
- [ ] Use placeholder remote host examples where needed.
- [ ] Ensure all examples target chat-proxy, not direct vLLM.
- [ ] Keep model names configurable through `VLLM_SERVED_MODEL` or equivalent environment variables.
- [ ] Ensure curl examples match the surrounding profile assumptions.

### 8.5 `docs/INDEX.md`

- [ ] Update descriptions if document roles change, especially `docs/PRODUCTION.md`.
- [ ] Avoid describing current-facing docs as tied to one specific deployment environment.
- [ ] Keep plan entries historical and accurate without turning completed plans into current setup guidance.

### 8.6 `tests/smoke/README.md`

- [ ] Replace plan-era labels such as "plan 02 contract" with current contract wording.
- [ ] Clarify that proxy smoke tests target the public chat-proxy API.
- [ ] Clarify that direct vLLM smoke tests are optional debug checks.
- [ ] Keep environment variables configurable and aligned with `.env.example`.

### 8.7 `open_webui/README.md`

- [ ] Ensure wording consistently treats Open WebUI as a public UI over chat-proxy.
- [ ] Keep the proxy `web_search` Filter setup concrete.
- [ ] Avoid environment-specific host, model, or deployment assumptions.
- [ ] Keep limitations visible: disable built-in OWUI web search for proxy-search workflow; enable status/citation capabilities.

---

## 9. Affected files

| Path | Purpose of planned update |
|------|---------------------------|
| `README.md` | Public reference positioning, local quick start, deployment profile summary |
| `docs/ARCHITECTURE.md` | Current-state architecture, boundaries, compatibility, generic profiles |
| `docs/PRODUCTION.md` | Reference deployment guide instead of environment-specific production notes |
| `examples/python/README.md` | Generic client setup and examples against chat-proxy |
| `docs/INDEX.md` | Navigation and document role descriptions |
| `tests/smoke/README.md` | Current API contract wording and debug/direct-vLLM distinction |
| `open_webui/README.md` | UI integration wording consistency |

No source files, Docker files, environment templates, or runtime configuration files should be changed in this plan unless a future explicit task expands the scope.

---

## 10. Validation steps

- [ ] Review all current-facing docs for wording that suggests the documentation was copied from a specific production environment; replace such wording with reusable engineering documentation where appropriate.
- [ ] Search current-facing docs for deployment-specific infrastructure assumptions: fixed hardware, fixed model choices, host-specific paths, private hosts/IPs, one-environment ports, legacy deployment references, and ownership language.
- [ ] Confirm any remaining concrete infrastructure values are either local defaults from repository configuration or clearly labeled examples.
- [ ] Confirm `README.md` explains the project as a reusable self-hosted AI platform reference implementation.
- [ ] Confirm `docs/PRODUCTION.md` is framed as reference deployment guidance.
- [ ] Confirm docs consistently describe chat-proxy as the public API boundary.
- [ ] Confirm docs consistently describe vLLM, MCP services, and SearXNG as internal services.
- [ ] Confirm compatibility wording is limited to OpenAI Chat Completions and `/v1/models`.
- [ ] Confirm unsupported API surfaces and current tool limitations are explicitly listed.
- [ ] Confirm examples are reusable without inheriting deployment details from an unrelated environment.
- [ ] Confirm no code, Docker, or runtime behavior changed.

Suggested review command:

```bash
rg -n "production|reference deployment|OpenAI-compatible|OpenAI Platform|/v1/responses|Assistants|Images API|Files API|legacy|target deployment|host|port|GPU|model|cache|/home|/mnt|172\\." README.md docs examples open_webui tests/smoke
```

Use the command as a review aid, not as the definition of success. The implementation should reason about wording in context.

---

## 11. Completion criteria

1. Current-facing documentation reads as reusable public open-source documentation.
2. The architecture story is consistent across README, architecture docs, reference deployment docs, examples, smoke docs, and Open WebUI docs.
3. A new engineer can understand:
   - what the platform is;
   - which components exist;
   - how components communicate;
   - which interfaces are public;
   - which services are internal;
   - how local development differs from reference deployment;
   - which values they must configure for their own environment.
4. Deployment-specific infrastructure assumptions are removed or reframed as configurable examples.
5. Model and hardware descriptions are generalized unless needed as clearly marked examples.
6. OpenAI compatibility is precise and not overstated.
7. Known limitations remain visible.
8. No implementation, Docker, or runtime behavior changes are made.

---

## 12. Out of scope

- Code changes.
- Docker Compose changes.
- Environment template changes.
- Model changes.
- Port changes.
- New APIs.
- New deployment automation.
- New screenshots.
- Rewriting completed historical plans, unless a completed plan is being used as current-facing user guidance.
- Claiming support for unsupported OpenAI APIs.

---

## 13. Risks and trade-offs

- Over-generalization can make documentation vague; preserve concrete component flows, env-var names, and operational checks.
- Removing deployment-specific details from `docs/PRODUCTION.md` may require a larger rewrite than other files.
- Concrete model and hardware examples can still be useful, but only when clearly marked as examples and not defaults.
- Historical plans may still contain old deployment details; avoid rewriting history unless it affects current onboarding.
- Public polish must not hide limitations; explicit boundaries are part of the engineering value.

---

## 14. Expected engineering impact

This documentation wave makes the repository easier to evaluate, reuse, and extend as an open-source AI platform reference implementation. It reduces onboarding ambiguity, clarifies service ownership boundaries, prevents users from copying environment-specific deployment details, and strengthens the repository's value as a senior-level AI systems engineering portfolio project.
