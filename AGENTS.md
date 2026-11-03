# Project Instructions

## Start Here (Human and AI Contributors)

- Read `README.md` and `CONTRIBUTING.md` before starting a contribution.
- Use `docs/CONTEXTO-PARA-IA.md` for a portable starter prompt and handoff format.
- Read `docs/ARQUITETURA.md` for the current module map and
  `docs/ESTADO-DO-PROJETO.md` for limitations and evidence routing.
- Inspect `git status --short` and `git diff` before editing. Trace the requested
  behavior through current code and tests; do not rely on private chat history.
- At handoff, record the change, exact checks, platform, results and pending work
  in the pull request or issue. Never publish private reasoning or raw chats.
- This file is the canonical shared instruction source. Tool-specific entry
  files should point here instead of duplicating project rules.

## Purpose

This repository builds a fully offline Linux Mint terminal assistant for Java
OOP exercises. It reads a user-selected PDF from the current project folder,
derives a Java/UML contract, writes sources only inside that folder, compiles
for Java 8, runs bounded checks, and reports what was and was not verified.

## Authoritative Sources

- Current implementation and public behavior: `src/java_assistant/`,
  `packaging/linux/`, and `pyproject.toml`.
- Product architecture and constraints:
  `docs/superpowers/specs/2026-10-21-assistente-java-offline-design.md`.
- Approved design for portable session memory:
  `docs/superpowers/specs/2026-10-22-memoria-portatil-entre-sessoes-design.md`.
- Planned memory work, not proof of implementation:
  `docs/superpowers/plans/2026-10-22-memoria-portatil-entre-sessoes.md`.
- End-user operation: `docs/USO-RAPIDO.md`.
- Required Linux artifacts: `docs/ARTEFATOS-LINUX.md`.
- Executable checks and known platform evidence: `tests/`.

Historical plans describe intent at their date. When they conflict with the
current code, manifest, or newer approved specification, do not treat them as
current behavior.

## Commands

- Installed use on Linux: `java-assistente` from the exercise directory.
- Build the prepared offline bundle on Linux:
  `bash packaging/linux/build-bundle.sh`.
- Full Python suite from a Linux source checkout:
  `PYTHONPATH=src python3 -m unittest discover -s tests -v`.
- Full Python suite from PowerShell:
  `$env:PYTHONPATH=(Resolve-Path src).Path; python -m unittest discover -s tests -v`.
- Linux acceptance after building the bundle:
  `bash tests/acceptance/run-offline.sh dist/java-assistente-linux-x86_64`.

The bundle build requires the pre-fetched files described in
`docs/ARTEFATOS-LINUX.md`. Do not download, install, or regenerate those
artifacts implicitly. If a sandbox blocks the OS temporary directory, point
`TEMP` and `TMP` to a writable temporary location and report that adjustment.

## Critical Invariants

- Installation and competition use remain completely offline and require no
  API, `sudo`, network access, or connected pendrive after installation.
- The process working directory is the immutable project root and the write
  boundary. Reject absolute paths, parent traversal, and symlink escapes.
- The model has no direct shell access; the controller executes only validated,
  allowlisted actions.
- Generated sources remain compatible with Java 8 and preserve exact PDF/UML
  names, types, visibility, signatures, and inheritance.
- The Frota exercise is a fixture only. Never hard-code its classes, formulas,
  or names into product behavior.
- Model, native tools, JDK, PDF/OCR tools, and installer stay bundled; the final
  distribution must not exceed the recorded 2 GiB hard limit.
- Compilation proves syntax and types, not business-rule correctness. Never
  claim success in unavailable judge tests.
- Keep confirmed PDF evidence, inferred structure, local validation, and
  unproven behavior visibly separated.
- Portable `.assistente` memory is approved future work until its plan and
  acceptance tests are actually implemented and pass.

## Working Boundaries

- Preserve existing uncommitted changes. Inspect the diff before editing and
  use partial staging when new work overlaps an already modified file.
- Make the smallest change that satisfies the active specification; do not
  rewrite unrelated sources or silently replace recorded project knowledge.
- Keep `CRITERIOS_GERAIS.md` user-editable and preserve it across reinstalls.
- Keep credentials, machine identifiers, and private model reasoning out of
  source files, memory, logs, and documentation.
- Ask separately before installing dependencies, enabling services, committing,
  pushing, publishing, deploying, or changing external state.
- Distinguish intended checks from checks actually executed, including WSL
  evidence versus Linux Mint evidence.

## Verification

- Run the smallest relevant `unittest` module while iterating.
- Before completion, run the full Python suite with `PYTHONPATH=src`.
- For packaging changes, run `tests.packaging.test_installer`, build the bundle,
  then run `tests/acceptance/run-offline.sh` on Linux or WSL.
- Linux Mint on a real 4-6 GB, CPU-only machine is the final hardware gate for
  startup time, memory use, instruction-set compatibility, and USB copy time.
- Report exact commands, pass/fail/skip counts, environmental failures, and
  anything not verified. A timeout or sandbox failure is not a passing result.

## Context Routing

- For controller, PDF/UML, Java, safety, packaging, and hardware decisions, read
  the main design specification before changing behavior.
- For cross-session memory work, read both the memory design and its current
  implementation plan before editing code.
- For installation or operator instructions, read `docs/USO-RAPIDO.md` and
  `docs/ARTEFATOS-LINUX.md`.
- For claimed behavior, prefer current code and executable tests over prose.
