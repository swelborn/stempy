from pathlib import Path

from pydantic import BaseModel
from stempy_dask.schemas.datainfo import StempyDataInfo

DASK_COUNT_JOB_SCRIPT_TEMPLATE = "count_dask.sh.j2"
STEMPY_COUNT_JOB_SCRIPT_TEMPLATE = "count_stempy.sh.j2"

BENCHMARK_WORKDIR = "/pscratch/sd/s/swelborn/stempy_benchmarks"

PRELOAD_FILEPATH = "/source/stempy/python/stempy_dask/preload_serializers.py"

COUNT_FILEPATH_DASK = (
    "/source/stempy/python/stempy_dask/benchmarking/scripts/count_dask.py"
)

COUNT_FILEPATH_STEMPY = (
    "/source/stempy/python/stempy_dask/benchmarking/scripts/count_stempy.py"
)

DASK_PERLMUTTER_MACHINE_CONSTANTS = {
    "name": "perlmutter",
    "account": "nstaff",
    "qos": "debug",
    "constraint": "gpu",
    "ntasks": 4,
    "image": "samwelborn/stempy-cuda:latest",
    "volume": "/global/homes/s/swelborn/stempy_swelborn/:/source/",
    "cpus_per_task": 128,
    "gpus_per_task": 1,
    "preload_path": Path(PRELOAD_FILEPATH),
    "count_path": Path(COUNT_FILEPATH_DASK),
}

STEMPY_PERLMUTTER_MACHINE_CONSTANTS = {
    "name": "perlmutter",
    "account": "nstaff",
    "qos": "debug",
    "constraint": "cpu",
    "ntasks": 4,
    "ntasks_per_node": 1,
    "image": "samwelborn/stempy-mpi:latest",
    "volume": "/global/homes/s/swelborn/stempy_swelborn/:/source/",
    "cpus_per_task": 128,
    "gpus_per_task": 1,
    "count_path": Path(COUNT_FILEPATH_STEMPY),
    "bbcp_dest_dir": " ",
}


BIG_DATA_BENCHMARK = StempyDataInfo(
    scan_number=26, location=Path("/pscratch/sd/s/swelborn/2022.10.17/"), name="big"
)

SMALL_DATA_BENCHMARK = StempyDataInfo(
    scan_number=22,
    location=Path("/pscratch/sd/s/swelborn/20230103_testing_stempy_reader/"),
    name="small",
)

# https://docs.nersc.gov/jobs/#commonly-used-options
SLURM_COMMON_OPTIONS_MAP = {
    "--cpus-per-task": "-c",
    "--ntasks": "-n",
    "--nodes": "-N",
    "--qos": "-q",
    "--constraint": "-C",
    "--account": "-A",
    "--job-name": "-J",
    "--time": "-t",
    "--gpus-per-node": None,
    "--gpus-per-task": None,
}
