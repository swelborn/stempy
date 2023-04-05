from __future__ import annotations

import asyncio
import contextlib
import itertools
import os
import sys
import time
from argparse import Namespace
from collections import namedtuple
from datetime import datetime
from functools import partial
from pathlib import Path
from time import perf_counter
from typing import Mapping, Tuple, Union

sys.path.append("/source/stempy/python")

import distributed
import numpy.typing as npt
import orjson
from dask.distributed import performance_report
from dask_cuda.benchmarks.utils import (
    address_to_index,
    aggregate_transfer_log_data,
    bandwidth_statistics,
    format_bytes,
    get_worker_device,
    parse_benchmark_args,
    peer_to_peer_bandwidths,
    print_key_value,
    print_separator,
    print_throughput_bandwidth,
    setup_memory_pool,
)
from distributed.comm.addressing import get_address_host
from pydantic import BaseModel, validator
from stempy_dask import preload_serializers
from stempy_dask.benchmarking.constants import StempyDataInfo
from stempy_dask.config import config as cfg
from stempy_dask.config.config import Settings
from stempy_dask.counting import Counter, DaskClient
from stempy_dask.schemas.job import Job
from stempy_dask.schemas.machine import DaskMachine
from stempy_dask.utils import log as pretty_logger

import stempy.io as stio

log = pretty_logger.create_logger("dask-benchmark", cfg.settings)


async def address_to_index(client: distributed.Client) -> Mapping[str, int]:
    """Produce a mapping from worker addresses to unique indices

    Parameters
    ----------
    client: Client
        distributed client

    Returns
    -------
    Mapping from worker addresses to int, with workers on the same
    host numbered contiguously, and sorted by device index on each host.
    """
    # Group workers by hostname and then device index
    addresses = await client.run(get_worker_device)
    return dict(
        zip(
            sorted(addresses, key=lambda k: (get_address_host(k), addresses[k])),
            itertools.count(),
        )
    )


# Start asynchronous client
async def connect_to_existing_client(args: Namespace) -> distributed.Client:
    client = await distributed.Client(
        scheduler_file=args.scheduler_file, asynchronous=True
    )
    return client


async def bench_once(
    counter: Counter,
    args: Namespace,
    write_profile=None,
):

    # Get contexts to use (defaults to null contexts that doesn't do anything)
    ctx1 = contextlib.nullcontext()
    if write_profile is not None:
        ctx1 = performance_report(filename=(Path(args.workdir) / "report.html"))
        async with ctx1:
            t1 = perf_counter()
            await counter.create_reader_on_all_workers()
            data = await counter.count()
            duration = perf_counter() - t1
    else:
        with ctx1:
            t1 = perf_counter()
            await counter.create_reader_on_all_workers()
            data = await counter.count()
            duration = perf_counter() - t1
    return data, duration


def set_env():
    sys.path.append("/source/stempy/python")
    return sys.path


async def setup_memory_pools(client, is_gpu, pool_size, disable_pool, log_directory):
    if not is_gpu:
        return
    await client.run(
        setup_memory_pool,
        pool_size=pool_size,
        disable_pool=disable_pool,
        log_directory=log_directory,
    )
    await client.run(set_env)
    await client.run_on_scheduler(set_env)

    # Create an RMM pool on the scheduler due to occasional deserialization
    # of CUDA objects. May cause issues with InfiniBand otherwise.
    await client.run_on_scheduler(
        setup_memory_pool,
        pool_size=1e9,
        disable_pool=disable_pool,
        log_directory=log_directory,
    )


async def run_benchmark(
    dask_client: DaskClient, address2index: Mapping[str, int], args: Namespace
):
    """Run a benchmark a specified number of times
    If ``args.profile`` is set, the final run is profiled.
    """
    results = []
    counter = Counter(dask_client, dask_client.machine.data)
    for run_number in range(max(1, args.runs) - 1):
        data, duration = await bench_once(counter, args, write_profile=None)
        results.append((run_number, 1, duration))

    # Only store data and write profile on the last one
    data, duration = await bench_once(counter, args, write_profile=True)
    results.append((results[-1][0], 1, duration))

    return results


async def gather_bench_results(dask_client: DaskClient, args: Namespace):
    """Collect benchmark results from the workers"""
    address2index = await address_to_index(dask_client.client)
    results = await run_benchmark(dask_client, address2index, args)
    # Collect aggregated peer-to-peer bandwidth
    message_data = await dask_client.client.run(
        partial(aggregate_transfer_log_data, bandwidth_statistics)
    )
    return address2index, results, message_data


