import ctypes
import time

import numpy as np
np.set_printoptions(formatter={'int':hex})

from . import lib6502
from . import dtypes as d
from ..emulator_base import EmulatorBase

import logging
logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)


debug_frames = False


class Generic6502(EmulatorBase):
    cpu = "6502"
    name = "6502"
    pretty_name = "Generic 6502"

    mime_prefix = ""

    input_array_dtype = d.INPUT_DTYPE
    output_array_dtype = d.OUTPUT_DTYPE
    width = d.VIDEO_WIDTH
    height = d.VIDEO_HEIGHT

    low_level_interface = lib6502

    @property
    def current_cpu_status(self):
        pc, a, x, y, sp, p = self.cpu_state
        dtype = d.STATESAV_DTYPE
        state = self.state_array[0:int(d.STATESAV_DTYPE.itemsize)].view(dtype=d.STATESAV_DTYPE)[0]
        # print("raw: %s" % self.raw_array[0:32])
        return "A=%02x X=%02x Y=%02x SP=%02x FLAGS=%02x PC=%04x cyc=%ld instr=%ld" % (a, x, y, sp, p, pc, self.output['cycles_since_power_on'][0], self.output['instructions_since_power_on'][0])

    @property
    def stack_pointer(self):
        return self.cpu_state[4]

    @property
    def program_counter(self):
        return self.cpu_state[0]

    @program_counter.setter
    def program_counter(self, value):
        self.cpu_state[0] = value

    def generate_extra_segments(self):
        cpu_offset = self.state_start_offset
        memory_offset = cpu_offset + d.CPU_DTYPE.itemsize
        segments = [
            (cpu_offset, d.CPU_DTYPE.itemsize, 0, "CPU Status"),
            (memory_offset, d.MAIN_MEMORY_SIZE, 0, "Main Memory"),
        ]
        self.segments.extend(segments)

    def calc_cpu_data_array(self):
        offset = self.state_start_offset
        dtype = d.CPU_DTYPE
        raw = self.raw_array[offset:offset + dtype.itemsize]
        print(("sizeof raw_array=%d raw=%d dtype=%d" % (len(self.raw_array), len(raw), dtype.itemsize)))
        dataview = raw.view(dtype=dtype)
        return dataview[0]

    def calc_main_memory_array(self):
        offset = self.state_start_offset + d.CPU_DTYPE.itemsize
        raw = self.raw_array[offset:offset + d.MAIN_MEMORY_SIZE]
        return raw

    def boot_from_segment(self, segment):
        # for now, simply copies data into main memory
        start = segment.origin
        end = start + len(segment)
        log.debug(f"Copying {segment} to memory: {start:#04x}-{end:#04x}")
        self.main_memory[start:end] = segment.data
        self.cpu_state[0] = segment.origin
        lib6502.restore_state(self.output)
        self.debug_state()
        self.last_boot_state = self.calc_current_state()

    # Emulator user input functions

    def coldstart(self):
        """Simulate an initial power-on startup.
        """
        lib6502.start_emulator(None)
        if self.last_boot_state is not None:
            lib6502.restore_state(self.last_boot_state)

    def warmstart(self):
        """Simulate a warm start; i.e. pressing the system reset button
        """
        lib6502.start_emulator(None)
        if self.last_boot_state is not None:
            lib6502.restore_state(self.last_boot_state)

    def keypress(self, ascii_char):
        self.send_char(ord(ascii_char))

    # Utility functions

    def load_disk(self, drive_num, pathname):
        lib6502.load_disk(drive_num, pathname)
