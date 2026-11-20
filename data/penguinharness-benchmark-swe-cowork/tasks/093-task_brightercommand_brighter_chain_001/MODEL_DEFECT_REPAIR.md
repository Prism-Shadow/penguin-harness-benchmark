# Successor repair: model-defect-093-20260922-v1

## Attempt-006 — integrate the six-file BASE compatibility correction

Controlled feedback `iteration-history/1790095009868456211/FEEDBACK.json`
binds `closure-093-owner-integration-v1/SUPERVISOR_FEEDBACK.json` (SHA256
`00d2aa972669f31ff2b3567459dd7a5e164f273b419e8e1acfd23addf14534e0`).
The latter paths are relative to the runtime repair root; iteration and scratch
paths are relative to this row. Its current BASE audit records 19 invalid nodes:
13 incomplete results, four harness compilation errors, and two fixture errors.
The earlier aggregate reward-zero statement is not strict BASE acceptance.
The original audit, failures, reports, and candidate receipts remain untouched.

Applied exactly `closure-093-current-v4-controls-v1/candidate-base-v6/base-compat-only.patch`
(SHA256 `58ae486fdace616b4aad6cd63674069fb574d8c50a3d6a1711019f0297022907`),
with all six before/after hashes checked against the supervisor's apply receipt.
The four integration tests bind newly required APIs at runtime rather than
preventing BASE harness compilation. They still execute the actual Reactor,
hosted startup, producer send/disposal, and validation handler chain. The dynamic
validation subclass implements only the test-supplied validation callback, not
production Handle/HandleAsync behavior. No framework or production stub is added.

Missing required production APIs now produce explicit xUnit assertions instead
of null dereferences or unqualified custom exceptions. SQS requires NackAsync
before entering its HTTP wait. For Kafka BASE, which predates consumerFactory,
the fixture loads the authentic cached librdkafka binary through the real native
loader, invokes the real constructor, and substitutes only the transport client.
Implementations exposing the optional constructor seam still take that path;
the sealed clock-layout equivalent remains accepted by design. Assembly loading,
native dependencies, fixture setup, or compiler failures remain invalid results.
The Kafka blocking assertion is retained; its message formatting changes only.
The grader now exposes harness_errors, verifier_setup_errors, and
invalid_test_nodes. A zero reward cannot certify a run with any invalid node.

The Attempt-005 parser and its regression tests are byte-identical. The ten F03
cases, nine patches, strict assertion qualification, behavior-only node 4070,
canonical requirements, public/owner facts, production archives, GOLD,
dependency versions, framework conditions, and image recipes are unchanged.
The existing renderer refreshes the node-4070 harness binding and exact asset
hashes. The historical, inactive tests/test.patch remains unchanged and hash-bound.

F04 retains actual network-disabled UID/GID-1000 BASE/GOLD matrix evidence in
`closure-093-current-v4-controls-v1/F04_CURRENT_HANDOFF.json`: 79/83 projects,
293/309 original project-framework pairs, 408 authentic package archives, GOLD
feature smoke, real CS1029 rejection, and successful recovery. The successor
binding at `model/scratch/attempt-006-evidence/F04_BINDING.json` checks unchanged
environment, source/GOLD, and matrix-probe inputs against the frozen inventory,
verifies the referenced matrix receipts, and binds them to the refreshed repair
manifest. It is evidence reuse by exact dependency equality, not new execution
or a claim that the prior image already contains this C# harness correction.

Local Python suites, receipt checks, shell syntax, and asset checks are recorded
in `model/scratch/attempt-006-evidence/`; no .NET or container was executed here.
Fresh strict native BASE/GOLD and all ten F03 target-plus-complete-verifier runs
remain required on this integrated package. BASE must contain exactly 29 complete
genuine behavior_failure F2P nodes and one passing P2P, with zero invalid nodes;
GOLD must pass all 30. `model/scratch/PROBES-ATTEMPT006.md` supplies separate
1800-second requests and a bounded wrapper without changing any control gates.
No unrelated deployed-dialogue, solver capture/replay, or complete-verifier
compiler-error/stale-DLL obligation is closed. Whole-task readiness remains false.

## Attempt-005 — distinguish xUnit assertion summaries from runner errors

