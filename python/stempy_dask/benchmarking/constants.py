from pathlib import Path

from pydantic import BaseModel

DASK_COUNT_JOB_SCRIPT_TEMPLATE = "count_dask.sh.j2"

BENCHMARK_WORKDIR = "/pscratch/sd/s/swelborn/stempy_dask_benchmarks"

DASK_PERLMUTTER_MACHINE_CONSTANTS = {
    "name": "perlmutter",
    "account": "staff",
    "qos": "regular",
    "constraint": "gpu",
    "ntasks": 4,
    "image": "samwelborn/stempy-cuda:latest",
    "workdir": Path(BENCHMARK_WORKDIR),
    "volume": "/global/homes/s/swelborn/stempy_swelborn/:/source/",
}


class StempyDataInfo(BaseModel):
    scan_number: int
    location: Path
    name: str


BIG_DATA_BENCHMARK = StempyDataInfo(
    scan_number=26, location=Path("/pscratch/sd/s/swelborn/2022.10.17/"), name="big"
)

SMALL_DATA_BENCHMARK = StempyDataInfo(
    scan_number=22,
    location=Path("/pscratch/sd/s/swelborn/20230103_testing_stempy_reader/"),
    name="small",
)
