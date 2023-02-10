import os
import pathlib
from typing import List

from pydantic import BaseModel, BaseSettings, validator


class JupyterKernel(BaseModel):
    base_path: pathlib.Path = (
        pathlib.Path(os.environ["HOME"]) / ".local" / "share" / "jupyter" / "kernels"
    )
    name: str = "stempy-cuda"
    helper_inside: str = "kernel_helper_inside.sh"
    helper_outside: str = "kernel_helper_outside.sh"
    cuda: bool = True

    @validator("name")
    def check_kernel_directory(cls, v, values):
        stempy_cuda_path = pathlib.Path(values["base_path"] / v)
        print(stempy_cuda_path)
        if not stempy_cuda_path.exists():
            raise FileNotFoundError
        return v

    @validator("helper_inside")
    def check_help_inside(cls, v, values):
        helper_inside_path = pathlib.Path(values["base_path"] / v)
        if not helper_inside_path.exists():
            raise FileNotFoundError
        return v

    @validator("helper_outside")
    def check_help_outside(cls, v, values):
        helper_outside_path = pathlib.Path(values["base_path"] / v)
        if not helper_outside_path.exists():
            raise FileNotFoundError
        return v


class NERSCJupyterSession(BaseSettings):
    kernel: JupyterKernel = JupyterKernel()
    USER: str
    HOME: pathlib.Path
    JUPYTERHUB_SERVER_NAME: str
    JUPYTERHUB_USER: str
    JUPYTERHUB_ACTIVITY_URL: str
    NERSC_HOST: str
    PROXY_SOCKET: str

    class Config:
        case_sensitive = True
