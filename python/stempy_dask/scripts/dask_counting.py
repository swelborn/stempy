import os
import sys
import time
from functools import partial
from pathlib import Path
from time import perf_counter

import dask.array as da
import numpy as np

import stempy.image as stim
import stempy.io as stio

"""
Contains a bunch of development code that should eventually be turned into the real thing. 

Organization from jupyter NB.

"""

# Taken from /global/homes/s/swelborn/stempy-dask/testing_stempy_cupy_dask_new.ipynb
# --------------------------------------------------------------------
# Synchronous counting stuff
# --------------------------------------------------------------------


def create_reader_on_worker():
    """
    Function to create the reader on worker. The reader is created by submitting this function
    as an actor. Then, the actor can call the get_block_from_image_number method and load in/scatter
    data onto the workers.

    """

    # Empty gain
    gain0 = None

    # Setup file name and path
    scanNum = 22
    if on_pm and large_data:
        drive = Path("/pscratch/sd/s/swelborn/2022.10.17/")  # image 192 is messed up
        scanNum = 26
    elif on_pm and not large_data:
        drive = Path("/pscratch/sd/s/swelborn/20230103_testing_stempy_reader/")
        scanNum = 22
    elif on_cori_gpu:
        drive = Path("/global/cscratch1/sd/swelborn/2022.03.08/")
        scanNum = 22
    else:
        drive = Path("2022.03.08/")
        scanNum = 22

    # Padded data (?) don't know what this is...
    pad = True
    if pad:
        scanName = "data_scan{:010}_*.data".format(scanNum)
    else:
        scanName = "data_scan{}_*.data".format(scanNum)

    print("Using files in {}".format(drive))
    print("scan name = {}".format(scanName))

    # Get file names
    files = drive.glob(scanName)
    iFiles = [str(f) for f in files]
    iFiles = sorted(iFiles)

    # Create reader
    reader = stio.reader(iFiles, stio.FileVersion.VERSION5, backend="multi-pass")
    reader.create_scan_map()
    return reader


def load_stem_image(reader, image_number=0, with_header=False):
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

    block = reader.get_block_from_image_number(image_number).result()

    # Depending on whether we want stempy._io._block object, or
    # np.array object
    if with_header:
        return block
    else:
        return np.array(block, copy=False)


def doubleRoll_dask(image, vec):
    """
    doubleRoll (from ncempy) converted to handle dask arrays.
    """
    return np.roll(np.roll(image, vec[0], axis=0), vec[1], axis=1)


def peakFind2D_dask(image_arr, threshold=0.01):
    """
    peakFind2D (from ncempy) converted to handle dask arrays.

    Args
    ----
    image_arr: dask.array
        Has dimensions (x, frame_dimensions[0], frame_dimensions[1])
        where x is the number of images on this particular scan
        position.

    Returns
    -------
    positions: tuple(x_pos: da.array, y_pos: da.array)
        Peak positions returned as a tuple of x and y positions.
    """
    if (threshold < 0) or (threshold >= 1):
        print("Error: Threshold must be 0 <= threshold < 1")
        return 0
    image = image_arr[0]
    # Could generate the set of coordinates using
    # list(set(permutations((0,1,1,-1,-1),2)))
    pLarge = (
        (image > doubleRoll_dask(image, [-1, -1]))
        & (image > doubleRoll_dask(image, [0, -1]))
        & (image > doubleRoll_dask(image, [1, -1]))
        & (image > doubleRoll_dask(image, [-1, 0]))
        & (image > doubleRoll_dask(image, [1, 0]))
        & (image > doubleRoll_dask(image, [-1, 1]))
        & (image > doubleRoll_dask(image, [0, 1]))
        & (image > doubleRoll_dask(image, [1, 1]))
        & (image > threshold * np.max(image))
    )

    positions = np.nonzero(pLarge * image)
    return positions


""" 
Run script from above functions
"""
# Create a reader actor and scatter it across workers:
reader = client.submit(create_reader_on_worker, actor=True).result()
client.scatter([reader])

# Get some metadata from one of the blocks:
scan_dimensions = (128, 128)  # Set manually (for now)
total_images = 10000

# Script to perform lazy operations on everything:
imread = dask.delayed(load_stem_image, pure=True)
lazy_images = [
    imread(reader, image_number=i, with_header=True) for i in range(total_images)
]
sample = lazy_images[0].compute()
frame_dimensions = (sample.data.shape[1], sample.data.shape[2])

