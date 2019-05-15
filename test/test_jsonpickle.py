from __future__ import print_function
from builtins import zip
from builtins import range
from builtins import object
import os

import pytest
jsonpickle = pytest.importorskip("jsonpickle")

import numpy as np

from atrip import Container, Segment


class TestJsonPickle:
    def setup(self):
        data = np.arange(4096, dtype=np.uint8)
        data[1::2] = np.repeat(np.arange(16, dtype=np.uint8), 128)
        data[::100] = 0x7f
        self.container = Container(data)
        self.container.disasm_type[100:200] = 10
        self.container.disasm_type[200:300] = 30
        self.container.disasm_type[1200:3000] = 10
        self.segment = Segment(self.container)
        index_by_100 = np.arange(40, dtype=np.int32) * 100
        self.seg100 = Segment(self.segment, index_by_100)
        self.seg1000 = Segment(self.seg100, [0,10,20,30])

    def test_simple(self):
        j = jsonpickle.dumps(self.container)
        print(j)
        
        c = jsonpickle.loads(j)
        j2 = jsonpickle.dumps(c)
        print(j2)

        assert j == j2

if __name__ == "__main__":
    t = TestJsonPickle()
    t.setup()
    t.test_simple()
