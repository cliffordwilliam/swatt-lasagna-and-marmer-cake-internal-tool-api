# Notes

Since this project main entry point is in `/app` directory, the `pyproject.toml` has been updated about that so that `FastAPI` knows about this custom entry point.

Before running this locally, run `uv sync` to update your local `venv` dependencies to match what the `lock` has declared.

For local development work, just run `uv run fastapi dev` to start the server with hotreload. Use `ctrl + c` to stop.

This uses the `psycopg2-binary`/`psycopg2` so do know that each handler is in its own thread, not a coroutine that gets managed by event loop. It is blocking so that is why per handler gets its own dedicated thread. Otherwise if its a coroutine the eventloop hangs and waits for that one coroutine to finish the whole UoW.

## Provision local offline database:
To provision a local offline database, just use Docker, note the `--rm` there is so that upon stopping the container and volume is gone so there is no persistance:
```bash
docker run --rm --name study-db \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=mydb \
  -p 5432:5432 \
  -d postgres:16
```

Do not forget to stop it later:
```bash
docker stop study-db
```

Subsequent runs you can just start it again:
```bash
docker start study-db
```

## List of things to take care of before going away from development:
1. Note that for now this is using this `psycopg2-binary` driver DBAPI for development, this must use `psycopg2` later outside development.
2. Lock is a snapshot of whatever I am using right now but do take note that you want to allow minor/patch, block major!
  This is what I am talking about when it comes to version numbering in the `pyproject.toml` file:
  ```text
  2 . 0 . 50
  ↑   ↑   ↑
  │   │   └── patch — bug fixes only, always safe to grow
  │   └──── minor — new features, backwards compatible, generally safe
  └────── major — breaking changes, never grow this accidentally
  ```
3. `create_engine` is very simple in dev, but later in production, please review and see what other arguments to pass into okay. Same goes with `sessionmaker` too. Both are in `root/app/core/database.py`. Engine right now also tells the database to send logs to stdout so maybe turn that off too in production, its on in development so I can see whats going on in the database.
