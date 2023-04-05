import itertools
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Tuple, Union

sys.path.append("/source/stempy_swelborn/stempy/python")

import jinja2
import numpy as np
from stempy_dask.benchmarking.constants import (
    BENCHMARK_WORKDIR,
    BIG_DATA_BENCHMARK,
    DASK_COUNT_JOB_SCRIPT_TEMPLATE,
    DASK_PERLMUTTER_MACHINE_CONSTANTS,
    SMALL_DATA_BENCHMARK,
    STEMPY_COUNT_JOB_SCRIPT_TEMPLATE,
    STEMPY_PERLMUTTER_MACHINE_CONSTANTS,
)
from stempy_dask.schemas import (
    BenchmarkMatrix,
    BenchmarkType,
    BenchmarkVariable,
    DaskMachine,
    Job,
    JobType,
    Machine,
    StempyDataInfo,
)


def calculate_time(matrix: BenchmarkMatrix, data: StempyDataInfo):
    # Calculate the appropriate value of time based on data_size
    num_runs = matrix.num_runs
    # Set number of minutes per run
    if matrix.type == "stempy-mpi":
        factor1 = 1
    else:
        factor1 = 3
    if data.name == "small":
        factor2 = 1
    else:
        factor2 = 3
    time_in_seconds = 60 * num_runs * factor1 * factor2  # Maximum time in seconds

    # Convert time to HH:MM:SS format
    hours = int(time_in_seconds // 3600)
    minutes = int((time_in_seconds % 3600) // 60)
    seconds = int(time_in_seconds % 60)
    time_str = "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)
    return time_str


def mock_job(
    machine: DaskMachine,
    matrix: BenchmarkMatrix,
    data: StempyDataInfo,
    id_generator: Iterator[int],
) -> Job:
    id = next(id_generator)
    benchmark_type = matrix.type
    if benchmark_type == BenchmarkType.DASK:
        job_type = JobType.DASK_COUNT
    elif benchmark_type == BenchmarkType.STEMPY_MPI:
        job_type = JobType.COUNT
    else:
        job_type = JobType.COUNT
    scan_id = data.scan_number
    machine_name = machine.name
    params = {"threshold": 4}

    return Job(
        id=id, job_type=job_type, scan_id=scan_id, machine=machine_name, params=params
    )  # type: ignore


# Create benchmark machines
def create_benchmark_machines(
    matrix: BenchmarkMatrix,
) -> List[Union[Machine, DaskMachine]]:
    machines = []
    benchmark_type = matrix.type
    if benchmark_type == BenchmarkType.DASK:
        MachineType = DaskMachine
        consts = DASK_PERLMUTTER_MACHINE_CONSTANTS
    elif benchmark_type == BenchmarkType.STEMPY_MPI:
        MachineType = Machine
        consts = STEMPY_PERLMUTTER_MACHINE_CONSTANTS
    else:
        MachineType = Machine
        consts = STEMPY_PERLMUTTER_MACHINE_CONSTANTS
    for nodes in matrix.nodes:
        for data in matrix.data:
            time = calculate_time(matrix, data)
            parent_workdir = matrix.workdir
            machine = MachineType(
                **consts,
                parent_workdir=parent_workdir,
                workdir=parent_workdir
                / f"{benchmark_type}-{nodes}node-{data.name}data",
                nodes=nodes,
                data=data,
                time=time,
            )
            if not machine.workdir.exists():
                machine.workdir.mkdir()

            machines.append(machine)

    return machines


# Render job script
def render_job_script(
    machine: Union[Machine, DaskMachine],
    matrix: BenchmarkMatrix,
    id_generator: Iterator[int],
) -> Tuple[Job, str]:

    # Check what benchmark type this is
    benchmark_type = matrix.type
    if benchmark_type == BenchmarkType.DASK:
        template_name = DASK_COUNT_JOB_SCRIPT_TEMPLATE
    elif benchmark_type == BenchmarkType.STEMPY_MPI:
        template_name = STEMPY_COUNT_JOB_SCRIPT_TEMPLATE
    else:
        template_name = STEMPY_COUNT_JOB_SCRIPT_TEMPLATE
    data = machine.data

    template_loader = jinja2.FileSystemLoader(
        searchpath=Path(__file__).parent / "templates"
    )
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template(template_name)
    job = mock_job(machine, matrix, data, id_generator)

    output = template.render(
        machine=machine,
        data=data,
        job=job,
        matrix=matrix,
        **job.params,
    )
    return (job, output)


def write_matrix(matrix: BenchmarkMatrix):
    with open(matrix.workdir / (str(matrix.type) + ".json"), "w") as f:
        f.write(matrix.json())


def write_scripts_into_folders(scripts: List[Tuple[DaskMachine, Tuple[Job, str]]]):
    for script in scripts:
        machine = script[0]
        job = script[1][0]
        run_script = script[1][1]
        workdir: Path = machine.workdir
        with open(workdir / "run.sh", "w") as f:
            f.write(run_script)
        with open(workdir / "machine.json", "w") as f:
            f.write(machine.json())
        with open(workdir / "job.json", "w") as f:
            f.write(job.json())


if __name__ == "__main__":

    # Configure benchmark variables
    nodes = [1, 2, 4, 8]
    data = [BIG_DATA_BENCHMARK, SMALL_DATA_BENCHMARK]
    benchmark_variables = [BenchmarkVariable.NODES, BenchmarkVariable.DATA]

    # Create matrix using those variables (for dask counting)
    matrix_dask = BenchmarkMatrix(
        nodes=nodes,
        data=data,
        variables=benchmark_variables,
        workdir=Path(BENCHMARK_WORKDIR),
        type=BenchmarkType.DASK,
        num_runs=3,
    )

    # Create matrix using those variables (for mpi counting)
    matrix_stempy = BenchmarkMatrix(
        nodes=nodes,
        data=data,
        variables=benchmark_variables,
        workdir=Path(BENCHMARK_WORKDIR),
        type=BenchmarkType.STEMPY_MPI,
        num_runs=1,
    )

    # Set up proper working directory
    prefix = matrix_dask.ts.strftime("%Y%m%d_%H%M%S")
    suffix = "-".join(matrix_dask.variables)
    matrix_dask.workdir = matrix_dask.workdir / f"{prefix}-{suffix}"

    # Set stempy working directory as the same one
    matrix_stempy.workdir = matrix_dask.workdir

    if not matrix_dask.workdir.exists():
        matrix_dask.workdir.mkdir()

    id_generator: Iterator[int] = itertools.count()  # for generating mock IDs
    dask_machines = create_benchmark_machines(matrix_dask)
    stempy_machines = create_benchmark_machines(matrix_stempy)

    # Create run scripts
    scripts = []
    for machine in dask_machines:
        scripts.append((machine, render_job_script(machine, matrix_dask, id_generator)))
    for machine in stempy_machines:
        scripts.append(
            (machine, render_job_script(machine, matrix_stempy, id_generator))
        )

    # Write JSONs/run scripts
    write_matrix(matrix_dask)
    write_matrix(matrix_stempy)
    write_scripts_into_folders(scripts)
