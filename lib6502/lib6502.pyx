import numpy as np
cimport numpy as np

cdef extern:
    int lib6502_init_cpu(float, float)
    int lib6502_clear_state_arrays(np.uint8_t *buf, np.uint8_t *buf)
    int lib6502_configure_state_arrays(np.uint8_t *buf, np.uint8_t *buf)
    int lib6502_next_frame(np.uint8_t *buf, np.uint8_t *buf, np.uint8_t *buf)
    void lib6502_get_current_state(np.uint8_t *buf)
    void lib6502_restore_state(np.uint8_t *buf)

def start_emulator(args):
    lib6502_init_cpu(1.023, 60.0)  # apple 2 speed

def clear_state_arrays(np.ndarray input not None, np.ndarray output not None):
    cdef np.uint8_t[:] ibuf
    cdef np.uint8_t[:] obuf

    ibuf = input.view(np.uint8)
    obuf = output.view(np.uint8)
    lib6502_clear_state_arrays(&ibuf[0], &obuf[0])

def configure_state_arrays(np.ndarray input not None, np.ndarray output not None):
    cdef np.uint8_t[:] ibuf
    cdef np.uint8_t[:] obuf

    ibuf = input.view(np.uint8)
    obuf = output.view(np.uint8)
    lib6502_configure_state_arrays(&ibuf[0], &obuf[0])

def next_frame(np.ndarray input not None, np.ndarray output not None, np.ndarray breakpoints not None):
    cdef np.uint8_t[:] ibuf  # ignored for this emulator
    cdef np.uint8_t[:] obuf
    cdef np.uint8_t[:] dbuf

    ibuf = input.view(np.uint8)
    obuf = output.view(np.uint8)
    dbuf = breakpoints.view(np.uint8)
    bpid = lib6502_next_frame(&ibuf[0], &obuf[0], &dbuf[0])
    return bpid

def get_current_state(np.ndarray output not None):
    cdef np.uint8_t[:] obuf

    obuf = output.view(np.uint8)
    lib6502_get_current_state(&obuf[0])

def load_disk(int disknum, char *filename, int readonly=0):
    raise NotImplementedError

def restore_state(np.ndarray state not None):
    cdef np.uint8_t[:] sbuf
    sbuf = state.view(np.uint8)
    lib6502_restore_state(&sbuf[0])
