#!/bin/bash
exit 
echo "Starting scheduler..."

scheduler_file=$SCRATCH/scheduler_file.json
rm -f $scheduler_file

#Modify this with your dask image name
image=samwelborn/stempy-cuda
preload_file=./preload_serializers.py
RMM_LOG_DIR="${SCRATCH}/rmm-logs/"

echo "Using image $image"
echo "Using preload file: $preload_file"
echo "Using RMM Log Directory: $RMM_LOG_DIR"

#start scheduler
UCX_MAX_RNDV_RAILS=1 \
UCX_MEMTYPE_REG_WHOLE_ALLOC_TYPES=cuda \
DASK_DISTRIBUTED__COMM__UCX__CREATE_CUDA_CONTEXT=True \
UCX_MEMTYPE_CACHE=n \
UCX_TCP_MAX_CONN_RETRIES=255 \
DASK_DISTRIBUTED__COMM__TIMEOUTS__CONNECT=3600s \
DASK_DISTRIBUTED__COMM__TIMEOUTS__TCP=3600s \
/usr/bin/shifter dask scheduler \
    --interface hsn0 \
    --scheduler-file $scheduler_file \
    --preload $preload_file \
    --preload dask_cuda.initialize &

dask_pid=$!

# Wait for the scheduler to start
sleep 2
until [ -f $scheduler_file ]
do
     sleep 2
done

echo "Starting workers"

    
#start gpu workers
UCX_TCP_MAX_CONN_RETRIES=255 \
DASK_DISTRIBUTED__COMM__TIMEOUTS__CONNECT=3600s \
DASK_DISTRIBUTED__COMM__TIMEOUTS__TCP=3600s \
UCX_MAX_RNDV_RAILS=1 \
UCX_MEMTYPE_REG_WHOLE_ALLOC_TYPES=cuda \
UCX_MEMTYPE_CACHE=n \
SCHEDULER_FILE=$scheduler_file \
PRELOAD_FILE=$preload_file \
srun shifter --image=${image} \
    dask-cuda-worker \
    --scheduler-file $scheduler_file \
    --name GPU_${SLURMD_NODENAME} \
    --interface hsn0 \
    --rmm-pool-size 38GB \
    --preload $preload_file \
    --preload dask_cuda.initialize 

echo "Killing scheduler"
kill -9 $dask_pid

    # --enable-tcp-over-ucx \
    # --rmm-log-directory RMM_LOG_DIR \
    # --rmm-track-allocations True \
    # --protocol "tcp" \