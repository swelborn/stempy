from pathlib import Path
from typing import Optional

from pydantic import BaseModel, validator


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
    image: str
    volume: str
    workdir: Path
    ucx: bool = False

    @validator("ntasks")
    @classmethod
    def validate_ntasks(cls, v, values):
        if values["name"] == "perlmutter" and values["constraint"] == "gpu":
            good_value = 4 * values["nodes"]
            try:
                assert v == good_value
            except AssertionError:
                return good_value

    @validator("cpus_per_task")
    @classmethod
    def validate_cpus_per_task_gpu(cls, v, values):
        if values["name"] == "perlmutter" and values["constraint"] == "gpu":
            good_value = 2 * 64 / (values["nodes"] * values["ntasks"])
            try:
                assert v == good_value
            except AssertionError:
                return good_value

    @validator("cpus_per_task")
    @classmethod
    def validate_cpus_per_task_cpu(cls, v, values):
        if values["name"] == "perlmutter" and values["constraint"] == "cpu":
            good_value = 2 * 128 / (values["nodes"] * values["ntasks"])
            try:
                assert v == good_value
            except AssertionError:
                return good_value
