name: "Indexing Commands Clarification & Unification"
description: |
  A PRP to analyze and refactor the OneNote Copilot indexing commands, clarifying differences between the direct CLI invocation and the interactive slash command, and unifying them into a simpler, more intuitive interface.

## Purpose
Provide a clear, consistent, and user-friendly indexing experience by merging or harmonizing the two existing `/index` workflows into a single, documented command set.

## Goal
- Eliminate confusion between `python -m src.main index` and `python -m src.main` + `/index`.
- Define a unified command signature (flags and options) that works identically in both contexts.
- Simplify internal implementation so there is one core indexing function used by both entrypoints.

## Why
- **User Experience**: Users should not have to learn two separate ways to trigger indexing.
- **Maintenance**: One implementation reduces duplication and potential divergences.
- **Documentation**: A single command is easier to document and teach.

## What
- Review `src/main.py` index command handler and `src/cli/interface.py` slash handler.
- Decide on a single CLI signature (e.g., `index [--initial|--sync|--status]`) for both modes.
- Refactor code to route both modes through a shared indexing function in `onenote_search` or a new helper.
- Update tests and documentation accordingly.

### Success Criteria
- [ ] Interactive and direct CLI both accept the same flags and options.
- [ ] Internal code duplication removed; single core indexing implementation.
- [ ] User documentation updated; only one `/index` command shown.
- [ ] All existing tests continue to pass without change to user-facing behavior.

## All Needed Context
```yaml
- file: src/main.py  # current index command definition
- file: src/cli/interface.py  # slash-based index handler
- file: src/tools/onenote_search.py  # core indexing logic
- file: README.md  # documentation for index commands
```

## High-Level Tasks
```yaml
Task 1:
  - Analyze current indexing entrypoints in `src/main.py` and `src/cli/interface.py`
  - Document behavioral differences

Task 2:
  - Design unified command signature and option parsing
  - Update Typer and slash handler to use same signature

Task 3:
  - Extract or refactor core indexing logic into shared helper/module
  - Ensure both entrypoints delegate to the helper

Task 4:
  - Update documentation (README.md and help text)
  - Add or adapt tests to verify both contexts work identically

Task 5:
  - Validate via test suite and manual interactive tests
```

## Implementation Blueprint
Use GitHub Copilot agent mode to generate refactoring changes, ensuring Windows/PowerShell compatibility and compliance with existing test patterns.
