#!/bin/bash
#SBATCH --ntasks=16
#SBATCH --ntasks-per-node=1
#SBATCH --account=dasrepo_g
#SBATCH --constraint=gpu
#SBATCH --gpus-per-node=4
#SBATCH --qos=early_science
#SBATCH --time 00:09:00


########SBATCH --qos=jupyter
set -xo pipefail
date
pwd

# load aliases like module
source /etc/profile


# loads cuda 11.5
module load cudatoolkit/21.9_11.4
module load PrgEnv-nvidia
# module load gcc/9.3.0 (only for building)

CONDA_ROOT=/global/u2/q/quasiben/miniconda3
source $CONDA_ROOT/etc/profile.d/conda.sh
ENV=ucx
#export RDMAV_HUGEPAGES_SAFE=1
#export UCX_IB_FORK_INIT=n

#cd /global/u2/q/quasiben/miniconda3/envs/ucx/lib/python3.8/site-packages/dask_cuda/benchmarks/
#UCX_MAX_RNDV_RAILS=1 python dask_cuda/benchmarks/local_cudf_merge.py -d 0,1,2,3 --runs 10 -c 50_000_000 -p ucx

conda activate $ENV
which python

# Each worker uses all GPUs on its node

# Prepare output directory
JOB_OUTPUT_DIR=/global/homes/q/quasiben/dask-merge-bench-$SLURM_NNODES-nodes
mkdir -p $JOB_OUTPUT_DIR

# Start a single scheduler on node 0 of the allocation
UCX_MAX_RNDV_RAILS=1 \
UCX_MEMTYPE_REG_WHOLE_ALLOC_TYPES=cuda \
DASK_DISTRIBUTED__COMM__UCX__CREATE_CUDA_CONTEXT=True \
UCX_MEMTYPE_CACHE=n \
UCX_TCP_MAX_CONN_RETRIES=255 \
DASK_DISTRIBUTED__COMM__TIMEOUTS__CONNECT=3600s \
DASK_DISTRIBUTED__COMM__TIMEOUTS__TCP=3600s \
python -m distributed.cli.dask_scheduler \
--protocol ucx \
--interface hsn0 \
--no-dashboard \
--scheduler-file "$JOB_OUTPUT_DIR/cluster.json" &

# Wait for the scheduler to start
sleep 5
until [ -f $JOB_OUTPUT_DIR/cluster.json ]
do
     sleep 5
done
echo "File found"
SCHED_ADDR="$(python -c "
import json
with open('$JOB_OUTPUT_DIR/cluster.json') as f:
  print(json.load(f)['address'])
")"
# Start one worker per node in the allocation (one process started per GPU)
echo "Starting Workers..."
for HOST in `scontrol show hostnames "$SLURM_JOB_NODELIST"`; do
  mkdir -p $JOB_OUTPUT_DIR/$HOST
  sleep 1

  if [ $HOST == $_HOST ]; then
    echo "Running worker on Head Node..."
    UCX_TCP_MAX_CONN_RETRIES=255 \
    DASK_DISTRIBUTED__COMM__TIMEOUTS__CONNECT=3600s \
    DASK_DISTRIBUTED__COMM__TIMEOUTS__TCP=3600s \
    UCX_MAX_RNDV_RAILS=1 \
    UCX_MEMTYPE_REG_WHOLE_ALLOC_TYPES=cuda \
    UCX_MEMTYPE_CACHE=n \
    python -m dask_cuda.cli.dask_cuda_worker \
      --rmm-pool-size 38GB \
      --interface hsn0 \
      --local-directory $JOB_OUTPUT_DIR/$HOST \
      --scheduler-file $JOB_OUTPUT_DIR/cluster.json &
  else
    UCX_TCP_MAX_CONN_RETRIES=255 \
    DASK_DISTRIBUTED__COMM__TIMEOUTS__CONNECT=3600s \
    DASK_DISTRIBUTED__COMM__TIMEOUTS__TCP=3600s \
    UCX_MAX_RNDV_RAILS=1 \
    UCX_MEMTYPE_REG_WHOLE_ALLOC_TYPES=cuda \
    UCX_MEMTYPE_CACHE=n \
    srun -N 1 -n 1 -w "$HOST" python -m dask_cuda.cli.dask_cuda_worker \
      --rmm-pool-size 38GB \
      --local-directory $JOB_OUTPUT_DIR/$HOST \
      --interface hsn0 \
      --scheduler-file $JOB_OUTPUT_DIR/cluster.json &
  fi

done
# Wait for the workers to start
sleep 10

# Execute the client script on node 0 of the allocation
# The client script should shut down the scheduler before exiting
#"$CONDA_PREFIX/lib/python3.8/site-packages/dask_cuda/benchmarks/local_cudf_merge.py" \
echo "Client start: $(date +%s)"
   DASK_DISTRIBUTED__COMM__TIMEOUTS__CONNECT=3600s \
   DASK_DISTRIBUTED__COMM__TIMEOUTS__TCP=3600s \
   UCX_MAX_RNDV_RAILS=1 \
   UCX_TCP_MAX_CONN_RETRIES=255 \
   UCX_MEMTYPE_REG_WHOLE_ALLOC_TYPES=cuda \
   UCX_MEMTYPE_CACHE=n \
   DASK_DISTRIBUTED__COMM__UCX__CREATE_CUDA_CONTEXT=True \
   python \
   "$CONDA_PREFIX/lib/python3.8/site-packages/dask_cuda/benchmarks/local_cudf_merge.py"  \
  --scheduler-address "$SCHED_ADDR" \
   -c 50_000_000 \
  --frac-match 0.3 \
  --protocol ucx \
  --interface hsn0 \
  --disable-rmm-pool \
  --markdown \
  --all-to-all \
  --runs 10 > $JOB_OUTPUT_DIR/raw_data.txt

echo "Client done: $(date +%s)"
# Wait for the cluster to shut down gracefully
sleep 2