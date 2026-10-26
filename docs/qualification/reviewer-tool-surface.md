---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-record"
domain: "independent-review"
severity: "strict"
name: "Review Broker v1 Reviewer Tool-Surface Inventory"
version: "0.1.2"
---

# Review Broker v1 Reviewer Tool-Surface Inventory

## Evidence boundary

Subject: `@openai/codex` `0.164.0`, upstream tag `rust-v0.164.0`, commit
`6aaac694803004a63c6f393d153c96d22521a6b9`, and the Review Broker
attempt-bound profile. Source links below point to this exact commit, never
upstream `main`. The broker passes `-c features.shell_tool=false` together
with its existing reasoning-effort override. The Codespace CLI reported
`codex-cli 0.164.0`; `codex features list` under an **empty temporary**
`CODEX_HOME` reported `shell_tool stable true` by default, `false` under the
specified override, and `true` under an explicit positive control. It did not
invoke `codex exec`, read OAuth material, or enumerate a model's effective tool
specification. The Codespace returned to observed `Shutdown`.

This is a **source-inferred, conditional inventory**, not an observed effective
model tool inventory. Model metadata, feature/config layers, MCP servers,
extensions, dynamic tools, provider capabilities and selected agent mode in a
live reviewer invocation were not independently inventoried. The security gate
remains **UNQUALIFIED**. No additional tool is disabled here.

## `exec_command` and `write_stdin`

