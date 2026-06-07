"""Item router layer.

This module holds item routes.
"""

from fastapi import APIRouter
from fastapi import Depends
from .item_schema import Item
from .item_repository import ItemRepository
from sqlalchemy.orm import Session
from app.core.deps import get_db

router = APIRouter(prefix="/items")


@router.post("")
def create_item(item: Item, db: Session = Depends(get_db)):
    return ItemRepository(db).create(name=item.name, amount=item.amount)


@router.get("")
def list_items(db: Session = Depends(get_db)):
    return ItemRepository(db).get_all()
