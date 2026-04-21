# Contributing

Pull requests are welcome. Please:

1. Install dev dependencies: `pip install -e ".[test,dev]"`.
2. Run `ruff check src tests` and `pytest tests/`.
3. Run `mypy src/lrdbench` if you change type-annotated APIs.

Keep changes focused and match existing style in the touched files.
