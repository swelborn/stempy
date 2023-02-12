import asyncio
import contextlib
import time
from argparse import Namespace
from datetime import datetime
from functools import partial
from pathlib import Path
from time import perf_counter
from typing import Mapping, Tuple

import distributed
import numpy as np
import orjson
from dask_cuda.benchmarks.utils import (
    address_to_index,
    aggregate_transfer_log_data,
    bandwidth_statistics,
    format_bytes,
    parse_benchmark_args,
    peer_to_peer_bandwidths,
    print_key_value,
    print_separator,
    print_throughput_bandwidth,
    setup_memory_pools,
    wait_for_cluster,
)
from pydantic import BaseModel, validator

import dask
from dask.distributed import performance_report

# Get local settings (inside slurm job)

# Setup output folders
# Needs to be done from externel command

# Setup scheduler address
# Needs to be done from external command


async def count(args):
    time.sleep(5)
    counted = 5
    return counted


# Start asynchronous client
async def connect_to_existing_client(args: Namespace) -> distributed.Client:
    client = distributed.Client(args.scheduler_address)
    return client


async def bench_once(client: distributed.Client, args: Namespace, write_profile=None):

    # Get contexts to use (defaults to null contexts that doesn't do anything)
    ctx1 = contextlib.nullcontext()
    if write_profile is not None:
        ctx1 = performance_report(filename=args.profile)
    with ctx1:
        t1 = perf_counter()
        data = await client.submit(count, args)
        duration = perf_counter() - t1
    return data, duration


async def run_benchmark(client: distributed.Client, args: Namespace):
    """Run a benchmark a specified number of times
    If ``args.profile`` is set, the final run is profiled.
    """
    results = []
    for run_number in range(max(1, args.runs) - 1):
        data, duration = await bench_once(client, args, write_profile=None)
        results.append((run_number, None, duration))

    # Only store data and write profile on the last one
    data, duration = await bench_once(client, args, write_profile=args.profile)
    results.append((results[-1][0], data, duration))

    return results


async def gather_bench_results(client: distributed.Client, args: Namespace):
    """Collect benchmark results from the workers"""
    address2index = address_to_index(client)
    results = await run_benchmark(client, args)
    # Collect aggregated peer-to-peer bandwidth
    message_data = client.run(
        partial(aggregate_transfer_log_data, bandwidth_statistics, args.ignore_size)
    )
    return address2index, results, message_data


def orjson_dumps(v, *, default):
    # orjson.dumps returns bytes, to match standard json.dumps we need to decode
    return orjson.dumps(v, default=default).decode()


class BenchmarkResults(BaseModel):
    p2p_bw: np.ndarray
    address_map: Mapping[str, int]
    results: list[Tuple[int, np.ndarray | None, float]]
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
    ]

    return parse_benchmark_args(
        description="Electron counting benchmarking", args_list=special_args
    )


def pretty_print_results(args, address_to_index, p2p_bw, results):

    if args.markdown:
        print("```")
    print("Merge benchmark")
    print_separator(separator="-")
    print_key_value(key="Protocol", value=f"{args.protocol}")
    print_key_value(key="Device(s)", value=f"{args.devs}")
    if args.device_memory_limit:
        print_key_value(
            key="Device memory limit", value=f"{format_bytes(args.device_memory_limit)}"
        )
    print_key_value(key="RMM Pool", value=f"{not args.disable_rmm_pool}")
    print_key_value(key="Frac-match", value=f"{args.frac_match}")
    if args.protocol == "ucx":
        print_key_value(key="TCP", value=f"{args.enable_tcp_over_ucx}")
        print_key_value(key="InfiniBand", value=f"{args.enable_infiniband}")
        print_key_value(key="NVLink", value=f"{args.enable_nvlink}")
    print_key_value(key="Worker thread(s)", value=f"{args.threads_per_worker}")
    print_key_value(key="Data processed", value=f"{format_bytes(results[-1][1])}")
    if args.markdown:
        print("\n```")

    data_processed, durations = zip(*results)
    print_throughput_bandwidth(
        args, durations, data_processed, p2p_bw, address_to_index
    )


async def run(client: distributed.Client, args: Namespace):
    """Run the full benchmark on the cluster
    Waits for the cluster, sets up memory pools, prints and saves results
    """

    wait_for_cluster(client, shutdown_on_failure=True)
    setup_memory_pools(
        client,
        args.type == "gpu",
        args.rmm_pool_size,
        args.disable_rmm_pool,
        args.rmm_log_directory,
        args.enable_rmm_statistics,
    )
    address_to_index, results, message_data = await gather_bench_results(client, args)
    results = await results
    p2p_bw: np.ndarray = peer_to_peer_bandwidths(message_data, address_to_index)
    results_model = BenchmarkResults(
        p2p_bw=p2p_bw,
        address_map=address_to_index,
        results=results,
        base_name="benchmark_results",
        save_dir=args.workdir,
    )
    save_benchmark_data(results_model)
    pretty_print_results(args, address_to_index, p2p_bw, results)


async def main():
    args = parse_args()
    client = connect_to_existing_client(args)
    asyncio.run(run(client, args))


if __name__ == "__main__":
    asyncio.run(main())
