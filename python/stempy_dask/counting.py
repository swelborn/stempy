import time
from collections import namedtuple
from functools import partial
from pathlib import Path
from time import perf_counter

import cupy as cp
import dask.array as da
import distributed
import numpy as np
from distributed import as_completed, wait
from pydantic import BaseModel
from stempy_dask.config import config as cfg
from stempy_dask.utils import log as pretty_logger

import stempy.image as stim
import stempy.io as stio

from .constants import StempyDataInfo
from .dask import DaskClient
from .kernels import kernels

log = pretty_logger.create_logger("counting", cfg.settings)


def create_reader(data_info: StempyDataInfo):
    """
    Function to create the reader on worker. The reader is created by submitting this function
    as an actor. Then, the actor can call the get_block_from_image_number method and load in/scatter
    data onto the workers.

    """

    # Padded data (?) don't know what this is...
    pad = True
    if pad:
        scanName = "data_scan{:010}_*.data".format(data_info.scan_number)
    else:
        scanName = "data_scan{}_*.data".format(data_info.scan_number)

    log.info("Using files in {}".format(data_info.location))
    log.info("scan name = {}".format(scanName))

    # Get file names
    files = data_info.location.glob(scanName)
    iFiles = [str(f) for f in files]
    iFiles = sorted(iFiles)

    # Create reader
    reader = stio.reader(iFiles, stio.FileVersion.VERSION5, backend="multi-pass")
    reader.create_scan_map()
    return reader


def load_stem_image(reader, image_number=0):
    """
    Given a reader, one can load an image number with this function.

    Args
    ----
    reader: stempy.io.SectorThreadedMultiPassReader
        This assumes that the reader has already created a map.
    image_number: int
        The image number to load (from the map).
    with_header: bool
        Return either a stempy._io._block object (with_header=True),
        or a numpy array.
    """
    b = reader.get_block_from_image_number(image_number)

    block = namedtuple("Block", ["header", "data"])
    block._block = b
    block.header = b.header
    block.data = np.array(b, copy=False)

    return block


async def a_load_stem_image_batch(reader, image_numbers=(0, 1)):
    """
    Given a reader, one can load an image number with this function.

    Args
    ----
    reader: stempy.io.SectorThreadedMultiPassReader
        This assumes that the reader has already created a map.
    image_number: int
        The image number to load (from the map).
    with_header: bool
        Return either a stempy._io._block object (with_header=True),
        or a numpy array.
    """
    stack_height = image_numbers[1] - image_numbers[0]
    arr = np.zeros((stack_height, 576, 576))
    for image_number in range(image_numbers[0], image_numbers[1]):
        stack_idx = image_number - image_numbers[0]
        if image_number != 192:
            img = (await reader.get_block_from_image_number(image_number)).data
            try:
                arr[stack_idx] = img
            except ValueError:
                continue
    return arr


class Counter:
    def __init__(
        self,
        client: DaskClient,
        data_info: StempyDataInfo,
    ):
        self.dask_client = client
        self.client = client.client
        self.data_info = data_info

    def calculate_data_info(self):
        pass

    async def create_reader_on_all_workers(self):
        self.readers = {}
        for worker_id in self.dask_client.gpu_workers:
            self.readers[worker_id] = self.client.submit(
                create_reader, self.data_info, actor=True, workers=worker_id
            )
        futures = [self.readers[k] for k in self.readers]
        await self.client.gather(futures)

    async def count(self):
        gpu_workers = self.dask_client.gpu_workers
        total_images = 128 * 128
        bytes_per_pattern = 1024 * 1024
        max_num_bytes = bytes_per_pattern * 100  # totally arbitrary right now
        batch_size = max_num_bytes // (
            bytes_per_pattern
        )  # really just ends up being 1000
        num_batches = total_images // batch_size + 1
        arrays_batch_futures = []
        d_arrays_batch_futures = []
        counted_batch_futures = []
        positions_futures = []
        pools = []
        div = num_batches // len(gpu_workers) + 1

        t0 = time.perf_counter()

        for worker_id, batch_idx in zip(gpu_workers * div, range(num_batches)):
            probes_remaining = total_images - (batch_idx * batch_size)
            this_batch_size = (
                probes_remaining if probes_remaining < batch_size else batch_size
            )
            first_batch_idx = batch_idx * batch_size
            second_batch_idx = this_batch_size + first_batch_idx
            concat_arr = self.client.submit(
                partial(a_load_stem_image_batch, await self.readers[worker_id]),
                (first_batch_idx, second_batch_idx),
                workers=worker_id,
            )
            # arrays_batch_futures.append(concat_arr)

            d_concat_arr = self.client.submit(
                cp.asarray, concat_arr, dtype=cp.uint16, workers=worker_id
            )
            get_maximal_points = kernels["maximal_pts_uint16"]
            positions = self.client.submit(
                get_maxima_2D,
                ar=d_concat_arr,
                get_maximal_points=get_maximal_points,
                workers=worker_id,
            )
            positions_futures.append(positions)

        await wait(positions_futures)
        t1 = time.perf_counter()


def get_maxima_2D(
    ar=None,
    sigma=0,
    edgeBoundary=0,
    minSpacing=60,
    minRelativeIntensity=0.005,
    minAbsoluteIntensity=0.0,
    relativeToPeak=0,
    maxNumPeaks=70,
    subpixel="poly",
    ar_FT=None,
    upsample_factor=16,
    get_maximal_points=None,
    # blocks=None,
    # threads=None,
):
    get_maximal_points = get_maximal_points
    blocks = (ar.shape[1],)
    threads = (ar.shape[2],)
    sizex = ar.shape[1]
    sizey = ar.shape[2]
    N = sizex * sizey
    positions_future = []
    maxima_bool = cp.zeros_like(ar, dtype=bool)
    for i in range(ar.shape[0]):
        # Get maxima
        get_maximal_points(
            blocks,
            threads,
            (ar[i], maxima_bool[i], minAbsoluteIntensity, sizex, sizey, N),
        )
        # Remove edges
        if edgeBoundary > 0:
            maxima_bool[i, :edgeBoundary, :] = False
            maxima_bool[i, -edgeBoundary:, :] = False
            maxima_bool[i, :, :edgeBoundary] = False
            maxima_bool[i, :, -edgeBoundary:] = False
        elif subpixel is True:
            maxima_bool[i, :1, :] = False
            maxima_bool[i, -1:, :] = False
            maxima_bool[i, :, :1] = False
            maxima_bool[i, :, -1:] = False

        # Get indices, sorted by intensity
        maxima_x, maxima_y = cp.nonzero(maxima_bool[i])
        positions_future.append((maxima_x, maxima_y))
    #         dtype = cp.dtype([("x", cp.uint16), ("y", cp.uint16), ("intensity", cp.uint16)])
    #         maxima = cp.zeros(len(maxima_x), dtype=dtype)
    #         maxima["x"] = maxima_x
    #         maxima["y"] = maxima_y
    #         maxima["intensity"] = ar[i, maxima_x, maxima_y]
    #         maxima = cp.sort(maxima, order="intensity")[::-1]

    #         positions_future.append((maxima["x"], maxima["y"], maxima["intensity"]))

    return positions_future
