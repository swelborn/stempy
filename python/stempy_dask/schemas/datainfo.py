from pathlib import Path

from pydantic import BaseModel


class StempyDataInfo(BaseModel):
    scan_number: int
    location: Path
    name: str
