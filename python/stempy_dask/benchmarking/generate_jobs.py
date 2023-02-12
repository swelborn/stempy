import itertools
import time
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Tuple

import jinja2
import numpy as np

from .constants import (
    BENCHMARK_WORKDIR,
    BIG_DATA_BENCHMARK,
    DASK_COUNT_JOB_SCRIPT_TEMPLATE,
    DASK_PERLMUTTER_MACHINE_CONSTANTS,
    SMALL_DATA_BENCHMARK,
    StempyDataInfo,
)
from .schemas import BenchmarkMatrix, BenchmarkVariable, DaskMachine, Job, JobType


def mock_job(
    machine: DaskMachine, data: StempyDataInfo, id_generator: Iterator[int]
) -> Job:
    id = next(id_generator)
    job_type = JobType.DASK
    scan_id = data.scan_number
    machine_name = machine.name
    params = {"hello": 123}

    return Job(
        id=id, job_type=job_type, scan_id=scan_id, machine=machine_name, params=params
    )  # type: ignore


# Create benchmark machines
def create_benchmark_dask_machines(
    matrix: BenchmarkMatrix,
) -> List[DaskMachine]:
    machines = []
    prefix = matrix.ts.strftime("%Y%m%d_%H%M%S")
    suffix = "-".join(matrix.variables)
    for nodes in matrix.nodes:
        machine = DaskMachine(nodes=nodes, **DASK_PERLMUTTER_MACHINE_CONSTANTS)
        machine.workdir = machine.workdir / f"{prefix}-{suffix}"
        machines.append(machine)

    return machines


# Render job script
def render_dask_job_script(
    machine: DaskMachine, data: StempyDataInfo, id_generator: Iterator[int]
) -> Tuple[Job, str]:

    template_name = DASK_COUNT_JOB_SCRIPT_TEMPLATE
    template_loader = jinja2.FileSystemLoader(
        searchpath=Path(__file__).parent / "templates"
    )
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template(template_name)
    job = mock_job(machine, data, id_generator)
    if not machine.workdir.exists():
        machine.workdir.mkdir()
    machine.workdir = machine.workdir / f"{machine.nodes}node-{data.name}data"
    if not machine.workdir.exists():
        machine.workdir.mkdir()
    output = template.render(
        machine=machine,
        data=data,
        job=job,
    )
    return (job, output)


def write_scripts_into_folders(
    scripts: List[Tuple[DaskMachine, StempyDataInfo, Tuple[Job, str]]]
):
    for script in scripts:
        machine = script[0]
        data = script[1]
        job = script[2][0]
        run_script = script[2][1]
        workdir: Path = machine.workdir
        with open(workdir / "run.sh", "w") as f:
            f.write(run_script)
        with open(workdir / "machine.json", "w") as f:
            f.write(machine.json())
        with open(workdir / "data.json", "w") as f:
            f.write(data.json())
        with open(workdir / "job.json", "w") as f:
            f.write(job.json())


if __name__ == "__main__":
    # Configure benchmark variables
    nodes = [1, 2, 4, 8]
    data = [BIG_DATA_BENCHMARK, SMALL_DATA_BENCHMARK]
    benchmark_variables = [BenchmarkVariable.NODES, BenchmarkVariable.DATA]

    # Create matrix using those variables
    matrix = BenchmarkMatrix(
        nodes=nodes,
        data=data,
        variables=benchmark_variables,
    )
    id_generator: Iterator[int] = itertools.count()  # for generating mock IDs
    machines = create_benchmark_dask_machines(matrix)
    scripts = []

    for machine in machines:
        for d in data:
            scripts.append(
                (machine, d, render_dask_job_script(machine, d, id_generator))
            )

    write_scripts_into_folders(scripts)
