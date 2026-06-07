"""Worker entry point.

This module creates the FastAPI app instance and register routes.
"""

from fastapi import FastAPI
from .domains.items import item_routers
from .core.database import Base
from .core.database import engine

app = FastAPI()


@app.get("/healthz")
def health_check():
    return {"status": "ok"}


app.include_router(item_routers.router)

# For development only, here we hydrate the PostgreSQL cluster to be the same with the mapped classes here
Base.metadata.create_all(engine)