Controlled feedback `iteration-history/1790091873234393374/FEEDBACK.json`
(SHA256 `730da352e4c01f1e90c6a78ec979260ff56d5d59f96a698490f495e933ef0769`)
supersedes the unexecuted-current-image statements in Attempt-004 below. Paths in
this section are relative to the row directory unless stated otherwise. The
supervisor's `program/run-9894144bcb3f/RESULT.json` binds the fresh image and native
BASE/GOLD acceptance. No historical report or receipt has been rewritten.

F04's two actual network-disabled, solver-permission matrices passed in
`targeted/run-0617d2d156d8/00-matrix_base/data/results/matrix-base/ACCEPTED.json`
and `01-matrix_gold/data/results/matrix-gold/ACCEPTED.json` under the same targeted
run. They built 79/83 delivered projects and 293/309 original project-framework
pairs, respectively. GOLD feature smoke, both real CS1029 compiler controls and
post-restoration recovery passed; BASE feature smoke remains explicitly not
applicable. All recovered dependencies, image recipes, public build commands,
original framework conditions and package constraints are retained unchanged.
No further dependency repair is supported by this feedback.

F03's GOLD, no-public-IsLocalHeader and structural-integration-equivalent controls
also passed their target and all 30 verifier nodes. All seven compiling negatives
reached the intended production-behavior assertions. However, the task-owned
`tests/private-runtime/segpipe-environment/run_native.py` treated xUnit VSTest's
ordinary `[xUnit.net timestamp] test-name [FAIL]` RunInfo summaries as infrastructure
errors, despite complete counters and corresponding assertion messages/stacks.
This incorrectly produced `test_result_incomplete`, and the strict probes stopped
before their complete-verifier phase. This is neither a production defect nor a
reason to accept incomplete/environment failures as mutation rejection.

The reader now separates only exact Error summaries naming a corresponding failed
assertion with a stack in a completed result set. It preserves every RunInfo text
and outcome in `run_info`, the matched summaries in `assertion_summaries`, unmatched
errors in `run_errors`, and the original TRX SHA256. Unexpected summaries, unrelated
errors, incomplete results, assembly/fixture failures and abnormal process exits
still cannot qualify. Regression tests exercise these distinctions, including an
ordinary summary mixed with a real host error. No shared runner is edited.

The host replay at `model/scratch/attempt-005-evidence/TRX_REPLAY.json` binds both
reader versions and the original immutable receipts: 93 previously passing TRXs
remain passing, and all seven negative TRXs now qualify against the unchanged
probe's exact intended assertion/class/method/stack requirements. This is Python
reclassification of already executed evidence, not new .NET execution and not
proof of those seven unperformed full-verifier runs.

The behavior-only node-4070 repair, all C# integration assertions, test patch,
node manifests, GOLD patches, nine production-control patches, strict probe,
canonical contract and public/owner projections remain unchanged. The
existing renderer refreshes the exact successor asset hashes. Ten fresh F03
target-plus-complete-verifier controls are requested in
`model/scratch/PROBES-ATTEMPT005.md`; no compiler/setup/timeout result may replace
an intended assertion failure. Native BASE/GOLD remains supervisor-scheduled.
Whole-task readiness, deployed dialogue and actual solver capture/replay are not
claimed by either these repairs or the retained public matrix successes.

## Attempt-004 — integrate the independently validated dependency recovery

This section supersedes earlier unresolved-dependency statements below without
rewriting any historical report, failure, or receipt. The controlled feedback at
`iteration-history/1790087611159208498/FEEDBACK.json` directs integration of
`closure-093-dependencies-v1/HANDOFF.json` (SHA256
`647737a7c217675a24ada7e31f7bfdfc1af27103de04fa5014b0caee1f51aecd`). The supervisor's
root review approves integration, not issue closure or current-package acceptance.

The successor now contains all 408 genuine signed dependency archives from that
handoff. Only the 340 missing, individually verified package-version directories
were imported; all original 68 archives and expanded files remain byte-identical.
No broad cache, Git tree, candidate source, or reconstructed restore assets were
copied. `environment/dependency-recovery.json` binds each archive, original-archive
hash, supervisor signature receipt, and handoff. The existing renderer generates
`environment/offline-package-manifest.json` for all installed package input files,
then binds it and updated public/owner projections in `repair-version.json`.
Host SHA256 verification is not a new signature verification or .NET execution.

