import os
from pathlib import Path
from typing import List, Optional, Union

from pydantic import BaseModel, BaseSettings, root_validator, validator
from stempy_dask.config.schemas.jupyter_session import NERSCJupyterSession
from stempy_dask.utils import log as pretty_logger


class Interpreter:
    def __init__(self):
        try:
            from IPython import get_ipython

            shell = get_ipython().__class__.__name__
        except ImportError or NameError:
            self.shell = "standard_interpreter"
            self.jupyter, self.ipython, self.standard = (
                False,
                False,
                True,
            )
        if shell == "ZMQInteractiveShell":
            self.shell = "jupyter"
            self.jupyter, self.ipython, self.standard = (
                True,
                False,
                False,
            )
        elif shell == "TerminalInteractiveShell":
            self.shell = "ipython"
            self.jupyter, self.ipython, self.standard = (
                False,
                True,
                False,
            )
        else:
            self.shell = "unknown"
            self.jupyter, self.ipython, self.standard = (
                False,
                False,
                False,
            )


class SlurmSettings(BaseSettings):
    SLURM_JOB_USER: str
    SLURM_TASKS_PER_NODE: str
    SLURM_JOB_UID: str
    SLURM_TASK_PID: str
    SLURM_LOCALID: str
    SLURM_SUBMIT_DIR: str
    SLURMD_NODENAME: str
    SLURM_NODE_ALIASES: str
    SLURM_CLUSTER_NAME: str
    SLURM_CPUS_ON_NODE: str
    SLURM_JOB_CPUS_PER_NODE: str
    SLURM_GTIDS: str
    SLURM_JOB_PARTITION: str
    SLURM_JOB_NUM_NODES: str
    SLURM_JOBID: str
    SLURM_JOB_QOS: str
    SLURM_PROCID: str
    SLURM_CPUS_PER_TASK: str
    SLURM_NTASKS: str
    SLURM_TOPOLOGY_ADDR: str
    SLURM_TOPOLOGY_ADDR_PATTERN: str
    SLURM_SCRIPT_CONTEXT: str
    SLURM_WORKING_CLUSTER: str
    SLURM_NODELIST: str
    SLURM_JOB_ACCOUNT: str
    SLURM_PRIO_PROCESS: str
    SLURM_NPROCS: str
    SLURM_NNODES: str
    SLURM_SUBMIT_HOST: str
    SLURM_JOB_ID: str
    SLURM_NODEID: str
    SLURM_JOB_NAME: str
    SLURM_NTASKS_PER_NODE: str
    SLURM_JOB_GID: str
    SLURM_JOB_NODELIST: str

    class Config:
        case_sensitive = True
        env_file = ".env"


class SlurmGPUSettings(SlurmSettings):
    SLURM_JOB_GPUS: str
    SLURM_GPUS_ON_NODE: str
    SLURM_GPU_FREQ: str
    SLURM_GPUS_PER_TASK: str

    class Config:
        case_sensitive = True
        env_file = ".env"


class ShifterSettings(BaseSettings):
    SHIFTER_RUNTIME: str
    SHIFTER_IMAGE: str
    SHIFTER_MODULE_MPICH: str
    SHIFTER_MODULE_GPU: str
    SHIFTER_IMAGEREQUEST: str

    class Config:
        case_sensitive = True
        env_file = ".env"


class System(BaseSettings):
    system: str = "perlmutter"
    HOME: Path
    USER: str
    SCRATCH: Optional[Path]

    @validator("system", pre=True, always=True)
    def _determine_system(cls, v):
        try:
            v = os.environ["NERSC_HOST"]
        except KeyError:
            v = "local"
            return v
        return v

    class Config:
        case_sensitive = True
        env_file = ".env"


class Settings(BaseSettings):
    interpreter: Interpreter
    system_settings: System
    jupyter_session: Optional[NERSCJupyterSession]
    slurm_settings: Optional[Union[SlurmSettings, SlurmGPUSettings]]
    shifter_settings: Optional[ShifterSettings]
    dask_dir: Path = Path("dask_cluster_workspace")

    @validator("dask_dir", always=True)
    @classmethod
    def set_dask_dir(cls, v, values):
        dir = Path(values["system_settings"].SCRATCH) / v
        if not dir.exists():
            try:
                dir.mkdir()
            except FileExistsError:
                return v

        return dir

    class Config:
        case_sensitive = True
        env_file = ".env"


system = System()
interpreter = Interpreter()

if interpreter.jupyter and system.system == "perlmutter":
    session = NERSCJupyterSession()
    slurm_settings = SlurmGPUSettings()
    shifter_settings = ShifterSettings()
    settings = Settings(
        interpreter=interpreter,
        system_settings=system,
        jupyter_session=session,
        slurm_settings=slurm_settings,
        shifter_settings=shifter_settings,
    )
elif system.system == "perlmutter":
    slurm_settings = SlurmGPUSettings()
    shifter_settings = ShifterSettings()
    settings = Settings(
        interpreter=interpreter,
        system_settings=system,
        slurm_settings=slurm_settings,
        shifter_settings=shifter_settings,
    )
else:
    settings = Settings(interpreter=interpreter, system_settings=system)

log = pretty_logger.create_logger("config", settings)
