# Insert path to shared object to import stempy._io._block
import copyreg
import sys

import numpy as np
import stempy._io
from distributed.protocol import register_generic


class DBlock:
    def __init__(self, header, data):
        self.header = header
        self.data = data


def pickle_block(b):
    return DBlock, (b.header, np.array(b, copy=False))


copyreg.pickle(stempy._io._block, pickle_block)
register_generic(DBlock)