The tested public build script now restores the actual current source graph and
builds one temporary solution, retaining every project's declared frameworks and
central version conditions. It never copies stale BASE assets onto GOLD. Forcing
all projects to net10.0 caused NU1010 for the original net8/net9-only MySql
EntityFrameworkCore/Pomelo conditions; adding a new pin or removing that project
would change the task instead of fixing the environment. Preserving the original
graph covers 79 BASE / 83 GOLD projects and 293 / 309 project-framework pairs.
This compatibility correction changes neither production source nor package
constraints, source archives, locks, GOLD patches, smoke assertions, or grader
gates. The focused private verifier retains its sealed net10 profile. Public docs
now distinguish that profile from the all-original-framework source build and
distinguish compilation from execution across runtimes.

Both fresh image recipes place the cache at `/opt/segpipe-nuget/packages`, set
`NUGET_PACKAGES`, and retain the old root-cache path as a compatibility symlink.
The recipes and documentation were not in the independently validated image;
they still require the supervisor's fresh current-package image build and native
BASE/GOLD acceptance. The independent image's success cannot stand in for those.

The scratch `probe_offline_original_matrix.py` integrates the final handoff's
post-compiler-recovery DLL snapshots. Each arm has a 1700-second internal total
deadline and an 1800-second outer budget, uses real restore/build, checks every
original project/framework and evaluated reference inventory, requires only the
injected CS1029 for its compiler negative, then requires successful recovery.
BASE excludes only the unchanged GOLD-feature smoke; GOLD must pass it. Missing
packages, setup, timeout, unexpected diagnostics, or incomplete outputs fail the
probe. No stub replaces framework behavior. Historical overwritten-output hashes
and all previous failed evidence remain untouched.

F03's behavior-only node-4070 repair, real production integration assertions,
strict failure classification, seven compiling-negative candidates, and both
structural equivalents are retained unchanged. Their ten separate target-node
plus full-verifier runs remain required on the new image, independently of the
public dependency matrix. No claim of their execution or whole-task readiness is
made. Current bindings and host-only checks are in the row's
`model/scratch/attempt-004-evidence/`; control instructions are in
`model/scratch/PROBES-ATTEMPT004.md`.

## Attempt-003 correction to the offline matrix

Retained feedback `iteration-history/1790075764534008739/FEEDBACK.json` identifies
a probe defect independent of missing dependencies: the previous scratch probe
required GOLD feature smoke on BASE. `environment/public-smoke/Program.cs` loads
`Paramore.Brighter.RejectionReason`, parses `DeliveryError`, and constructs
`MessageRejectionReason`; these new feature types are absent from BASE. Providing
packages cannot make this feature smoke pass on authentic BASE.

The scratch `probe_offline_matrix.py` now requires explicit `--arm base|gold` and
matches that arm's complete project inventory. Both arms require successful
focused/full preflight and builds (79 BASE / 83 GOLD projects), successful SDK
and package/framework-reference evaluation, strict injected CS1029 rejection,
and successful focused recovery. GOLD additionally requires the unchanged public
feature smoke. BASE records that smoke as `not_applicable_to_base`, not a pass,
environment failure, or successful mutant rejection. The probe writes its exact
matrix contract and arm into the evidence. No production or smoke assertions,
package constraints, source archives, locks, test patches or previous F03 controls
change. The new local arm-selection tests and retained diagnostic tests exercise
Python logic only; no compiler or container was executed here.

The later supervisor receipt `program/run-0442cf60bf46/RESULT.json` records the
attempt-002 native BASE reward 0 / GOLD reward 1 pair on image
`sha256:87b68f570115db0af11cc3a78ec37542edf0df356ff4b299cc989ebf035606ec`, bound in the
inspection to repair manifest
`8441bd532ab6d26ce88a3508378b67d3a9e5e65df1e14f2015a759c3f71bfcca`.
That is historical execution evidence, not proof of the ten F03 control cases or
offline closure. Original receipts and failed evidence remain unchanged. The
attempt-003 changes and checks are bound separately in
`model/scratch/attempt-003-evidence/ATTEMPT_RESULT.json` relative to the row.

The dependency/image owner still must provide the authentic original transitive
package closure and restore inputs. Known missing pins include AWSSDK.SQS
4.0.2.13, AWSSDK.SecurityToken 4.0.5.8 and AWSSDK.SimpleNotificationService 4.0.2.15
from BASE `environment/Directory.Packages.props:9`, and GOLD's FluentValidation
11.12.0. These examples are not a complete closure list. The 68 supplied package
archives do not supply them, and no supervisor evidence index is present. No
archive/daemon/network access or later implementation packages are proposed.
After provenance-bound provisioning and image sealing, run the corrected matrix
on each arm at solver permissions. All ten F03 cases also still need targeted
runtime evidence. This continuation does not declare whole-task readiness.

