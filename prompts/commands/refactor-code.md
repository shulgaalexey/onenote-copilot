# TL;DR: File Refactor Workflow

**Core Philosophy:**
Treat large file refactoring like surgery on a live patient – one wrong cut kills the system.

---

## 3–Phase Approach

1. **SAFETY NET** (Before touching anything)
    - Write tests for at least 80% behavior coverage
    - Set up feature flags for every change
    - Create micro-branches (<200 line PRs)

2. **SURGICAL PLANNING**
    - Find complexity hotspots
    - Map cohesive code islands
    - Order by risk (lowest first)

3. **INCREMENTAL EXECUTION**
    - Extract in 50–150 line chunks
    - Start with private methods (safest)
    - Progress to classes, then interfaces
    - Use Strangler Fig for high-coupling areas
    - **MANDATORY**: Use TEST_RUN.md approach for all test validation:
      ```powershell
      python -m pytest tests/ -v --cov=src --cov-report=term-missing > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"
      ```
    - Wait for `%TESTS FINISHED%` marker before proceeding to next refactor step
    - **🚨 CRITICAL**: Log ALL file deletions in `DEL_FILES.md` before removing

### 🗂️ File Deletion During Refactoring
**MANDATORY for any files removed during refactoring:**

#### Before Deleting Any File:
1. **Log in DEL_FILES.md** with complete details
2. **Include refactoring context** - what replaced the deleted file
3. **Document migration path** - how functionality was moved
4. **Verify tests still pass** after deletion

#### Refactoring Deletion Template:
```markdown
**File Path**: `src/legacy/old_implementation.py`
- **Reason**: Refactored into smaller, focused modules
- **Context**: Functionality moved to src/new/module_a.py and src/new/module_b.py
- **Deleted by**: [Refactoring Agent/Developer]
- **Date**: YYYY-MM-DD
- **Migration**: See refactoring commit for functionality mapping
```

---

### Key Rules

- NEVER do big-bang rewrites
- ALWAYS deploy behind feature flags
- Each refactor must pass tests before next step
- File size must decrease every sprint
- **NEVER delete without logging in DEL_FILES.md**

---

**Success = Zero downtime + Faster delivery + Readable code**