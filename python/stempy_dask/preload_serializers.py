# Insert path to shared object to import stempy._io._block
import copyreg
import sys

sys.path.append("/source/stempy/python/")

import numpy as np
from distributed.protocol import register_generic

import stempy._io


class DBlock:
    def __init__(self, header, data):
        self.header = header
        self.data = data


def pickle_block(b):
    return DBlock, (b.header, np.array(b, copy=False))


copyreg.pickle(stempy._io._block, pickle_block)
register_generic(DBlock)