## Attempt-002 correction to control evidence

The supervisor's retained `program/run-30f00dcc2b8a/RESULT.json` records a native
BASE reward 0 / GOLD reward 1 pair for the prior successor snapshot. That snapshot
has repair-manifest SHA256
`c2b9b184527e913830bdbc650ec04aeed074333034d0a6d78165e97731700ec7` and native-runner
SHA256 `f363d1029fcdedc4a8ff37d2f9b056c3317f0c2b93320bf3845610d875db49cc`.
It does not validate the reporting changes below or the seven mutations. Preserve
that receipt and the rejected control inspection at
`iteration-history/1790069937371338231/FEEDBACK.json`; neither is rewritten.

This continuation fixes their demonstrated classification gaps. Native test
timeouts, abnormal process exits, incomplete/empty/skipped TRX runs and unknown
runtime exceptions can no longer become `behavior_failure`. Ordinary exit 1,
complete counters/results and assertion messages with stacks are required.
The complete grader preserves abnormal exits even when a result file exists and
counts execution/result/timeout errors separately. Reward gates and C# assertions
are unchanged.

The scratch F03 probe copies the standalone target TRX before the full verifier
can overwrite it, independently checks every full-verifier node's actual process
exit, completed TRX and hash, and binds the intended test method, assertion kind
and stack frame for each negative. `CONTROL.json` retains those qualifying
messages/stacks, target/full TRX hashes and runner/probe hashes. Execute the seven
negatives in separate disposable containers, plus gold and both equivalents;
the older group wrapper is not the bounded acceptance recipe.

The scratch offline probe now accepts only exit 1 with completed CS1029 compiler
diagnostics from the injected source file and its real project. Timeout, signal,
restore/setup/other compiler diagnostics or mixed failures are rejected. Successful
source restoration and focused recovery remain mandatory. Its Python unit checks
exercise report parsing only, not .NET or dependency closure.

F04 provisioning remains blocked. No complete authentic pinned package closure
was supplied, and `SUPERVISOR_EVIDENCE_INDEX.json` is absent. The host image archive
is not a permitted control-container input; the prior archive script is retained
for evidence, not requested as an executable container probe. The dependency/image
owner must provide provenance-bound original package bytes and restore inputs for
all 79 BASE / 83 GOLD projects, including the original SQS v4 pins and GOLD's
FluentValidation 11.12.0. No source constraints, locks, image recipe, production
archives or acceptance scope have changed. A fresh full matrix is still required
after authentic provisioning. All original static failing preflights remain.
The inspected original author/DeepSWE environments have no package cache. The
later `full-agent-staging-v3-semantic-20260918/.../093-cowork-author-batch-503708-0/delivery`
environment does have a cache, but its 68 archive hashes exactly match this
successor's incomplete cache; it adds none of the missing pinned inputs. This
clarifies the initial submission's broader wording about delivery environments.

Current local reporting tests, exact asset comparison and successor hashes are
recorded separately in the row's `model/scratch/attempt-002-evidence/`. They are not
native executions. The following original repair rationale remains applicable;
its pending-runtime statements describe the initial submission, not the historical
native pair recorded above.

This is an unvalidated successor of `repair-093-v4`, not a replacement for any
historical execution report. `REPAIR_VALIDATION.md`, `EXPORT_RECEIPT.json`, and
`semantic-runtime-version.json` remain unchanged historical evidence. The reviewed
parent task.toml SHA256 is
`1ed2608f0bbbf40b6d3b77689df8c196b819e7e927284b67deb176c7d00432e8`.
The review SHA256 is
`b454d7269c8a0eca8e1c06331b33421ac8b57bfd09a528575cda204ee410376e`;
the runtime evidence index SHA256 is
`36f7e7c0fe805f62a007299fa1e77560e4f1a21b557807c89c22ba04a5bb57ac`.

## 093:F03 — implemented, runtime controls pending

The baseline MessageHeader has no IsLocalHeader API. Assignment item 24 requires
local-header filtering, while the published addendum specifies RegisterLocalHeader
and BagWithoutLocalHeaders. Neither establishes an IsLocalHeader compatibility
requirement. The gold patch introduces that additional helper, which is not a
reason to require every implementation to expose it.

