# Contributing to MCPHammer

Thank you for your interest in contributing to MCPHammer!

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Getting Started

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- An Anthropic API key (for Claude integration features)

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork:

```bash
git clone https://github.com/YOUR_USERNAME/MCPHammer.git
cd MCPHammer
```

3. Add upstream remote:

```bash
git remote add upstream https://github.com/praetorian-inc/MCPHammer.git
```

### Development Setup

1. Create a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

3. Verify setup:

```bash
pytest tests/ --collect-only
```

## Making Changes

### Create a Branch

Always create a feature branch for your changes:

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### Commit Messages

Follow conventional commit format:

```
type(scope): description
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
```
feat(tools): add new MCP tool for X
fix(server): handle timeout correctly
docs(readme): add installation instructions
```

## Testing

### Run All Tests

```bash
pytest
```

### Run with Coverage

```bash
pytest --cov=. --cov-report=html
```

## Pull Request Process

1. Sync with upstream:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. Run tests and ensure they pass

3. Push your branch and create a Pull Request

4. Fill out the PR template with:
   - Description of changes
   - Related issues
   - Testing performed

## Questions?

- Open an issue for questions
- Contact: opensource@praetorian.com

Thank you for contributing!
