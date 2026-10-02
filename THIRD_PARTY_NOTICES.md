# Third-party notices

This repository is Apache-2.0 licensed (see `LICENSE`). It also carries, or fetches at run time, benchmark material from other projects, each under its own terms. The vendored Harbor task sets (Terminal-Bench, Terminal-Bench-Science, DeepSWE; Apache-2.0) are attributed in `NOTICE`; the two sources below are converted rather than vendored. Per-benchmark provenance (upstream commit, digests, what was copied or left out) is in `benchmarks/<id>/SOURCE.md`.

| Source | Licence | In this repository | Where |
| --- | --- | --- | --- |
| [AutomationBench](https://github.com/zapier/AutomationBench) (Zapier), commit `4a8e1061254004d9dac807054eed33fad7d1ff14` | MIT | vendored package and generated tasks | `benchmarks/automation-bench/` |
| [rag-bench-essential](https://github.com/Prism-Shadow/rag-bench-essential) (PrismShadow), commit `979adae32d59c1b9a8a9d4ebd761c11c9d0f6e29` | MIT (code); case payloads under their source benchmarks' terms | **not stored**: fetched and converted at run time | `benchmarks/rag-bench-essential/`, `tools/rag_bench/` |

## AutomationBench

Copyright 2026 Zapier, Inc. Licensed under the MIT License; the full licence text, including Zapier's "Scope of license" note that the MIT grant does not cover the representations of third-party API endpoint structures, is kept with the vendored copy at `benchmarks/automation-bench/vendor/automationbench-4a8e106/LICENSE` and installed in every task image at `/opt/automationbench/LICENSE`. The vendored source files keep their `SPDX-License-Identifier: MIT` headers. The generated tasks under `benchmarks/automation-bench/tasks/` contain AutomationBench task data (prompts, simulated initial states, assertions) under the same licence. AutomationBench carries no canary string.

## rag-bench-essential

Copyright 2026 PrismShadow. The repository's code (scorer, validators, reference solutions) is MIT-licensed. Its case payloads are derived from Spider 2.0, BrowseComp-Plus, DocFinQA, DocVQA, LongData, MultiHiertt, WorkspaceBench, DVWorld, BankerToolBench, FinLongDocQA, DABstep, PrepBench, SpreadsheetBench, HarveyLab/REPS and FDABench/BIRD app-store data, and remain subject to those sources' licences and access terms (upstream `THIRD_PARTY_NOTICES.md`). This repository therefore stores none of it: `tools/rag_bench/fetch.sh` downloads the pinned commit from the public upstream repository into a git-ignored directory, and `tools/rag_bench/convert.py` builds the Harbor tasks from it locally. The BrowseComp-Plus (DCI) case is excluded: its question and answer are BrowseComp-Plus plaintext, which that benchmark distributes only in encrypted form, and its corpus is a separate Hugging Face download. None of the ten converted cases carries a canary string.
