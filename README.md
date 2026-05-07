This project has atac json save file in /atac, you can use atac to load and work on it. Atac likes to dump its logs in there too so I have gitignores it

This project main entry point is in the /app dir. So the toml has been updated to point over there which means fastapi is aware of where the entry point is

You can just run uv run fastapi dev to start the server with hotreload

If you are editing in nvim like me, its best to start the venv first so your lsp is aware on where the python venv is that you are using, so it knows where its deps are too
Do not forget to turn it off when you are done

turn on
source .venv/bin/activate

turn off
deactivate
