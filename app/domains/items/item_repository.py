"""Item repository layer.

This module directly uses this UoW Session state for database operations.
"""

from sqlalchemy.orm import Session
from app.domains.items.item_model import Item
from sqlalchemy import select
from typing import Sequence


class ItemRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, item_id: int) -> Item | None:
        return self.db.get(Item, item_id)

    def get_all(self) -> Sequence[Item]:
        return self.db.execute(select(Item)).scalars().all()

    def create(self, name: str, amount: int) -> Item:
        item = Item(name=name, amount=amount)
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item
