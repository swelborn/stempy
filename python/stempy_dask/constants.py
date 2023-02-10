from pathlib import Path

from pydantic import BaseModel


class StempyDataInfo(BaseModel):
    scan_number: int
    location: Path


BIG_DATA_BENCHMARK = StempyDataInfo(
    scan_number=26, location=Path("/pscratch/sd/s/swelborn/2022.10.17/")
)

SMALL_DATA_BENCHMARK = StempyDataInfo(
    scan_number=22,
    location=Path("/pscratch/sd/s/swelborn/20230103_testing_stempy_reader/"),
)
