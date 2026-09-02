# lm-program

Task planning enabled

A terminal-based, OpenAI-compatible coding agent that reads, edits, and runs code in your project through a ReAct-style tool-calling loop with approvals, hooks, MCP, and session persistence.

## Install

Prerequisites: Python 3.13+ and `uv`.

Install dependencies into the project-managed environment:

```bash
uv sync
```

Build distributable artifacts:

```bash
uv build
```

This creates:

- `dist/lm_program-<version>-py3-none-any.whl`
- `dist/lm_program-<version>.tar.gz`

## First Run

After syncing the project environment, configure credentials:

```bash
uv run lm-program --configure
```

This prompts for:

- your API key
- an optional base URL for any OpenAI-compatible provider
- a model name (for DeepSeek, use `deepseek-v4-flash` or `deepseek-v4-pro`)

The values are saved in your user config file at:

- Windows: `%APPDATA%\lm-program\config.toml`
- macOS: `~/Library/Application Support/lm-program/config.toml`
- Linux: `~/.config/lm-program/config.toml`

You can still use a project-local `.env` file or `API_KEY` and `BASE_URL` environment variables, but they are no longer required for packaged installs.

## Usage

Run interactively:

```bash
uv run lm-program
```

Run a single prompt:

```bash
uv run lm-program "Summarize what this repo does"
```

Target a specific working directory:

```bash
uv run lm-program --cwd /path/to/project "Find and fix the failing test"
```

Update saved credentials later:

```bash
uv run lm-program --configure
```

Inside an interactive session:

```text
[user]> /setup                  # update saved API credentials
[user]> /tools                  # list available tools
[user]> /project                # show detected repository structure and dependencies
[user]> /mcp                    # list connected MCP servers
[user]> /approval auto-edit     # change the approval policy
[user]> /save                   # save the current session
[user]> /sessions               # list saved sessions
[user]> /resume <session_id>    # resume a saved session
[user]> /checkpoint             # snapshot the current session
[user]> /stats                  # show token/turn usage stats
[user]> /trust                  # show the latest Agent Guardian report
[user]> /guardian-demo          # run deterministic Guardian security self-tests
[user]> /demo-reset             # restore the calculator demo's initial bug
[user]> /tasks                  # list persisted task plans and retry state
[user]> /plan <title> | <step>  # create a task plan without the model
[user]> /continue-task <id>     # resume a paused task plan
[user]> /interrupt              # pause active tasks and save the session
[user]> /exit                   # quit
```

For multi-step prompts, the agent creates a persisted task plan in `.tasks/` and
shows its active todo list before each prompt. Press `Ctrl+C` or use `/interrupt`
to pause it. Resume the saved session with `/resume <session_id>` and ask the
agent to continue; it will resume the paused plan. Read-only tool calls are
retried once automatically. Write, shell, network, and task-management calls
are never automatically repeated because they can have side effects.

## Agent Guardian

Every user task runs under a deterministic local supervision layer that is
separate from the language model:

- **Test Integrity Guard** snapshots existing test files before the task. Direct
  edits to those files are blocked. If a shell command changes or deletes one,
  the original content is restored and the violation is returned to the model.
- **Prompt-Injection Firewall** treats repository files as untrusted data. It
  detects instruction overrides, secret-exfiltration requests, agent
  impersonation, and destructive instructions. After a finding, network, MCP,
  memory, and non-read-only shell actions are blocked while ordinary repository
  inspection and test commands remain available.
- **Trust Report** records inspected and changed files, commands, test outcomes,
  injection findings, blocked actions, and integrity violations. A deterministic
  score is displayed after each task and is also available with `/trust`.

The Guardian does not ask the model whether its own behavior was safe. Its
decisions are derived from local files, tool kinds, command results, and test
snapshots.

## Blocker Gate

The agent stops exploring when a task cannot proceed without unavailable
external prerequisites. If a live or private integration explicitly lacks two
or more of its SDK, credentials, or API documentation, tools are disabled before
the first model turn and the agent must report the minimum inputs needed to
continue.

During execution, the Semantic Attempt Tracker groups differently worded shell
commands by objective. Repeated package checks such as `import package`, `pip
show package`, and `find_spec(package)` share one retry budget. Two repeated
failures for the same objective, or two shell-syntax failures, activate the
Blocker Gate. This prevents endless environment probing and diagnostic files
when no meaningful progress is possible.

## Safety Confirmations

Read operations and recognised test commands run automatically. The agent asks
for confirmation before deleting files, overwriting common configuration files,
fetching or searching the web, and running `git commit`, `git push`, or `git
config`. The explicit `yolo` approval policy bypasses these prompts; `never`
rejects them.

## Automatic Verification

After a successful edit to a source file, lm-program runs checks declared by the
project: Python repositories can run configured Ruff/Mypy checks and unit tests;
Node repositories can run declared format, lint, typecheck, test, and build
scripts. Failed output is returned to the agent so it can fix the issue and the
next source edit triggers verification again.

## Project Config

Project-level overrides still live in `.ai-agent/config.toml`.

You can also add:

- `AGENT.MD` for project-specific developer instructions
- `.ai-agent/skills/<skill-name>/SKILL.md` for reusable skills
- `.ai-agent/tools/*.py` for custom tools

## Publish Checklist

1. Bump `version` in `pyproject.toml`.
2. Run tests.
3. Build the wheel and sdist with `uv build --no-sources`.
4. Test the CLI with `uv run lm-program --configure`.
5. Upload to TestPyPI.
6. Verify both `uv run lm-program --configure` and `uv run lm-program` work.
7. Publish to PyPI.

## Publish With uv

Recommended local release flow:

```bash
uv sync --frozen
uv run python -m unittest tests.test_config_loader tests.test_skills
uv build --no-sources
uv run --isolated --no-project --with dist/*.whl tests/smoke_test.py
uv run --isolated --no-project --with dist/*.tar.gz tests/smoke_test.py
```

TestPyPI publish:

```bash
$env:UV_PUBLISH_TOKEN="pypi-***"
uv publish --publish-url https://test.pypi.org/legacy/
```

PyPI publish:

```bash
$env:UV_PUBLISH_TOKEN="pypi-***"
uv publish
```

For the first release, verify the package name on PyPI before publishing. If `lm-program` is already taken, rename `project.name` in `pyproject.toml` before uploading.

## Trusted Publishing

A GitHub Actions release workflow is included at `.github/workflows/publish.yml`.

To use it:

1. Create the project on PyPI.
2. In the PyPI project settings, add a Trusted Publisher for this GitHub repository.
3. In GitHub, create an environment named `pypi`.
4. Push a version tag like `v0.1.0`.

That workflow will:

- sync with `uv`
- run the unit tests
- build the wheel and source distribution
- smoke-test both artifacts
- publish with `uv publish`

## Why `uv` Instead of `pip install -e .`

This repository already carries a `uv.lock`, so `uv sync` is the safer default for development. It avoids polluting a shared Python installation and reduces resolver conflicts with unrelated packages already installed on your machine.

## License

Distributed under the [MIT License](LICENSE).
