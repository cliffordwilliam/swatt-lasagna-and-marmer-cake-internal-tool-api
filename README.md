Since this project main entry point is in `/app` directory, the `pyproject.toml` has been updated about that so that `FastAPI` knows about this custom entry point.

Before running this locally, run `uv sync` to update your local `venv` dependencies to match what the `lock` has declared.

For local development work, just run `uv run fastapi dev` to start the server with hotreload. Use `ctrl + c` to stop.