arrays = [
    da.from_delayed(
        lazy_image.data,  # Construct a small Dask array
        dtype=sample.data.dtype,  # for every lazy value
        shape=sample.data.shape,
    )
    for lazy_image in lazy_images
]
print(f"Lazily loaded {len(arrays)} stem images.")

# Persists the arrays in worker memory for fast access
arrays = [array.persist() for array in arrays]
print("Persisted the arrays on the workers.")
# Submits the futures
futures = client.map(peakFind2D_dask, arrays)
print("Submitted the counting algorithm to the cluster.")

# --------------------------------------------------------------------


# --------------------------------------------------------------------
# Asynchronous counting
# --------------------------------------------------------------------

# First attempt:


async def a_load_stem_image(reader, image_number=0):
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

    block = reader.get_block_from_image_number(image_number)

    # Depending on whether we want stempy._io._block object, or
    # np.array object
    return block


def doubleRoll(image, vec):
    """
    doubleRoll (from ncempy) converted to handle dask arrays.
    """
    return cp.roll(cp.roll(image, vec[0], axis=0), vec[1], axis=1)


async def a_peakFind2D(image_arr, threshold=0.01):
    """
    peakFind2D (from ncempy) converted to handle dask arrays.

    Args
    ----
    image_arr: dask.array
        Has dimensions (x, frame_dimensions[0], frame_dimensions[1])
        where x is the number of images on this particular scan
        position.

    Returns
    -------
    positions: tuple(x_pos: da.array, y_pos: da.array)
        Peak positions returned as a tuple of x and y positions.
    """
    if (threshold < 0) or (threshold >= 1):
        print("Error: Threshold must be 0 <= threshold < 1")
        return 0
    image_arr = await image_arr
    image = image_arr.data[0]
    image = cp.asarray(image)
    pLarge = (
        (image > doubleRoll(image, [-1, -1]))
        & (image > doubleRoll(image, [0, -1]))
        & (image > doubleRoll(image, [1, -1]))
        & (image > doubleRoll(image, [-1, 0]))
        & (image > doubleRoll(image, [1, 0]))
        & (image > doubleRoll(image, [-1, 1]))
        & (image > doubleRoll(image, [0, 1]))
        & (image > doubleRoll(image, [1, 1]))
        & (image > threshold * cp.max(image))
    )
    non_zero_arr = pLarge * image
    positions = np.nonzero(non_zero_arr)
    return positions


"""
Run script
"""
import time

t0 = time.perf_counter()
total_images = 100
reader = await client.submit(create_reader_on_worker, actor=True)
arrays = client.map(partial(a_load_stem_image, reader), range(total_images))
b = client.map(a_peakFind2D, arrays)
b = await client.gather(b)
t1 = time.perf_counter()
print(f"Total time for {total_images} images = {t1-t0}s")


# --------------------------------------------------------------------


# Second attempt: batching


async def a_peakFind2D_batched(image_arrs, threshold=0.01):
    """
    peakFind2D (from ncempy) converted to handle dask arrays.

    Args
    ----
    image_arr: dask.array
        Has dimensions (x, frame_dimensions[0], frame_dimensions[1])
        where x is the number of images on this particular scan
        position.

    Returns
    -------
    positions: tuple(x_pos: da.array, y_pos: da.array)
        Peak positions returned as a tuple of x and y positions.
    """
    if (threshold < 0) or (threshold >= 1):
        print("Error: Threshold must be 0 <= threshold < 1")
        return 0
    positions = []
    for image in image_arrs:
        pLarge = (
            (image > doubleRoll(image, [-1, -1]))
            & (image > doubleRoll(image, [0, -1]))
            & (image > doubleRoll(image, [1, -1]))
            & (image > doubleRoll(image, [-1, 0]))
            & (image > doubleRoll(image, [1, 0]))
            & (image > doubleRoll(image, [-1, 1]))
            & (image > doubleRoll(image, [0, 1]))
            & (image > doubleRoll(image, [1, 1]))
            & (image > threshold * cp.max(image))
        )
        non_zero_arr = pLarge * image
        d_pos = cp.nonzero(non_zero_arr)
        positions.append((cp.asnumpy(d_pos[0]), cp.asnumpy(d_pos[1])))
    return positions


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
    with concurrent.futures.ThreadPoolExecutor(2) as executor:
        for i, result in enumerate(
            executor.map(
                reader.get_block_from_image_number,
                range(image_numbers[0], image_numbers[1]),
            )
        ):
            arr[i] = (await result).data
    return arr


