from fastapi import APIRouter

from storage import _retrieve_all_objects

router = APIRouter()

@router.get("/debug/retrieve_all/{index}")
async def retrieve_all(index: str):
    return _retrieve_all_objects(index)

# stats!!