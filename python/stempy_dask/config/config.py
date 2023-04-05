import os
import re
from enum import Enum
from pathlib import Path
from pprint import pprint
from typing import Dict, List, Optional, Union

import orjson
from pydantic import BaseModel, BaseSettings, Field, root_validator, validator
from stempy_dask.schemas.jupyter_session import NERSCJupyterSession
from stempy_dask.utils import log as pretty_logger


class InterpreterShell(str, Enum):
    UNKNOWN = "unknown"
    JUPYTER = "ZMQInteractiveShell"
    IPYTHON = "TerminalInteractiveShell"
    STANDARD = "standard_interpreter"


class Interpreter:
    def __init__(self, shell=None):
        if shell is None:
            try:
                from IPython import get_ipython

                shell = get_ipython().__class__.__name__
            except ImportError:
                shell = "standard_interpreter"
            except NameError:
                shell = "unknown"
            if shell == "NoneType":
                shell = "standard_interpreter"
        self.shell = InterpreterShell(shell)
        self.jupyter = self.shell == InterpreterShell.JUPYTER
        self.ipython = self.shell == InterpreterShell.IPYTHON
        self.standard = self.shell == InterpreterShell.STANDARD


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


class CondaEnvironment(BaseModel):
    name: str
    packages: Dict[str, str]

    @classmethod
    def from_environment(cls, name: str):
        packages = {}
        meta_dir = os.path.join("/opt/conda/", "conda-meta")
        for fn in os.listdir(meta_dir):
            if fn.endswith(".json"):
                with open(os.path.join(meta_dir, fn), "r") as f:
                    data = orjson.loads(f.read())
                    if data["name"] != "python":
                        packages[data["name"]] = data["version"]
        return cls(name=name, packages=packages)


class System(BaseSettings):
    NERSC_HOST: str
    HOME: Path
    USER: str
    SCRATCH: Optional[Path]

    class Config:
        case_sensitive = True
        env_file = ".env"


# class CustomOrjsonEncoder(orjson.JSONEncoder):
#     def default(self, obj):
#         if isinstance(obj, InterpreterShell):
#             return obj.value
#         elif isinstance(obj, Interpreter):
#             return {"shell": obj.shell}
#         return super().default(obj)


# def custom_orjson_decoder(data):
#     if isinstance(data, bytes):
#         data = data.decode()
#     if "shell" in data:
#         return InterpreterShell(data["shell"])
#     return data


def orjson_dumps(v, *, default):
    # orjson.dumps returns bytes, to match standard json.dumps we need to decode
    return orjson.dumps(v, default=default, option=orjson.OPT_SERIALIZE_NUMPY).decode()


class Settings(BaseSettings):
    interpreter: Interpreter
    system_settings: System
    jupyter_session: Optional[NERSCJupyterSession]
    slurm_settings: Optional[Union[SlurmSettings, SlurmGPUSettings]]
    shifter_settings: Optional[ShifterSettings]
    # dask_dir: Path = Path("dask_cluster_workspace")

    # Deserialize interpreter properly
    @validator("interpreter", pre=True)
    def valid_interpreter(cls, v: Union[str, Interpreter]) -> Interpreter:
        if isinstance(v, Interpreter):
            return v
        if isinstance(v, str):
            return Interpreter(v)
        raise TypeError("Invalid Foo type")

    # @validator("dask_dir", always=True)
    # @classmethod
    # def set_dask_dir(cls, v, values):
    #     dir = Path(values["system_settings"].SCRATCH) / v
    #     if not dir.exists():
    #         try:
    #             dir.mkdir()
    #         except FileExistsError:
    #             return v

    #     return dir

    class Config:
        case_sensitive = True
        env_file = ".env"
        json_encoders = {Interpreter: lambda v: v.shell}
        json_decoders = {Interpreter: lambda v: v.shell}
        json_loads = orjson.loads
        json_dumps = orjson_dumps
        arbitrary_types_allowed = True


# Detect system and interpreter
system = System()
interpreter = Interpreter()
conda_env = CondaEnvironment.from_environment("base")

if interpreter.jupyter and system.NERSC_HOST == "perlmutter":
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

elif system.NERSC_HOST == "perlmutter" and "nid" in os.environ["HOST"]:
    if "SLURM_JOB_GPUS" in os.environ:
        slurm_settings = SlurmGPUSettings()
    else:
        slurm_settings = SlurmSettings()
    shifter_settings = ShifterSettings()
    settings = Settings(
        interpreter=interpreter,
        system_settings=system,
        slurm_settings=slurm_settings,
        shifter_settings=shifter_settings,
    )

elif system.NERSC_HOST == "perlmutter" and "login" in os.environ["HOST"]:
    shifter_settings = ShifterSettings()
    settings = Settings(
        interpreter=interpreter,
        system_settings=system,
        shifter_settings=shifter_settings,
    )

else:
    settings = Settings(
        interpreter=interpreter,
        system_settings=system,
    )


# Print settings to log
log = pretty_logger.create_logger("config", settings)
log.info("-" * 80)
log.info("{:-^80}".format(" IMPORTED SYSTEM CONFIGURATION "))
log.info(pprint(settings.dict()))
log.info("-" * 80)
log.info(f"Current working directory: {os.getcwd()}")
log.info("-" * 80)
log.debug("{:-^80}".format(" CONDA ENVIRONMENT "))
log.debug(conda_env.json(indent=2))
