# Custom Commands

## --UPD

When user writes `--UPD`, perform full project documentation update:

### 1. Development Log — append, never delete
- `doc/DEVELOPMENT_LOG.md` — append new dev log entries for work done in this session

### 2. Full Source Code — regenerate
- Delete old `doc/FULL_SOURCE.txt`
- Generate new `doc/FULL_SOURCE.txt` — all project source code in one file
- Include: `.py`, `.jsx`, `.js`, `.json` (config only), `.md` (knowledge data)
- Exclude: `node_modules/`, `dist/`, `venv/`, `.git/`, `__pycache__/`, `*.pyc`, `*.png`, `*.pdf`, `*.jpg`, lock files, `data/logs/`, `.env`

### 3. Update MEMORY.md
- Update `/home/oleksandr/.claude/projects/-home-oleksandr-Documents-Repositories-trading-counsil-bot/memory/MEMORY.md` with any new relevant context from the session
- MEMORY.md is an index with links to topic files in the same directory
- Keep it under 200 lines

## --ABAIC

Reserved for AI consultation synthesis tasks. Run structured questionnaire across multiple AI models and synthesise results.
