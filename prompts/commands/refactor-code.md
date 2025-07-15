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

---

### Key Rules

- NEVER do big-bang rewrites
- ALWAYS deploy behind feature flags
- Each refactor must pass tests before next step
- File size must decrease every sprint

---

**Success = Zero downtime + Faster delivery + Readable code**