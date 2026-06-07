"""Worker entry point.

This module creates the FastAPI app instance and register routes.
"""

from fastapi import FastAPI
from .domains.items import item_routers

app = FastAPI()


@app.get("/healthz")
def health_check():
    return {"status": "ok"}


app.include_router(item_routers.router)
