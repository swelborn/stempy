#!/bin/bash

dask-cuda-worker \
    --scheduler-file $SCHEDULER_FILE \
    --name GPU_${SLURMD_NODENAME} \
    --interface hsn0 \
    --rmm-pool-size 38GB \
    --preload $PRELOAD_FILE \
    --enable-tcp-over-ucx \
    --rmm-log-directory RMM_LOG_DIR \
    --rmm-track-allocations True \
    --protocol "tcp" \
    --preload dask_cuda.initialize 

# dask worker \
#     --scheduler-file $SCHEDULER_FILE \
#     --name IO_${SLURMD_NODENAME} \
#     --interface hsn0 \
#     --preload $PRELOAD_FILE \
#     --protocol "tcp" \ 
#     --nworkers 16 \
#     --nthreads 1