- **Registration:** [`spec_plan.rs:1214–1265`](https://github.com/openai/codex/blob/6aaac694803004a63c6f393d153c96d22521a6b9/codex-rs/core/src/tools/spec_plan.rs#L1214-L1265) returns before registering either tool if `Feature::ShellTool` is disabled. Unified execution chooses both tools or a one-shot `exec_command` only after that guard. [`features/src/lib.rs:1080–1085`](https://github.com/openai/codex/blob/6aaac694803004a63c6f393d153c96d22521a6b9/codex-rs/features/src/lib.rs#L1080-L1085) defines `shell_tool` as stable and on by default.
- **Expected reviewer state:** Not registered by this shell-tool source path. The actual model tool list was not observed; extension and dynamic registries are separate.
- **Host I/O:** If exposed, subprocess execution would be host I/O subject to runtime permissions. That path is intentionally removed for v1.
- **Further qualification:** Independently inspect the exact effective tool specifications and feature stack without treating the CLI feature listing as that inventory.

## `apply_patch`

- **Registration:** [`spec_plan.rs:1409–1412`](https://github.com/openai/codex/blob/6aaac694803004a63c96d22521a6b9/codex-rs/core/src/tools/spec_plan.rs#L1409-L1412) registers it when `model_info.apply_patch_tool_type` exists, independent of `ShellTool`. The handler verifies the patch against a sandbox context and dispatches through `ToolOrchestrator`, deriving write permissions from the selected environment and possible additional permissions in [`apply_patch.rs:476–563`](https://github.com/openai/codex/blob/6aaac694803004a63c96d22521a6b9/codex-rs/core/src/tools/handlers/apply_patch.rs#L476-L563).
- **Expected reviewer state:** Conditional on unobserved pinned model metadata; **not disabled** by this task. The current read-only permission profile should prevent writes, but effective handler enforcement was not exercised.
- **Host I/O:** A separate filesystem-writing mechanism, not equivalent to the shell. Permissions and approval behavior require integrated testing; do not assume its absence or success from `shell_tool=false`.
- **Further qualification:** Inventory actual model specs and safely test patch attempts against non-secret denied paths without authenticated reviewer inference until the security gate permits it.

## MCP resource and server tools

- **Registration:** [`spec_plan.rs:151–164`](https://github.com/openai/codex/blob/6aaac694803004a63c96d22521a6b9/codex-rs/core/src/tools/spec_plan.rs#L151-L164) appends MCP server tools independently of shell. [`spec_plan.rs:1269–1285`](https://github.com/openai/codex/blob/6aaac694803004a63c96d22521a6b9/codex-rs/core/src/tools/spec_plan.rs#L1269-L1285) adds resource-list, template-list and resource-read tools when servers exist or code-mode-only is effective. Server exposure has separate rules at lines 198–293. Resource handlers can dispatch to a server; app-server gating is visible in [`mcp_resource.rs:45–60`](https://github.com/openai/codex/blob/6aaac694803004a63c96d22521a6b9/codex-rs/core/src/tools/handlers/mcp_resource.rs#L45-L60).
- **Expected reviewer state:** The broker profile declares no MCP server, but actual managed, plugin and application layers were not inspected. **UNDETERMINED**, not an assertion of no MCP tools.
- **Host I/O:** Depends on each effective server and its authority; potential filesystem or network access outside the shell sandbox.
- **Further qualification:** Enumerate effective servers, resources, tool policies, inherited authorization and per-tool I/O for the actual reviewer configuration.

## Subagents and collaboration

- **Registration:** [`spec_plan.rs:1436–1582`](https://github.com/openai/codex/blob/6aaac694803004a63c96d22521a6b9/codex-rs/core/src/tools/spec_plan.rs#L1436-L1582) selects V1 or V2 spawn and management tools when collaboration is enabled. `multi_agent` defaults on and `multi_agent_v2` defaults off in [`features/src/lib.rs:1507–1519`](https://github.com/openai/codex/blob/6aaac694803004a63c96d22521a6b9/codex-rs/features/src/lib.rs#L1507-L1519); agents default enabled in [`config/mod.rs:4034–4038`](https://github.com/openai/codex/blob/6aaac694803004a63c96d22521a6b9/codex-rs/core/src/config/mod.rs#L4034-L4038). Model metadata may select the version. The V1 handler says children inherit effective config, provider, approvals, sandbox and cwd, then optionally layer role config in [`multi_agents.rs:1–7`](https://github.com/openai/codex/blob/6aaac694803004a63c96d22521a6b9/codex-rs/core/src/tools/handlers/multi_agents.rs#L1-L7).
- **Expected reviewer state:** Potentially available, not disabled by this task; effective model version, depth, role layers and actual inventory unobserved.
- **Host I/O:** A child may possess tools under inherited or role-layered configuration. Whether any layer broadens permissions is **UNDETERMINED**.
- **Further qualification:** Trace child effective feature/profile propagation and runtime tool sets without assuming parent shell disable automatically proves child isolation.

## Code-mode execution

- **Registration:** [`spec_plan.rs:1013–1102`](https://github.com/openai/codex/blob/6aaac694803004a63c96d22521a6b9/codex-rs/core/src/tools/spec_plan.rs#L1013-L1102) registers JavaScript code-mode execute/wait for effective CodeMode or CodeModeOnly. [`tools/mod.rs:64–91`](https://github.com/openai/codex/blob/6aaac694803004a63c96d22521a6b9/codex-rs/core/src/tools/mod.rs#L64-L91) prefers model `tool_mode` metadata over feature defaults. The `code_mode` feature defaults off, while `code_mode_host` defaults on in [`features/src/lib.rs:1197–1222`](https://github.com/openai/codex/blob/6aaac694803004a63c96d22521a6b9/codex-rs/features/src/lib.rs#L1197-L1222).
- **Expected reviewer state:** Direct mode if no overriding model metadata or configuration; actual pinned model metadata and effective mode **UNDETERMINED**. `shell_tool=false` does not disable code-mode tools.
- **Host I/O:** Host execution or nested tool calls require separate scrutiny; absence of filesystem, process or network reachability is **not established**.
- **Further qualification:** Observe the effective mode, host setup and nested tool list and test sandbox enforcement using only permitted non-secret probes.

## Web, extension and dynamic tools

- **Registration:** Hosted web search is provider/model/cached-mode dependent at [`spec_plan.rs:687–715`](https://github.com/openai/codex/blob/6aaac694803004a63c96d22521a6b9/codex-rs/core/src/tools/spec_plan.rs#L687-L715). Extension executors, including standalone `web.run`, are appended at [`spec_plan.rs:1624–1652`](https://github.com/openai/codex/blob/6aaac694803004a63c96d22521a6b9/codex-rs/core/src/tools/spec_plan.rs#L1624-L1652); dynamic tools are registered separately at lines 1585–1614. None is controlled by the shell feature guard.
- **Expected reviewer state:** Conditional on unobserved provider capabilities, effective web mode, extensions and dynamic tools. **UNDETERMINED**.
- **Host I/O:** Hosted web can use provider network rather than sandboxed direct network. Extension and dynamic runtimes can carry separate host authority. No blanket network-denial claim follows from shell removal.
- **Further qualification:** Inspect the actual tool router, extension providers, network routes and response exposure under the target model.

## Other built-ins

- **Registration:** [`spec_plan.rs:1288–1426`](https://github.com/openai/codex/blob/6aaac694803004a63c96d22521a6b9/codex-rs/core/src/tools/spec_plan.rs#L1288-L1426) conditionally adds planning, environment wait, user messaging, permissions requests, clock, sleep, plugin suggestions, testing and image viewing. `view_image` defaults on in [`features/src/lib.rs:1086–1091`](https://github.com/openai/codex/blob/6aaac694803004a63c96d22521a6b9/codex-rs/features/src/lib.rs#L1086-L1091), and its handler asks the filesystem for file bytes with a sandbox context in [`view_image.rs:147–180`](https://github.com/openai/codex/blob/6aaac694803004a63c96d22521a6b9/codex-rs/core/src/tools/handlers/view_image.rs#L147-L180).
- **Expected reviewer state:** Conditional per feature/model/config; notably `view_image` is potentially available independently of shell. No effective tool list was observed.
- **Host I/O:** `view_image` is another filesystem read path. Its hard-link behavior and real credential protections have not been tested. Other utilities may mutate session state, invoke providers or ask for permissions; no broad safety claim is made.
- **Further qualification:** Inspect actual registration, permission checks, hard-link handling and denial paths for each host-I/O-capable tool.

## Historical hard-link and qualification claims

**A — Filesystem:** The preserved direct-sandbox receipt in
`receipts/attempt-bound-direct-sandbox-v1.json` established that an actually
constructed outside-file hard link was readable through the packet path.
The packet-tree link-count and symlink checks remain mandatory defense in
depth. Nothing in this inventory changes that observation.

**B — Shell:** Source registration and the non-inference CLI feature resolution
support the bounded claim that `features.shell_tool=false` disables the ordinary
shell registration path in pinned `0.164.0`. No effective live model tool
inventory has been observed.

**C — Global isolation:** The remaining model-capable surfaces, runtime config,
model metadata and end-to-end privilege effects are not qualified. A passing B
is not a passing C. Independent security acceptance is still required before
any authenticated reviewer inference.

## 2026-10-26 — Exact-SHA bundled metadata and router investigation

**Subject:** PR #14 at `6f1495ac073d9121655fab2146cfe78d8359e536`,
upstream tag `rust-v0.164.0` at
`6aaac694803004a63c6f393d153c96d22521a6b9`. This section supplements,
not replaces, the historical hard-link, `/proc` and feature-resolution results
above. Evidence classes below describe only the cited subject and inputs.
The sanitized local receipt is
[`bundled-model-tool-metadata-0164.json`](receipts/bundled-model-tool-metadata-0164.json).

### Installed CLI and exact bundled entry — OBSERVED_NON_INFERENCE

- The dedicated Codespace ran installed `codex-cli 0.164.0`. Its native Linux
  executable had SHA-256
  `b93f6811d3f653f0fb83be4050d857fb9abbb111dfa2ce160563327daff7f306`;
  its JavaScript launcher had SHA-256
  `61b0194f3bb6534439c8d26a3ed57d0805f84b884588b761795323eeb92fcf70`.
  The original `env -i` version check failed because minimal `PATH` omitted
  Node; a fresh empty temporary `HOME` and `CODEX_HOME`, `env -i`, and a PATH
  containing only the installed Node location and system binaries fixed it.
  A temporary-home PATH-alias warning did not prevent the successful local
  commands. The Codespace returned to independently observed `Shutdown` after
  **each** inspection. No service credentials were forwarded to these CLI
  children; no real authentication files or credential contents were read.
- `codex debug models --bundled`, **not** online `codex debug models`, emitted
  JSON with root field `models`, 11 entries, 658607 stdout bytes and SHA-256
  `69af12f94a39dabd1a1ded8f5257b4884d2118902ea2b5b9cffbf4a1925dfa65`.
  Exactly one entry had `slug: "gpt-5.6-sol"`. The selected entry's actual
  fields were `shell_type: "unified_exec"`,
  `apply_patch_tool_type: "freeform"`, `tool_mode: "code_mode_only"`,
  `multi_agent_version: "v2"`, `experimental_supported_tools: []`,
  `supports_search_tool: true`, `web_search_tool_type: "text_and_image"`,
  `node_repl_disabled: false`, `supported_in_api: true`, and
  `use_responses_lite: true`. None is an observed effective model-visible tool
  specification or evidence that a provider accepted this model. Other catalog
  entries and model instruction text were not published.
- With the broker's two `-c` settings and an empty temporary home, the installed
  `features list` reported `shell_tool=false`, `code_mode=false`,
  `code_mode_only=false`, `code_mode_host=true`, `multi_agent=true`,
  `multi_agent_v2=false`, `standalone_web_search=false`, `view_image=true`.
  These are **feature-resolution observations for that clean configuration**,
  not an installed attempt-profile or live turn-state inspection.

### Metadata selection and model-visible inventory — SOURCE_DERIVED / UNDETERMINED

- [`cli/src/main.rs:2192–2222`](https://github.com/openai/codex/blob/6aaac694803004a63c6f393d153c96d22521a6b9/codex-rs/cli/src/main.rs#L2192-L2222)
  selects the bundled catalog directly under `--bundled`, skipping the normal
  config, auth and catalog refresh branch. The ordinary manager seeds bundled
  entries but can use identity-bound cache and a provider `/models` refresh;
  [`models-manager/src/manager.rs:288–365`](https://github.com/openai/codex/blob/6aaac694803004a63c6f393d153c96d22521a6b9/codex-rs/models-manager/src/manager.rs#L288-L365),
  [`488–500`](https://github.com/openai/codex/blob/6aaac694803004a63c6f393d153c96d22521a6b9/codex-rs/models-manager/src/manager.rs#L488-L500),
  [`545–614`](https://github.com/openai/codex/blob/6aaac694803004a63c6f393d153c96d22521a6b9/codex-rs/models-manager/src/manager.rs#L545-L614).
  Thus the exact bundled match is a **local fallback candidate**, not an
  attestation of the authenticated reviewer's selected catalog, authorization,
  tool metadata, or effective model identity.
- The CLI help and pinned `prompt_debug.rs:24–109` show `debug prompt-input`
  builds the **prompt input list**, starts a debug thread and an auth manager;
  it does not emit `ToolRouter.model_visible_specs`. It was **not executed**.
  `debug models --bundled` exports a catalog, while `app-server --help` exposes
  startup-config printing and server transport, not a final tool-spec dump.
  [`tools/spec_plan.rs:371–551`](https://github.com/openai/codex/blob/6aaac694803004a63c6f393d153c96d22521a6b9/codex-rs/core/src/tools/spec_plan.rs#L371-L551)
  builds the final registry and model-visible specifications from live turn,
  selected model, environment, MCP binding, extension/dynamic registrations,
  provider-hosted specs and tool policy. No supported **non-inference final
  tool-inventory interface** was established for this exact invocation.
  **EFFECTIVE_TOOL_INVENTORY=UNAVAILABLE_WITH_SUPPORTED_NON_INFERENCE_INTERFACE**.
- The source-derived inputs actually known are the broker's `codex exec` argv,
  requested model and effort, source-generated immutable profile bytes, the
  initial offline packet guard, this empty-home CLI feature snapshot and the
  bundled descriptor. **UNDETERMINED:** installed attempt-bound and managed
  feature layers, effective model metadata and tool mode, provider-hosted tool
  capabilities, MCP servers and resources, plugins and application extensions,
  dynamic definitions, agent-role configs, tool policy, environment availability
  and final model-visible tool router. The profile source does not declare MCP,
  extensions or agent roles; their absence from every effective layer was not
  proved. Neither the actual OAuth session nor an authenticated model request
  was used to fill these gaps.

### Conditional host-I/O paths — SOURCE_DERIVED, not an effective list

- **Shell:** `shell_type: "unified_exec"` specifies a preferred shell **type**, not
  compulsory exposure. `add_shell_tools` at
  [`spec_plan.rs:1235–1265`](https://github.com/openai/codex/blob/6aaac694803004a63c6f393d153c96d22521a6b9/codex-rs/core/src/tools/spec_plan.rs#L1235-L1265)
  exits before adding `exec_command`/`write_stdin` if effective
  `Feature::ShellTool=false`. This remains valid even if the bundled descriptor
  selects `code_mode_only`, because the code-mode wrapper draws its nested tools
  from the registered tool set at
  [`spec_plan.rs:951–995`](https://github.com/openai/codex/blob/6aaac694803004a63c6f393d153c96d22521a6b9/codex-rs/core/src/tools/spec_plan.rs#L951-L995).
  The actual managed/profile feature stack and final registry were not observed.
- **Patch and image filesystem:** The exact bundled descriptor supplies
  `apply_patch_tool_type: "freeform"`. If selected at runtime, it triggers
  independent patch registration at
  [`spec_plan.rs:1409–1412`](https://github.com/openai/codex/blob/6aaac694803004a63c6f393d153c96d22521a6b9/codex-rs/core/src/tools/spec_plan.rs#L1409-L1412).
  The patch handler verifies against an environment filesystem sandbox before
  parsing and executing; it derives and requests write permissions at
  [`apply_patch.rs:328–357`](https://github.com/openai/codex/blob/6aaac694803004a63c6f393d153c96d22521a6b9/codex-rs/core/src/tools/handlers/apply_patch.rs#L328-L357)
  and [`476–563`](https://github.com/openai/codex/blob/6aaac694803004a63c6f393d153c96d22521a6b9/codex-rs/core/src/tools/handlers/apply_patch.rs#L476-L563).
  It is **not** a read-only inert tool, nor is successful write escalation
  demonstrated. Default-on `view_image` registers independently and obtains
  metadata and bytes through the environment filesystem **with sandbox
  context**, [`view_image.rs:147–180`](https://github.com/openai/codex/blob/6aaac694803004a63c6f393d153c96d22521a6b9/codex-rs/core/src/tools/handlers/view_image.rs#L147-L180).
  Path aliases and credential material were not tested through either model
  tool. A hard-link alias passed the **direct sandbox**, while the broker's
  pre-invocation packet-tree check rejects multi-linked files; no integrated
  model-tool result eliminates race, alternate-path or `/proc` concerns.
- **Code mode:** The bundled entry specifies `tool_mode: "code_mode_only"`.
  [`tools/mod.rs:64–91`](https://github.com/openai/codex/blob/6aaac694803004a63c6f393d153c96d22521a6b9/codex-rs/core/src/tools/mod.rs#L64-L91)
  prefers model mode over default-off `code_mode` feature flags; if that entry
  is effective, `spec_plan.rs:1013–1102` registers code-mode execute/wait and
  exposes eligible nested tools. The code-mode runtime's V8 globals export
  broker-provided `tools` and `ALL_TOOLS`, and its module loader rejects
  imports, at
  [`runtime/globals.rs:16–63`](https://github.com/openai/codex/blob/6aaac694803004a63c6f393d153c96d22521a6b9/codex-rs/code-mode-runtime/src/runtime/globals.rs#L16-L63)
  and [`runtime/module_loader.rs:143–206`](https://github.com/openai/codex/blob/6aaac694803004a63c6f393d153c96d22521a6b9/codex-rs/code-mode-runtime/src/runtime/module_loader.rs#L143-L206).
  This is **not Node's unrestricted filesystem/process API**, and the JavaScript
  wrapper does not by itself restore the disabled shell. It dispatches nested
  registered tools through `tools/code_mode/delegate.rs:441–464`; those tools'
  distinct permissions and any V8-to-host escape remain unqualified.
- **MCP:** Even without a bound server, `code_mode_only` causes independent
  MCP-resource registration at `spec_plan.rs:1269–1285`; an actual server's
  tools depend on the live MCP binding and per-server policy at
  [`spec_plan.rs:151–166`](https://github.com/openai/codex/blob/6aaac694803004a63c6f393d153c96d22521a6b9/codex-rs/core/src/tools/spec_plan.rs#L151-L166)
  and `198–293`. Servers can carry their own filesystem, service or network
  authority; an empty broker profile alone is not an effective server census.
- **Subagents:** The bundled entry selects `multi_agent_version: "v2"` if the
  model entry is chosen and config does not override it;
  [`config/mod.rs:1658–1684`](https://github.com/openai/codex/blob/6aaac694803004a63c6f393d153c96d22521a6b9/codex-rs/core/src/config/mod.rs#L1658-L1684).
  Spawning still depends on enabled agents, depth, policy and available tools
  (`spec_plan.rs:729–765`, `1439–1582`). V2 spawn routes through
  [`multi_agents_v2/spawn.rs:94–138`](https://github.com/openai/codex/blob/6aaac694803004a63c6f393d153c96d22521a6b9/codex-rs/core/src/tools/handlers/multi_agents_v2/spawn.rs#L94-L138).
  Children start from their parent's effective config and carry current
  approval/profile/cwd state, then may layer role and model choices;
  [`agent/child_config.rs:52–100`](https://github.com/openai/codex/blob/6aaac694803004a63c6f393d153c96d22521a6b9/codex-rs/core/src/agent/child_config.rs#L52-L100)
  and [`132–201`](https://github.com/openai/codex/blob/6aaac694803004a63c96d22521a6b9/codex-rs/core/src/agent/child_config.rs#L132-L201).
  In the inspected role code, feature overrides can **disable** `ShellTool`,
  not turn a false parent feature on (`agent/role.rs:90–106`, `200–221`).
  Other role/provider/environment privilege effects remain unobserved.
- **Web, extension, dynamic and other tools:** The bundled
  `web_search_tool_type: "text_and_image"` and `supports_search_tool: true`
  affect conditional hosted web, deferred search and third-party exposure,
  **not** proof that web is off or that external calls are sandboxed.
  `spec_plan.rs:687–715` requires provider capability and selected web mode;
  `1624–1652` registers eligible extensions independently of shell;
  `1585–1614` registers dynamic tools. Broker code did not establish the
  effective server, provider, plugin, extension or dynamic inventories.
  Provider-hosted calls and tool plugins may have different network and local
  service privileges from the Linux shell sandbox.

### Discovery classification

- **Bundled mode:** Statement: the exact bundled `gpt-5.6-sol` entry specifies
  `code_mode_only`, even though clean-home feature defaults for code mode are
  false. Source and evidence: installed CLI receipt and pinned `tools/mod.rs`.
  Existing authority: the reviewer-independence contract requires isolation,
  not a specific tool mode. Semantic disposition: `no-normative-impact`;
  affected layers: `verification-or-qualification-evidence`,
  `architecture-or-implementation`, `integration-or-conformance`. Related
  consequence: possible nested tool paths below. Required authority:
  independent security acceptance, not a new product choice. Next action:
  validate actual catalog selection and model-visible specs.
- **Incomplete host-I/O guarantee:** Statement: shell registration can be
  suppressed without demonstrating that all other tool I/O is credential
  isolated. Source and evidence: this conditional registration analysis plus
  the retained hard-link and `/proc` direct-sandbox observations. Existing
  authority: `docs/security/reviewer-independence.md` requires model-tool
  credential isolation and an independent qualification gate. Semantic
  disposition: `no-normative-impact` (qualification gap under an already
  accepted rule); affected layers: `verification-or-qualification-evidence`,
  `integration-or-conformance`. Related consequence: Issue #22 remains open.
  Required authority: independent security adjudication. Next action:
  request separate exact-SHA security verdicts via Issue #11; do not silently
  weaken the accepted requirement.

### Security dispositions and handoff

- **SHELL_REGISTRATION_BOUNDARY — SOURCE_DERIVED conditional denial:** With the
  broker's exact `-c features.shell_tool=false` effective, normal shell-tool
  registration is rejected; the installed clean-home CLI resolved that flag as
  false. This does not attest the final model-visible list or all child tools.
- **OTHER_MODEL_HOST_IO_BOUNDARY — UNDETERMINED:** A selected bundled model
  would have code-mode nested tools, independent patch/image filesystem routes,
  MCP resource entry points and conditional V2 agents, web and extensions.
  Which of these are exposed in the actual authenticated turn and what
  privileged host resources each can reach are not established.
- **CREDENTIAL_ISOLATION_BOUNDARY — UNQUALIFIED:** The existing contract
  forbids all model-controlled paths to OAuth and privileged material. Neither
  shell suppression nor source-derived V8 constraints qualify the remaining
  paths, `/proc`, descriptors, hard-link aliases or packet-tree time-of-check.
  No authenticated reviewer inference or real credential access occurred.
  Independent shell, remaining-tool and credential-isolation verdicts must
  be requested separately. Do not set the security variable, merge PR #14,
  or close Issues #22/#11 from these producer findings.

## 2026-10-26 — Runtime identity and managed-requirement delta

Official npm metadata identifies the Linux x64 installation as root package
`@openai/codex@0.164.0` plus alias `@openai/codex-linux-x64`, whose published
artifact is `@openai/codex@0.164.0-linux-x64`. Both downloaded archives matched
their registry `dist.integrity`; independently extracted launcher and native
hashes matched the dedicated Codespace. The versioned trust record and receipt
are `src/review_broker/trust/codex-release-v1.json` and
[`codex-npm-release-provenance-0164.json`](receipts/codex-npm-release-provenance-0164.json).
This is **OBSERVED_NON_INFERENCE** official-artifact identity, not reproducible
source equivalence or independent acceptance. The bundled `unified_exec` versus
pinned-source `shell_command` discrepancy remains unresolved.

The mutable npm installation is no longer the model-transport executable. A
pre-arm check binds its official launcher/package mapping to a root-owned,
non-writable package-layout copy, and invocation repeats that verification
before executing the protected absolute native path. Node and mutable launcher
lookup are excluded from model transport; loader and Node injection variables
are removed. Missing, ambiguous, changed, unsupported or unprotected runtimes
fail before model-capable execution evidence is created.

The separate receipt
[`managed-requirements-attestation-0164.json`](receipts/managed-requirements-attestation-0164.json)
records isolated synthetic managed requirements. They changed effective
`shell_tool=false` to true, replaced the requested profile with `:read-only`,
replaced approval `never` with `on-request`, and selected a managed profile with
network enabled. These were **OBSERVED_NON_INFERENCE** diagnostics and agree
with pinned source resolution.

`app-server --print-startup-config` emits requirements, `doctor` and `features`
are separate processes, and `codex exec --json` emits only a thread identifier
from its effective session configuration before continuing to the turn. No
supported interface provides shell state, exact active profile, complete
filesystem/network policy and approval policy from the same `codex exec`
process with a broker-controlled pause before model transport. Therefore
`OBL02_ATTESTATION_INTERFACE=UNAVAILABLE` and `OBL02_STATUS=BLOCKED`. Attempt
evidence records this absence explicitly; it does not convert requested argv or
profile bytes into effective-policy attestation.
