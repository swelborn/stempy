
Running on Jupyter at NERSC
==================

The Docker containers under the ``/docker`` folder in the stempy repository are built with each new 
commit and can be found `here <https://hub.docker.com/u/openchemistry/>`_. 
You can follow the instructions below to pull these images for use as a stempy environment at NERSC.

You should review the `NERSC documentation 
<https://docs.nersc.gov/development/shifter/shifter-tutorial/>`_ for more information 
regarding shifter.

Pulling the latest image
------------------------

Login to NERSC and use the following command to pull the latest image from dockerhub:

``shifter pull openchemistry/stempy:latest``

Note
####

Since this is the latest image, it is subject to change whenever one makes a commit on the repository.
If you would like to use a more stable version, use a more stable tag e.g.:

``shifter pull openchemistry/stempy:3.2.1``


Creating a Jupyter Kernel
-------------------------

The shifter image that you pulled above is now available, but you have to get at it through
your Jupyter at NERSC instance. To do this, you will have to create a custom Jupyter kernel. 
NERSC documentation on Jupyter kernels can be found 
`here <https://docs.nersc.gov/services/jupyter/#shifter-kernels-on-jupyter>`_.
We can use the python executable in the container's conda environment instead of:
``/opt/conda/bin/python``. 

There is a bit of a trick to this that is not (currently) in the NERSC documentation. Create a subfolder
in ``$HOME/.local/share/jupyter/kernel`` with the name of the kernel (e.g., stempy). 
Then, make a kernel.json file:

.. code-block::

    {
        "argv": [
            "shifter",
            "--image=openchemistry/stempy:latest",
            "{resource_dir}/kernel_helper.sh",
            "{connection_file}"
        ],
        "display_name": "stempy",
        "language": "python"
    }

The ``kernel_helper.sh`` script should be in the same directory (the resource_dir):

.. code-block::

    #! /bin/bash
    source /opt/miniconda3/etc/profile.d/conda.sh
    conda activate stempy
    python -m ipykernel_launcher -f $1
    exec "$@"

Once the kernel has been created, you can access stempy by logging into a Jupyter at NERSC instance
(`link <jupyter.nersc.gov>`_), starting a notebook, and using the kernel listed under kernels.