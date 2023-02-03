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

# #start scheduler
# DASK_DISTRIBUTED__COMM__TIMEOUTS__CONNECT=3600s \
# DASK_DISTRIBUTED__COMM__TIMEOUTS__TCP=3600s \
# shifter --image=$image dask worker \
#     --scheduler-file $scheduler_file \
#     --name IO_${SLURMD_NODENAME} \
#     --nworkers 8 \
#     --nthreads 1 \
#     --interface hsn0 \
#     --protocol "tcp" \
#     --preload $preload_file &
    
#start gpu workers
UCX_TCP_MAX_CONN_RETRIES=255 \
DASK_DISTRIBUTED__COMM__TIMEOUTS__CONNECT=3600s \
DASK_DISTRIBUTED__COMM__TIMEOUTS__TCP=3600s \
UCX_MAX_RNDV_RAILS=1 \
UCX_MEMTYPE_REG_WHOLE_ALLOC_TYPES=cuda \
UCX_MEMTYPE_CACHE=n \
SCHEDULER_FILE=$scheduler_file \
PRELOAD_FILE=$preload_file \
/usr/bin/srun shifter --image=samwelborn/stempy-cuda \
    --volume="/global/homes/s/swelborn/stempy-dask/:/build/" \
    /build/start_dask_workers.sh

echo "Killing scheduler"
kill -9 $dask_pid