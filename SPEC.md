# GitHub Review Agent - CLI Tool Specification

## Project Overview
- **Project Name**: GitHub Review Agent
- **Type**: CLI Tool (Python)
- **Core Functionality**: Analyzes git changes (branch diff or commit range), identifies issues, categorizes changes, assesses risk, and recommends actions (Create Issue, Create PR, or No action)
- **Target Users**: Developers and DevOps engineers who want automated code review assistance

## Functionality Specification

### Core Features

1. **Git Diff Analysis**
   - Analyze current branch changes vs default branch (main/master)
   - Analyze changes between commit ranges
   - Parse file additions, modifications, and deletions
   - Extract code changes (additions/deletions)

2. **Issue Detection**
   - Identify potential bugs (e.g., TODO, FIXME, debug print statements)
   - Detect security vulnerabilities (e.g., hardcoded credentials, SQL injection risks)
   - Find code smells (e.g., long functions, duplicate code, magic numbers)
   - Detect missing error handling
   - Identify performance concerns

3. **Change Categorization**
   - Feature: New functionality added
   - Bugfix: Bug fixes
   - Refactor: Code restructuring without behavior change
   - Documentation: Docs added/updated
   - Test: Test files added/modified
   - Chore: Maintenance tasks
   - Style: Formatting changes

4. **Risk Assessment**
   - Low: Minor changes, documentation, style fixes
   - Medium: New features, refactoring, bug fixes
   - High: Security changes, critical bug fixes, large-scale refactoring

5. **Action Recommendation**
   - Create Issue: For bugs, improvements, or feature requests needing discussion
   - Create PR: For ready-to-merge changes
   - No Action: For trivial changes (chores, formatting)

6. **Evidence-Based Justification**
   - Provide line numbers and code snippets supporting the decision
   - Link specific files and changes to the recommendation

### User Interactions

1. **CLI Commands**
   - `review branch` - Review current branch changes vs default branch
   - `review commits <start>..<end>` - Review changes in commit range
   - `review --help` - Show help message

2. **Output**
   - Summary of changes (files changed, additions, deletions)
   - Detected issues list
   - Change category
   - Risk level
   - Recommended action with justification

### Edge Cases
- No changes detected
- Invalid commit range
- Git not initialized
- No default branch configured
- Large diffs (handle pagination)

## Technical Design

### Project Structure
```
github-agent/
├── github_agent/
│   ├── __init__.py
│   ├── cli.py          # Main CLI entry point
│   ├── git_utils.py    # Git operations
│   ├── analyzer.py     # Code analysis logic
│   ├── categorizer.py  # Change categorization
│   ├── risk_assessor.py # Risk assessment
│   └── reporter.py     # Output formatting
├── tests/
├── requirements.txt
├── setup.py
└── README.md
```

### Dependencies
- Click (CLI framework)
- GitPython (git operations)
- PyYAML (optional config)

## Acceptance Criteria

1. ✅ Can analyze current branch changes
2. ✅ Can analyze commit range changes
3. ✅ Correctly categorizes at least 80% of common change types
4. ✅ Provides evidence-based justifications
5. ✅ Outputs clear recommendations
6. ✅ Handles errors gracefully
7. ✅ Works on Windows/Mac/Linux