"""
Run script for above:
"""
import concurrent.futures

from distributed import as_completed, wait

total_images = 128 * 128
bytes_per_pattern = 1024 * 1024
max_num_bytes = bytes_per_pattern * 1000  # totally arbitrary right now
batch_size = max_num_bytes // (bytes_per_pattern)  # really just ends up being 1000
num_batches = total_images // batch_size + 1
arrays_batch_futures = []
d_arrays_batch_futures = []
counted_batch_futures = []
positions_futures = []
pools = []
div = num_batches // len(worker_ids) + 1
readers = {}
t0 = time.perf_counter()

for worker_id in worker_ids:
    readers[worker_id] = client.submit(
        create_reader_on_worker, actor=True, workers=worker_id
    )

for worker_id, batch_idx in zip(worker_ids * div, range(num_batches)):
    probes_remaining = total_images - (batch_idx * batch_size)
    this_batch_size = probes_remaining if probes_remaining < batch_size else batch_size
    first_batch_idx = batch_idx * batch_size
    second_batch_idx = this_batch_size + first_batch_idx
    concat_arr = client.submit(
        partial(a_load_stem_image_batch, await readers[worker_id]),
        (first_batch_idx, second_batch_idx),
        workers=worker_id,
    )
    # arrays_batch_futures.append(concat_arr)

    d_concat_arr = client.submit(cp.asarray, concat_arr, workers=worker_id)
    arrays_batch_futures.append(d_concat_arr)

    positions = client.submit(a_peakFind2D_batched, d_concat_arr, workers=worker_id)
    # arrays_batch_futures.append(concat_arr)
    # d_arrays_batch_futures.append(d_concat_arr)
    positions_futures.append(positions)

await client.gather(positions_futures)
t1 = time.perf_counter()

print(f"Total time: {t1-t0}")

# ----------------

"""
Another run script, apparently creates a lot of tasks
"""

# Persists the arrays in worker memory for fast accesstotal_images = 128(
from distributed import as_completed, wait

total_images = 128 * 128
bytes_per_pattern = 1024 * 1024
max_num_bytes = bytes_per_pattern * 1000  # totally arbitrary right now
batch_size = max_num_bytes // (bytes_per_pattern)  # really just ends up being 1000
num_batches = total_images // batch_size + 1
arrays_batch_futures = []
d_arrays_batch_futures = []
counted_batch_futures = []
positions_futures = []
pools = []
div = num_batches // len(worker_ids) + 1
readers = {}
t0 = time.perf_counter()

for worker_id in worker_ids:
    readers[worker_id] = await client.submit(
        create_reader_on_worker, actor=True, workers=worker_id
    )

for worker_id, batch_idx in zip(worker_ids * div, range(num_batches)):
    probes_remaining = total_images - (batch_idx * batch_size)
    this_batch_size = probes_remaining if probes_remaining < batch_size else batch_size
    first_batch_idx = batch_idx * batch_size
    second_batch_idx = this_batch_size + first_batch_idx
    batched_arrays = client.map(
        partial(a_load_stem_image, readers[worker_id]),
        range(first_batch_idx, second_batch_idx),
        workers=worker_id,
    )
    concat_arr = client.submit(concatenate_futures, batched_arrays, workers=worker_id)
    d_concat_arr = client.submit(
        cp.asarray, concat_arr, dtype=uint16, workers=worker_id
    )
    positions = client.submit(a_peakFind2D_batched, d_concat_arr, workers=worker_id)
    # arrays_batch_futures.append(concat_arr)
    # d_arrays_batch_futures.append(d_concat_arr)
    positions_futures.append(positions)

await client.gather(positions_futures)
t1 = time.perf_counter()

print(f"Total time: {t1-t0}")


# -------------------------------------

# This one uses kernels from py4dstem


import time

from dask.distributed import get_client, get_worker


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


async def get_maxima_wrapper(
    image_number=None, arr=None, get_maximal_points=None, wid=None
):

    blocks = (arr.shape[1],)
    threads = (arr.shape[2],)
    client = get_client()
    future = client.submit(
        get_maxima_2D,
        ar=arr,
        blocks=blocks,
        threads=threads,
        get_maximal_points=get_maximal_points,
        workers=wid,
    )
    return future


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


import concurrent.futures

import distributed
from distributed import as_completed, wait

