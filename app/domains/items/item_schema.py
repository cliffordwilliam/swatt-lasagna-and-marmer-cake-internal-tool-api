"""Item schema layer.

This module holds item DTOs.
"""

from pydantic import BaseModel


class Item(BaseModel):
    name: str
    amount: int
