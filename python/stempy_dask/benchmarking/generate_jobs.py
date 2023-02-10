import asyncio
import copy
import json
import logging
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import aiohttp
import httpx
import jinja2
import tenacity
from aiopath import AsyncPath
from authlib.integrations.httpx_client.oauth2_client import AsyncOAuth2Client
from authlib.jose import JsonWebKey
from authlib.oauth2.rfc7523 import PrivateKeyJWT
from config import settings
from constants import COUNT_JOB_SCRIPT_TEMPLATE
from dotenv import dotenv_values
from schemas import JobUpdate
from schemas import Location as LocationRest
from schemas import Machine, Scan, ScanUpdate, SfapiJob
from utils import get_job
from utils import get_machine
from utils import get_machine as fetch_machine
from utils import get_machines as fetch_machines
from utils import get_scan
from utils import update_job as update_job_request
from utils import update_scan

# Cache to store machines, we only need to fetch them once
_machines = None


async def render_job_script(
    scan: Scan, job: Job, machine: Machine, dest_dir: str, machine_names: List[str]
) -> str:

    template_name = COUNT_JOB_SCRIPT_TEMPLATE
    template_loader = jinja2.FileSystemLoader(
        searchpath=Path(__file__).parent / "templates"
    )
    template_env = jinja2.Environment(loader=template_loader, enable_async=True)
    template = template_env.get_template(template_name)

    # Make a copy and filter out machines from locations
    scan = copy.deepcopy(scan)
    scan.locations = [x for x in scan.locations if x.host not in machine_names]

    try:
        output = await template.render_async(
            settings=settings,
            scan=scan,
            dest_dir=dest_dir,
            job=job,
            machine=machine,
            **job.params,
        )
    except:
        logger.exception("Exception rendering job script.")
        raise

    return output


async def submit_job(machine: str, batch_submit_file: str) -> int:
    data = {"job": batch_submit_file, "isPath": True}

    r = await sfapi_post(f"compute/jobs/{machine}", data)
    r.raise_for_status()

    sfapi_response = r.json()
    if sfapi_response["status"].lower() != "ok":
        raise SfApiError(sfapi_response["error"])

    task_id = sfapi_response["task_id"]

    # We now need to poll waiting for the task to complete!
    while True:
        r = await sfapi_get(f"tasks/{task_id}")
        r.raise_for_status()

        sfapi_response = r.json()

        if sfapi_response["status"].lower() == "error":
            raise SfApiError(sfapi_response["error"])

        logger.info(sfapi_response)

        if sfapi_response.get("result") is None:
            await asyncio.sleep(1)
            continue

        results = json.loads(sfapi_response["result"])

        if results["status"].lower() == "error":
            raise SfApiError(results["error"])

        slurm_id = results.get("jobid")
        if slurm_id is None:
            raise SfApiError(f"Unable to extract slurm job if for task: {task_id}")

        return int(slurm_id)
