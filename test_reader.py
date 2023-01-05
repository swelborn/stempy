import sys
import os

sys.path.insert(0,"/source/stempy/build/lib")
import stempy
from stempy import io as stio

print("You are using stempy from this file location: ")
print(os.path.dirname(stempy.__file__))

# print('electron_count_cori.py')

# import argparse

# parser = argparse.ArgumentParser()
# parser.add_argument('--scan_number','-s', type=int)
# parser.add_argument('--threshold', '-t', type=float)
# parser.add_argument('--num_threads','-r',type=int, default=0)
# parser.add_argument('--location', '-l', type=str, default='/global/cscratch1/sd/percius')
# parser.add_argument('--threaded', '-d', type=int, default=1) # 1 for threaded, 0 for not
# parser.add_argument('--pad', '-p', action='store_true', default=True)
# parser.add_argument('--multi-pass', '-m', dest='multi_pass',action='store_true') # multi-pass testing
# args = parser.parse_args()

from pathlib import Path
import sys
import time
import os

import numpy as np

# import stempy.io as stio
# import stempy.image as stim
# from mpi4py import MPI

# comm = MPI.COMM_WORLD
# rank = comm.Get_rank()

# # Inputs
# scanNum = args.scan_number
# th = float(args.threshold)
# drive = Path(args.location)
# num_threads = args.num_threads
# pad = args.pad # pad scan num with zeros

# Empty dark reference
dark0 = np.zeros((576,576))

# Empty gain
gain0 = None

# Setup file name and path
scanNum = 22
drive = Path("/pscratch/sd/s/swelborn/20230103_testing_stempy_reader/")
pad = True
if pad:
    scanName = 'data_scan{:010}_*.data'.format(scanNum)
else:
    scanName = 'data_scan{}_*.data'.format(scanNum)

print('Using files in {}'.format(drive))
print('scan name = {}'.format(scanName))

files = drive.glob(scanName)

sorted_by_mtime_ascending = sorted(files, key=lambda t: os.stat(t).st_mtime)
iFiles = [str(f) for f in sorted_by_mtime_ascending]

# # Electron count the data
sReader = stio.reader(iFiles, stio.FileVersion.VERSION5, backend="multi-pass", threads=1)

sReader.create_scan_map()
print(sReader)
block = sReader.get_block_from_image_number(3)
print(block.header.version)
print(memoryview(block).shape)

import numpy as np
arr = np.array(block, copy=False)

try:
    assert arr.shape == (1, 576, 576)
except:
    print("no good")
else:
    print("all good")

import ncempy.algo.peak_find as peakfind

pos = peakfind.peakFind2D(arr[0], 0.05)

print(pos)


# print('start counting #{}'.format(scanNum))
# t0 = time.time()

# electron_counted_data = stim.electron_count(sReader, dark0, gain=gain0,number_of_samples=1200,verbose=True,threshold_num_blocks=20,xray_threshold_n_sigma=175, background_threshold_n_sigma=th)

# t1 = time.time()


# if rank == 0:
#     print('total time = {}'.format(t1-t0))
#     # as H5 file
#     outPath = drive / Path('data_scan{}_th{}_electrons.h5'.format(scanNum, th))
#     stio.save_electron_counts(outPath, electron_counted_data)
#     print(outPath)
