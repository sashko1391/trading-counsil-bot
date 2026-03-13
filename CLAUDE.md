# CLAUDE.md — Project Instructions

## Permissions
- You may read, create, edit, and delete any files in this repository
- You may run any shell commands including install, build, test, lint, and git operations
- You may commit changes without asking for confirmation
- You may push to the current branch without asking
- You may create and switch branches freely
- You may run tests and fix failing tests automatically
- You may install/update dependencies (pip, npm, etc.)
- You may modify configuration files (.env excluded — never commit secrets)
- You may create, rename, move, and delete files and directories as needed
- You may run long-running processes (servers, watchers) in background

## Workflow Preferences
- Act autonomously — do not ask for confirmation on routine operations
- Fix lint/type/test errors immediately when encountered
- If a test fails after your change, fix it before reporting back
- Prefer editing existing files over creating new ones
- Keep commits atomic and meaningful
- Run tests after making changes to verify correctness
- Use Ukrainian for communication, English for code/comments

## Project Context
- Python 3.10+ project, use modern Python idioms (match/case, type hints, dataclasses)
- Package structure: source in `src/`, config in `config/`, tests in `tests/`
- Entry point: `python -m main` (from `src/`)
- Test runner: `pytest tests/ -v`
- Install: `pip install -e .`
- Virtual env expected at `venv/`
- Pydantic v2 for all data models
- Async-first where possible (aiohttp, asyncio)
- loguru for logging (not stdlib logging)

## Code Style
- Type hints on all function signatures
- Docstrings only where logic is non-obvious
- No unnecessary abstractions — keep it simple
- Follow existing patterns in the codebase
- snake_case for variables/functions, PascalCase for classes

## Security
- Never commit .env, API keys, or credentials
- Never log secrets or tokens
- Validate external input (API responses, user data)

## Git
- Branch naming: feature/<name>, fix/<name>, refactor/<name>
- Commit messages: concise, imperative mood, English
- Main branch: `main`
