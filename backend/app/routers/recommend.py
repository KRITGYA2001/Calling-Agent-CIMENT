from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
def status() -> dict[str, str]:
    return {
        "status": "skeleton",
        "note": "Wire this up to ContentRecommender once the problem statement and dataset are known.",
    }
