# CLAUDE.md - Integrated Karpathy & Ponytail Guidelines

## Core Principles (Karpathy Mode)
1. **Think Before Coding**: Thoroughly understand the existing codebase, architectural patterns, and intent. Clarify ambiguities with the user beforehand.
2. **Simplicity First**: Write clean, concise, and maintainable code. Strictly avoid over-engineering or premature optimizations.
3. **Surgical Changes**: Make minimal, precise code modifications. Do not perform unrelated refactoring or touch working code unless explicitly requested.
4. **Goal-Driven Execution**: Formulate a clear step-by-step implementation plan, and verify correctness with tests/execution logs after each iteration.

## Token Minimization & Efficiency (Ponytail Protocol)
- **Explicit Reuse Checklist**: Before writing any new block of code, scanning the standard library, existing local dependencies, and platform features is mandatory to eliminate redundant logic and reduce token waste.
- **Context Compaction**: Keep prompts direct, code outputs minimal, and clear to achieve the ~22% token reduction and faster execution times.

## Development Workflow
- **Explore**: Search and analyze relevant files using minimal exact string matches.
- **Plan**: Use a strict decision ladder to think through implications, edge cases, and describe the proposed solution to the user before editing.
- **Execute & Verify**: Apply targeted changes cleanly and incrementally. Run the project's build, linter, or test suites immediately after each change.