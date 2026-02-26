# GitHub Review Agent

A CLI tool for analyzing and reviewing git changes. It examines diffs, identifies potential issues, categorizes changes, assesses risk, and recommends appropriate actions.

## Features

- **Git Diff Analysis**: Analyze changes from current branch or commit ranges
- **Issue Detection**: Find bugs, security vulnerabilities, code smells, TODOs, and more
- **Change Categorization**: Classify changes as feature, bugfix, refactor, documentation, test, chore, style, security, or performance
- **Risk Assessment**: Evaluate risk level (low/medium/high) based on multiple factors
- **Action Recommendation**: Recommend creating an issue, PR, or no action with evidence-based justification

## Installation

```
bash
# Clone the repository
git clone <repository-url>
cd github-agent

# Install dependencies
pip install -r requirements.txt

# Install the package
pip install -e .
```

## Usage

### Review Current Branch Changes

```
bash
# Review changes in current branch vs default branch (main/master)
github-review branch

# Or use the short form
github-review
```

### Review Commit Range

```
bash
# Review changes between commits
github-review commits abc123..def456

# Or use the range argument
github-review abc123..def456
```

### Options

- `--branch, -b`: Specify a branch to compare against (default: main/master)
- `--no-colors`: Disable colored output
- `--help`: Show help message

## Output

The tool provides a comprehensive report including:

1. **Summary**: Files changed, additions, deletions, category, and risk level
2. **Detected Issues**: Issues grouped by severity (error, warning, info)
3. **Risk Assessment**: Score, factors, and justification
4. **Recommended Action**: Create Issue, Create PR, or No Action
5. **File Changes**: List of modified files with change statistics

## Example Output

```
============================================================
              Git Change Review Report                     
============================================================

--- Summary ---
  Files changed: 5
  Additions: +120
  Deletions: -30

  Category: FEATURE
  Risk Level: MEDIUM

--- Detected Issues (3) ---
  Warnings (2):
  • Debug print statement left in code
    → src/utils.py:42
  • Bare except clause - catches all exceptions
    → src/handler.py:15

  Info (1):
  • TODO comment found
    → src/features.py:10

--- Risk Assessment ---
  Score: 4.5
  Level: MEDIUM

  Factors:
    • Category: feature (+3.0)
    • Found 2 warning(s)

--- Recommended Action ---
  Action: Create Pull Request

  Justification:
    Changes ready for review with 3 minor issue(s)

--- File Changes ---
  M src/utils.py +15 -5
  M src/handler.py +25 -10
  A src/features.py +50 -0
  M tests/test_utils.py +20 -10
  M README.md +10 -5
```

## How It Works

1. **Git Analysis**: Uses `git diff` to extract file changes
2. **Code Analysis**: Scans for patterns indicating bugs, security issues, code smells
3. **Categorization**: Classifies changes based on file paths, names, and commit messages
4. **Risk Scoring**: Calculates risk score based on category, issues, and change scope
5. **Decision Logic**: Recommends action based on risk level and issue severity

## Requirements

- Python 3.7+
- Git
- click
- colorama

## License

MIT License
