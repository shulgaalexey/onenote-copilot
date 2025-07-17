name: "Current Architecture Documentation: Production System Analysis"
description: |
  Comprehensive documentation and analysis of the current OneNote Copilot CLI architecture,
  comparing implemented solution against original design specifications.

## Purpose
Document the actual implemented architecture of OneNote Copilot CLI, analyzing alignment with original PRP specifications and identifying architectural decisions made during development.

## Goal
Create comprehensive architecture documentation covering:
- Current module structure and component relationships
- Design pattern implementation and adherence
- API integration architecture and data flow
- Deviation analysis from original specifications

## Success Criteria
- [ ] Complete architectural diagrams of current implementation
- [ ] Module-by-module documentation with responsibilities
- [ ] API integration flow documentation
- [ ] Design pattern compliance analysis
- [ ] Architectural decision record (ADR) for deviations

## Tasks
```yaml
Task 1: Module Architecture Analysis
DOCUMENT src/ structure:
  - MAP: Current module dependencies and relationships
  - ANALYZE: Component separation and cohesion
  - VERIFY: Design pattern implementations (Repository, Factory, etc.)
  - ASSESS: Code organization against original specifications

Task 2: API Integration Architecture
DOCUMENT external integrations:
  - MAP: Microsoft Graph API integration patterns
  - ANALYZE: Authentication flow and token management
  - DOCUMENT: LangGraph agent architecture and state management
  - VERIFY: Rich CLI integration and streaming patterns

Task 3: Data Flow Documentation
CREATE architectural diagrams:
  - DIAGRAM: User query → Agent → Tools → API → Response flow
  - MAP: Error handling and recovery paths
  - DOCUMENT: Configuration and settings management
  - ANALYZE: Performance bottlenecks and optimization points

Task 4: Compliance Assessment
COMPARE with original PRP:
  - VERIFY: All specified components implemented
  - IDENTIFY: Architectural deviations and reasons
  - ASSESS: Quality metrics against requirements
  - DOCUMENT: Technical debt and improvement opportunities
```

## Documentation Outputs
```yaml
DELIVERABLES:
  - architecture_overview.md: "High-level system architecture"
  - module_documentation/: "Detailed module responsibilities"
  - api_integration_flows.md: "External API integration patterns"
  - design_decisions.md: "ADR for architectural choices"
```

## Analysis Commands
```powershell
# Generate dependency graph
python -c "import src; help(src)" > module_analysis.md

# Code metrics analysis
python -m py_todo src/ > technical_debt_analysis.md

# Architecture visualization
tree src/ /f > current_structure.md
```

## Confidence Score: 9/10
Straightforward documentation task with existing codebase to analyze, clear deliverables.
