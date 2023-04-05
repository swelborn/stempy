from pathlib import Path
from typing import Optional

from pydantic import BaseModel, validator
from stempy_dask.schemas.datainfo import StempyDataInfo


class Machine(BaseModel):
    name: str
    account: str
    qos: str
    qos_filter: Optional[str]
    nodes: int
    constraint: str
    ntasks: int
    ntasks_per_node: Optional[int]
    cpus_per_task: int
    bbcp_dest_dir: str
    reservation: Optional[str]
    volume: Optional[Path]
    image: str
    parent_workdir: Path
    workdir: Path
    data: StempyDataInfo
    count_path: Path
    time: str

    # https://docs.nersc.gov/systems/perlmutter/running-jobs/
    @validator("ntasks")
    @classmethod
    def validate_ntasks(cls, v, values):
        if values["name"] == "perlmutter" and values["constraint"] == "cpu":
            good_value = values["nodes"]
            try:
                assert v == good_value
            except:
                return good_value
        return v

    @validator("cpus_per_task")
    @classmethod
    def validate_cpus_per_task_cpu(cls, v, values):
        if values["name"] == "perlmutter" and values["constraint"] == "cpu":
            good_value = int(2 * 128 / (values["ntasks"] / values["nodes"]))
            try:
                assert v == good_value
            except AssertionError:
                return good_value
        return v


class DaskMachine(BaseModel):
    name: str
    account: str
    qos: str
    qos_filter: Optional[str]
    nodes: int
    constraint: str
    ntasks: int
    ntasks_per_node: Optional[int]
    cpus_per_task: int
    gpus_per_task: int
    image: str
    volume: str
    parent_workdir: Path
    workdir: Path
    preload_path: Path
    ucx: bool = False
    data: StempyDataInfo
    count_path: Path
    time: str

    @validator("ntasks")
    @classmethod
    def validate_ntasks(cls, v, values):
        if values["name"] == "perlmutter" and values["constraint"] == "gpu":
            good_value = 4 * values["nodes"]
            try:
                assert v == good_value
            except:
                return good_value
        return v

    @validator("cpus_per_task")
    @classmethod
    def validate_cpus_per_task_gpu(cls, v, values):
        if values["name"] == "perlmutter" and values["constraint"] == "gpu":
            good_value = int(2 * 64 / (values["ntasks"] / values["nodes"]))
            try:
                assert v == good_value
            except AssertionError:
                return good_value
        return v

    @validator("cpus_per_task")
    @classmethod
    def validate_cpus_per_task_cpu(cls, v, values):
        if values["name"] == "perlmutter" and values["constraint"] == "cpu":
            good_value = int(2 * 128 / (values["ntasks"] / values["nodes"]))
            try:
                assert v == good_value
            except AssertionError:
                return good_value
        return v