Node 4070 replaces its IsLocalHeader assertion with a production filtering check
after repeated registration; it no longer reflects on that extra helper. Its calls into real production
registration/filtering remain, including filtering a newly registered key,
retaining ordinary values and their identity, preserving the original bag, and
idempotent registration. No filtering assertion was removed. All other nodes,
real startup/validation/Reactor/confirmation tests, reward thresholds, original
gold plus its sealed supplemental patch, and solver time budget remain unchanged.

`tools/render_contract_assets.py` generates the node binding, public/owner
version projections and exact hashes. It also binds all active node source and
project manifests and the unchanged `tests/test.patch`. The latter is a historical
source patch, not the private runtime harness used by the native runner; rewriting
it would not change node 4070. No target source, archive, package constraint or
dependency lock is modified.

The row's `model/scratch/f03-controls` contains nine gold-relative production
patches: a consistent helper rename eliminating IsLocalHeader, a combined
structurally equivalent implementation, and negative registered-key leakage,
startup no-op, validation bypass, inclusive window boundary, missing window reset,
lost confirmation context and reversed callback-order implementations. Each patch
is bound to its input source hashes and has passed `git apply --check`; this is not
a claim of C# compilation. `probe_f03_matrix.py` runs the corresponding real native
node and complete `/tests/test.sh`, rejects setup/restore/compiler errors as
mutation evidence, and preserves node receipts and logs. Gold and equivalents must
pass all 30 nodes; negative controls must compile and fail behavioral assertions
at their relevant nodes. Supervisor execution is still required.

## 093-cowork:F04 — provisioning blocked, scope unchanged

The delivered matrix still requires every source project on net10.0: 79 in BASE,
83 after the unchanged GOLD patches add Testing and three Validation projects.
The prior public-projection probe used the package baseline, even in its gold
container; its 79-project count does not describe the patched gold worktree. The nine
asset files include a project not present in baseline, so only eight baseline
projects have matching restore assets. There are 68 nupkg archives, not a complete
all-source dependency closure. Static inventory is not MSBuild evaluation.

`environment/Directory.Packages.props` defines AWSSQSV4=4.0.2.13,
AWSSecurityTokenV4=4.0.5.8 and AWSSDKSimpleNotificationServiceV4=4.0.2.15.
`src/Paramore.Brighter.MessagingGateway.AWSSQS.V4/*.csproj` uses these explicit
VersionOverride properties. The supplied cache contains only v3 of these packages.
Other missing direct package families include Azure, Google Cloud, database,
scheduler and hosting dependencies. GOLD additionally requires its original
FluentValidation 11.12.0 pin. A new host static preflight of the materialized gold
source reports 83 projects, 78 findings, 74 projects without matching assets, and
exit 78. This is not a .NET build result. These facts do not justify changing pins,
importing target Brighter packages, or reducing acceptance to the focused projects.

Read-only research covered the canonical original author's SOURCE_CONTRACT.json,
PROVENANCE.md, original DeepSWE environment, its delivery environment, the reviewed
source package, and the prior row-specific native evidence. The original
author/delivery environments do not contain a NuGet cache. No readable complete
original package closure was found. A relevant preserved image archive exists at
`/data2/leixinping/release_tasks/image-archives/brighter-f9dd17551dec-environment.tar`
but reading it returned PermissionError. No permissions were changed or bypassed,
and no network, daemon or credentials were used. Its contents are not claimed to
contain the missing packages.

The row's scratch `offline-input-inventory.json` records declared requirements,
existing package hashes and unchanged source bindings; the separate
`gold-offline-input-inventory.json` covers all 83 patched projects without modifying
gold. `probe_archive_packages.py`
is a bounded, read-only supervisor metadata request to inventory only relevant
nupkg members in that archive; it does not copy Git or dependency trees or install
anything. If the exact original closure can be recovered, stage only required
original package bytes and restore inputs, retain provenance, regenerate bindings,
and rebuild the image. If it cannot, the image/dependency owner must provide that
closure. Arbitrary replacement versions or fabricated packages are not acceptable.

`probe_offline_matrix.py` must then run at solver permissions in fresh BASE and
GOLD containers with networking disabled: evaluated references for every project
(79 BASE, 83 GOLD),
SDK/runtime inventory, focused/full preflight and builds, smoke, followed by a real
compiler-error control and recovery. Missing inputs or failed builds are failures,
never successful F2P negatives. Until provisioning and these gates succeed, F04
is unresolved and the whole task is not ready.
