---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-record"
domain: "independent-review"
severity: "strict"
name: "Review Broker v1 Reviewer Tool-Surface Inventory"
version: "0.1.0"
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
