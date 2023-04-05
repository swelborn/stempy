#!/bin/bash
export PYTHONPATH=$PYTHONPATH:/global/homes/s/swelborn/stempy_swelborn/stempy/python/
scheduler_file=/pscratch/sd/s/swelborn/stempy_benchmarks/20230222_034241-nodes-data/dask-2node-smalldata/scheduler_file.json
RMM_LOG_DIR=/pscratch/sd/s/swelborn/stempy_benchmarks/20230222_034241-nodes-data/dask-2node-smalldata/rmm-logs
workdir=/pscratch/sd/s/swelborn/stempy_benchmarks/20230222_034241-nodes-data/dask-2node-smalldata

python /global/homes/s/swelborn/stempy_swelborn/stempy/python/stempy_dask/benchmarking/scripts/count_dask.py \
  --scheduler-file $scheduler_file \
  --protocol tcp \
  --interface hsn0 \
  --markdown \
  --rmm-pool-size 38GB \
  --rmm-log-directory $RMM_LOG_DIR \
  --workdir $workdir \
  --runs 10 \
  --no-silence-logs 