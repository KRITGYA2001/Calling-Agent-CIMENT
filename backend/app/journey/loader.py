import json
from functools import lru_cache
from pathlib import Path

from app.journey.schema import JourneyDefinition

_DEFAULT_PATH = Path(__file__).parent / "energy_journey.json"


@lru_cache
def get_journey(path: str | None = None) -> JourneyDefinition:
    file_path = Path(path) if path else _DEFAULT_PATH
    data = json.loads(file_path.read_text(encoding="utf-8"))
    return JourneyDefinition.model_validate(data)
