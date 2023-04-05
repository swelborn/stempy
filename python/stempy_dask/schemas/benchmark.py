from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, validator
from stempy_dask.schemas.datainfo import StempyDataInfo
from stempy_dask.schemas.job import Job
from stempy_dask.schemas.machine import Machine


class BenchmarkType(str, Enum):
    DASK = "dask"
    STEMPY_MPI = "stempy-mpi"
    STEMPY_SINGLE_NODE = "stempy-single-node"

    def __str__(self) -> str:
        return self.value


class BenchmarkVariable(str, Enum):
    NODES = "nodes"
    DATA = "data"

    def __str__(self) -> str:
        return self.value


class BenchmarkResult(BaseModel):
    type: BenchmarkType
    read_time: str
    write_time: str
    count_time: str
    start_data_size_bytes: int
    end_data_size_bytes: int
    job: Job
    machine: Machine


class BenchmarkMatrix(BaseModel):
    nodes: List[int]
    data: List[StempyDataInfo]
    ts: datetime = None
    variables: List[BenchmarkVariable]
    workdir: Path
    type: BenchmarkType
    num_runs: int

    @validator("ts", pre=True, always=True)
    @classmethod
    def set_ts_now(cls, v):
        return v or datetime.now()
