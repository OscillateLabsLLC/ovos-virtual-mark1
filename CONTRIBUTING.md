# Contributing to ovos-virtual-mark1

Contributions are welcome: bug fixes, fidelity improvements against the real Mark 1
firmware, GUI work, and tests.

## Development Setup

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv)
- [just](https://github.com/casey/just) (optional; every recipe has a `uv` equivalent below)

### Getting Started

```bash
git clone https://github.com/OscillateLabsLLC/ovos-virtual-mark1
cd ovos-virtual-mark1
just sync          # uv sync --extra test
```

## Common Commands

```bash
just test          # uv run pytest
just lint          # uv run ruff check . && uv run ruff format --check .
just fmt           # uv run ruff format .
just run -v        # uv run ovos-virtual-mark1 -v
```

## Fidelity rule

Behaviour that differs from the Arduino firmware is a bug unless the README lists it as
intentionally not emulated. When you change mouth or eye behaviour, cite the firmware
function you are matching in the PR description. The fonts and bitmaps are generated;
edit `scripts/port_firmware_tables.py`, never the generated files.

## Pull Requests

1. Create a branch: `git checkout -b feat/my-change` or `fix/my-change`
2. Add tests for the change
3. Run `just lint` and `just test`
4. Commit using [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `chore:`, `docs:`)
5. Open a pull request against `main`

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
