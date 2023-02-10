import os
import signal
from datetime import datetime
from pathlib import Path
from subprocess import Popen
from threading import Thread
from typing import Union

import cupy as cp
import dask
import jinja2
import rmm
from dask.distributed import Client
from stempy_dask.config import config as cfg
from stempy_dask.config.config import Settings
from stempy_dask.utils import log as pretty_logger

log = pretty_logger.create_logger("dask", cfg.settings)


class DaskSettings:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.workdir_parent: Path = self.settings.dask_dir
        self.io_workers: int = 0
        self.expected_gpu_workers: Union[int, None] = 16
        self.total_expected_workers: Union[int, None] = self.expected_gpu_workers
        self.timestamp: datetime = datetime.now()
        self.dashboard_link: str = (
            "{JUPYTERHUB_SERVICE_PREFIX}proxy/{host}:{port}/status"
        )
        self.setup_subdir()
        self.scheduler_file_path: Path = self.workdir / "scheduler_file.json"
        self.preload_file_path: Path = (
            Path(__file__).parent / "scripts" / "preload_serializers.py"
        )

    def setup_subdir(self):
        ts = self.timestamp.strftime("%Y%m%d_%H%M%S")
        self.workdir: Path = self.workdir_parent / ts
        not_made = True
        count = 0
        while not_made:
            try:
                self.workdir.mkdir()
                not_made = False
            except FileExistsError:
                count += 1
                self.workdir = self.workdir_parent / (ts + "-" + str(count))


class DaskScripts:
    def __init__(self, dask_settings: DaskSettings, settings: Settings):
        self.dask_settings = dask_settings
        self.settings = settings
        self.dask_script_path = self.dask_settings.workdir / "dask.sh"
        self.worker_script_path = self.dask_settings.workdir / "workers.sh"
        self.logs_path = self.dask_settings.workdir / "logs.txt"
        self.render_dask_scripts()
        self.write_script(self.dask_script_path, self.scripts["dask"])
        self.write_script(self.worker_script_path, self.scripts["workers"])
        self.start_script()

    def render_dask_scripts(self):
        self.scripts = {}
        template_loader = jinja2.FileSystemLoader(
            searchpath=Path(__file__).parent / "config" / "templates"
        )

        template_name = "dask.sh.j2"
        template_env = jinja2.Environment(loader=template_loader)
        template = template_env.get_template(template_name)

        try:
            self.scripts["dask"] = template.render(
                dask_settings=self.dask_settings,
                settings=self.settings,
            )
        except:
            raise

        template_name = "workers.sh.j2"
        template = template_env.get_template(template_name)

        try:
            self.scripts["workers"] = template.render(
                dask_settings=self.dask_settings,
                settings=self.settings,
            )
        except:
            raise

    @staticmethod
    def write_script(path, script):
        with (path).open("w") as fp:
            fp.write(script)
        path.chmod(0o740)

    def start_script(self):

        self.logs_path = self.dask_script_path.parent / "logs.txt"
        self.logfile = open(self.logs_path, "w")
        self.process = Popen(
            self.dask_script_path,
            stdout=self.logfile,
            stderr=self.logfile,
        )

    def start(self):
        self.thread = Thread(target=self.start_script, args=[self])
        self.thread.start()

    def end(self):
        self.process.kill()
        self.thread.join()


class DaskClient:
    def __init__(self, dask_scripts: DaskScripts, wait_for_workers: bool = True):
        self.dask_scripts = dask_scripts
        self.settings = dask_scripts.settings
        self.dask_settings = dask_scripts.dask_settings
        self.system_settings = dask_scripts.settings.system_settings
        self.wait_for_workers = wait_for_workers

    async def start(self):
        self.dask_settings = self.dask_scripts.dask_settings

        if self.settings.system_settings.system == "perlmutter":
            dask.config.config["distributed"]["dashboard"][
                "link"
            ] = self.dask_settings.dashboard_link

        self.client = await Client(
            scheduler_file=self.dask_settings.scheduler_file_path, asynchronous=True
        )

        if self.wait_for_workers:
            await self.client.wait_for_workers(
                n_workers=self.dask_settings.total_expected_workers
            )
            await self.cuda_allocator()
            await self.get_worker_info()

        return self.client

    async def cuda_allocator(self):
        await self.client.run(cp.cuda.set_allocator, rmm.rmm_cupy_allocator)

    async def get_worker_info(self):
        self.workers_info = self.client.scheduler_info()["workers"]
        self.worker_ids = []
        for key in self.workers_info:
            worker_info = self.workers_info[key]
            self.worker_ids.append(worker_info["id"])  # Gets the worker ID
        if self.system_settings.system == "perlmutter":
            self.gpu_workers = [x for x in self.worker_ids if "GPU" in x]
            self.head_gpu_worker = self.gpu_workers[0]
        # TODO: other systems / IO workers
        # elif on_cori_gpu:
        #     gpu_workers = [x for x in worker_ids]
        #     head_gpu_worker = gpu_workers[0]
        log.info(f"Total workers: {len(self.worker_ids)}")
        log.info(f"Head GPU worker: {self.head_gpu_worker}")
        log.info(f"GPU workers: {self.gpu_workers}")
        if self.dask_settings.io_workers > 0:
            io_workers = [x for x in self.worker_ids if "IO" in x]
            head_io_worker = io_workers[0]
            gpu_workers_to_io_workers = len(gpu_workers) // len(io_workers)
            gpu_workers_divvied = [
                [gpu_workers[i], gpu_workers[i + 1]]
                for i in range(0, len(gpu_workers), 2)
            ]
            log.info(f"Determined head io node: {head_io_worker}")
            log.info(f"Head IO worker: {head_io_worker}")
            log.info(f"IO workers: {io_workers}")
            log.info(f"IO -> GPU worker map: {worker_map}")
            worker_map = {k: v for k, v in zip((io_workers), gpu_workers_divvied)}