total_images = 128 * 128
bytes_per_pattern = 1024 * 1024
max_num_bytes = bytes_per_pattern * 100  # totally arbitrary right now
batch_size = max_num_bytes // (bytes_per_pattern)  # really just ends up being 1000
num_batches = total_images // batch_size + 1
arrays_batch_futures = []
d_arrays_batch_futures = []
counted_batch_futures = []
positions_futures = []
pools = []
div = num_batches // len(gpu_workers) + 1

t0 = time.perf_counter()


# workers_info = client.scheduler_info()["workers"]
# worker_ids = []
# for key in workers_info:
#     worker_info = workers_info[key]
#     worker_ids.append(worker_info["id"]) # Gets the worker ID
# gpu_workers = [x for x in worker_ids if "GPU" in x]
# head_gpu_worker = gpu_workers[0]

for worker_id in gpu_workers:
    readers[worker_id] = client.submit(
        create_reader_on_worker, actor=True, workers=worker_id
    )
# reader = client.submit(create_reader_on_worker,
#                                              actor=True,
#                                              workers=head_gpu_worker)

for worker_id, batch_idx in zip(gpu_workers * div, range(num_batches)):
    probes_remaining = total_images - (batch_idx * batch_size)
    this_batch_size = probes_remaining if probes_remaining < batch_size else batch_size
    first_batch_idx = batch_idx * batch_size
    second_batch_idx = this_batch_size + first_batch_idx
    concat_arr = client.submit(
        partial(a_load_stem_image_batch, await readers[worker_id]),
        (first_batch_idx, second_batch_idx),
        workers=worker_id,
    )
    # arrays_batch_futures.append(concat_arr)

    d_concat_arr = client.submit(
        cp.asarray, concat_arr, dtype=cp.uint16, workers=worker_id
    )
    get_maximal_points = kernels["maximal_pts_uint16"]
    positions = client.submit(
        get_maxima_2D,
        ar=d_concat_arr,
        get_maximal_points=get_maximal_points,
        workers=worker_id,
    )
    positions_futures.append(positions)

# await client.gather(positions_futures)
await wait(positions_futures)
t1 = time.perf_counter()

print(f"Total time: {t1-t0}")


# ------

# This one runs from an IO node, sends out to GPU workers


async def a_load_stem_image_batch(reader, image_numbers=(0, 1), thread_pool=False):
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

    if thread_pool:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for i, result in enumerate(
                executor.map(
                    reader.get_block_from_image_number,
                    range(image_numbers[0], image_numbers[1]),
                )
            ):
                arr[i] = (await result).data

    else:
        for image_number in range(image_numbers[0], image_numbers[1]):
            stack_idx = image_number - image_numbers[0]
            arr[stack_idx] = (
                await reader.get_block_from_image_number(image_number)
            ).data

    return arr


import concurrent.futures

import distributed
from distributed import as_completed, wait

total_images = 512 * 512
bytes_per_pattern = 1024 * 1024
max_num_bytes = bytes_per_pattern * 100  # totally arbitrary right now
batch_size = max_num_bytes // (bytes_per_pattern)  # really just ends up being 1000
num_batches = total_images // batch_size + 1
arrays_batch_futures = []
d_arrays_batch_futures = []
counted_batch_futures = []
positions_futures = []
pools = []
div = num_batches // len(io_workers) + 1
readers = {}
t0 = time.perf_counter()

for io_worker in io_workers:
    # Create one reader on the head io node
    readers[io_worker] = await client.submit(
        create_reader_on_worker, actor=True, workers=io_worker
    )
for worker_id, batch_idx in zip(io_workers * div, range(num_batches)):
    probes_remaining = total_images - (batch_idx * batch_size)
    this_batch_size = probes_remaining if probes_remaining < batch_size else batch_size
    first_batch_idx = batch_idx * batch_size
    second_batch_idx = this_batch_size + first_batch_idx
    concat_arr = client.submit(
        partial(a_load_stem_image_batch, readers[worker_id], thread_pool=False),
        (first_batch_idx, second_batch_idx),
        workers=worker_id,
    )
    d_concat_arr = client.submit(
        cp.asarray, concat_arr, dtype=cp.uint16, workers=worker_map[worker_id][0]
    )
    get_maximal_points = kernels["maximal_pts_uint16"]
    positions = client.submit(
        get_maxima_2D,
        ar=d_concat_arr,
        get_maximal_points=get_maximal_points,
        workers=worker_map[worker_id],
    )
    positions_futures.append(positions)

# await client.gather(positions_futures)
await wait(positions_futures)
t1 = time.perf_counter()
print(f"Total time: {t1-t0}")