def orjson_dumps(v, *, default):
    # orjson.dumps returns bytes, to match standard json.dumps we need to decode
    return orjson.dumps(v, default=default, option=orjson.OPT_SERIALIZE_NUMPY).decode()


class BenchmarkResults(BaseModel):
    p2p_bw: npt.NDArray
    address_map: Mapping[str, int]
    results: list[Tuple[int, Union[npt.NDArray, int, None], float]]
    ts: datetime = None
    base_name: str
    save_dir: Path

    @validator("ts", pre=True, always=True)
    @classmethod
    def set_ts_now(cls, v):
        return v or datetime.now()

    class Config:
        json_loads = orjson.loads
        json_dumps = orjson_dumps
        arbitrary_types_allowed = True


def save_benchmark_data(benchmark: BenchmarkResults):
    """Save benchmark data to files"""
    ts: str = benchmark.ts.strftime("%Y%m%d_%H%M%S")
    benchmark_json = benchmark.json()
    with open(f"{benchmark.save_dir / (benchmark.base_name + ts)}.json", "w") as f:
        f.write(benchmark_json)


# Write benchmark statistics in output folder


def parse_args():
    special_args = [
        {
            "name": [
                "-t",
                "--type",
            ],
            "choices": ["cpu", "gpu"],
            "default": "gpu",
            "type": str,
            "help": "Count with CPU or GPU",
        },
        {
            "name": [
                "-c",
                "--chunk-size",
            ],
            "default": 1_000_000,
            "metavar": "n",
            "type": int,
            "help": "Chunk size (default 1_000_000)",
        },
        {
            "name": "--runs",
            "default": 3,
            "type": int,
            "help": "Number of runs",
        },
        {
            "name": "--workdir",
            "type": str,
            "help": "Working directory",
        },
    ]

    return parse_benchmark_args(
        description="Electron counting benchmarking", args_list=special_args
    )


def pretty_print_results(args, address_to_index, p2p_bw, results):

    if args.markdown:
        print("```")
    print("Count benchmark")
    print_separator(separator="-")
    print_key_value(key="Protocol", value=f"{args.protocol}")
    print_key_value(key="Device(s)", value=f"{args.devs}")
    if args.device_memory_limit:
        print_key_value(
            key="Device memory limit", value=f"{format_bytes(args.device_memory_limit)}"
        )
    print_key_value(key="RMM Pool", value=f"{not args.disable_rmm_pool}")
    if args.protocol == "ucx":
        print_key_value(key="TCP", value=f"{args.enable_tcp_over_ucx}")
        print_key_value(key="InfiniBand", value=f"{args.enable_infiniband}")
        print_key_value(key="NVLink", value=f"{args.enable_nvlink}")
    print_key_value(key="Data processed", value=f"{format_bytes(results[-1][1])}")
    if args.markdown:
        print("\n```")

    _, data_processed, durations = zip(*results)
    print_throughput_bandwidth(
        args, durations, data_processed, p2p_bw, address_to_index
    )


async def run(dask_client: DaskClient, args: Namespace):
    """Run the full benchmark on the cluster
    Waits for the cluster, sets up memory pools, prints and saves results
    """

    await setup_memory_pools(
        dask_client.client,
        args.type == "gpu",
        args.rmm_pool_size,
        args.disable_rmm_pool,
        args.rmm_log_directory,
    )
    address_to_index, results, message_data = await gather_bench_results(
        dask_client, args
    )
    p2p_bw: npt.NDArray = peer_to_peer_bandwidths(message_data, address_to_index)
    results_model = BenchmarkResults(
        p2p_bw=p2p_bw,
        address_map=address_to_index,
        results=results,
        base_name="benchmark_results",
        save_dir=args.workdir,
    )
    save_benchmark_data(results_model)
    pretty_print_results(args, address_to_index, p2p_bw, results)


def load_models(args: Namespace):
    workdir = Path(args.workdir)
    machine = DaskMachine.parse_file(workdir / "machine.json")
    job = Job.parse_file(workdir / "job.json")
    return machine, job


async def main():
    args = parse_args()
    machine, _ = load_models(args)
    dask_client = DaskClient(machine, cfg.settings)
    await dask_client.connect()
    await run(dask_client, args)


if __name__ == "__main__":
    asyncio.run(main())
