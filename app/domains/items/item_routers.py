from fastapi import APIRouter
from .item_schema import Item

router = APIRouter(prefix="/items")

@router.post("/")
async def create_item(item: Item):
    return item

