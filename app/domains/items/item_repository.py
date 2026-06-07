"""Item repository layer.

This module directly uses this UoW Session state for database operations.
"""

from sqlalchemy.orm import Session
from app.domains.items.item_model import Item


class ItemRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, item_id: int) -> Item | None:
        return self.db.get(Item, item_id)

    def get_all(self) -> list[Item]:
        return self.db.query(Item).all()

    def create(self, name: str, amount: int) -> Item:
        item = Item(name=name, amount=amount)
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item
