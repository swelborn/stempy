import logging
import os

import dask
from dask.distributed import Client
from stempy_dask.utils import log as pretty_logger


def _determine_system():
    try:
        system = os.environ["NERSC_HOST"]
    except KeyError:
        system = "local"
        return system
    return system

# Determine whether in iPython, Jupyter, or in standard interpreter

def _determine_interpreter():
    """
    Checks if this is running within a jupyter notebook.
    """
    try:
        from IPython import get_ipython
        shell = get_ipython().__class__.__name__
    except ImportError or NameError:
        shell = "standard_interpreter"
        in_jupyter, in_ipython, in_standard = False, False, True
        return shell, (in_jupyter, in_ipython, in_standard)

    if shell == "ZMQInteractiveShell":
        shell = "jupyter"
        in_jupyter, in_ipython, in_standard = True, False, False
    elif shell == "TerminalInteractiveShell":
        shell = "ipython"
        in_jupyter, in_ipython, in_standard = False, True, False
    else:
        shell = "unknown"
        in_jupyter, in_ipython, in_standard = False, False, False
    return shell, (in_jupyter, in_ipython, in_standard)

system = _determine_system()
shell, (in_jupyter, in_ipython, in_standard) = _determine_interpreter()

sys_log = pretty_logger.create_logger("system")



# def _detect_jupyter_at_nersc():

sys_log.show()