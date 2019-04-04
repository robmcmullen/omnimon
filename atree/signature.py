import pkg_resources

import numpy as np

import logging
log = logging.getLogger(__name__)


_signatures = None

def _find_signatures():
    signatures = []
    for entry_point in pkg_resources.iter_entry_points('atree.signatures'):
        mod = entry_point.load()
        log.debug(f"find_signatures: Found module {entry_point.name}={mod.__name__}")
        if hasattr(mod, "sha1_signatures"):
            if hasattr(mod, "mime"):
                log.debug(f"find_signatures:  found signature class {mod.__name__} for {mod.mime}")
            else:
                log.warning(f"find_signatures:  unspecified MIME type for signature class {mod.__name__}")
                mod.mime = "application/octet-stream"
            signatures.append(mod)
    return signatures

def find_signatures():
    global _signatures

    if _signatures is None:
        _signatures = _find_signatures()
    return _signatures


class Signature:
    def __init__(self, mime, name):
        self.mime = mime
        self.name = name

    def __str__(self):
        return f"{self.mime}: {self.name}"


def guess_signature_by_size(container, verbose=False):
    found = None
    size = len(container)
    sha_hash = container.sha1
    log.debug(f"container: {container}; sha1={sha_hash}")
    for mod in find_signatures():
        if size in mod.sha1_signatures:
            log.debug(f"size {size} in signature database {mod.__name__}")
            try:
                name = mod.sha1_signatures[size][sha_hash]
            except KeyError:
                continue
            else:
                log.debug(f"found match: {name}")
                return Signature(mod.mime, name)
        else:
            log.debug(f"size {size} not in signature database {mod.__name__}; skipping")
    else:
        log.debug(f"{size} not found in signature database; skipping sha1 matching")
    return None


# different than the above mime_parse_order, this list is the order in which
# the mime parsers will appear in a UI. Some, like the vectrex and atari2600
# parsers, aren't included in the parse order because they will identify
# many things incorrectly. They are used only when parsing by size and
# signature.
mime_display_order = [
    "application/vnd.atari8bit.atr",
    "application/vnd.atari8bit.xex",
    "application/vnd.atari8bit.cart",
    "application/vnd.atari5200.cart",
    "application/vnd.atari2600.cart",
    "application/vnd.atari2600.starpath",
    "application/vnd.vectrex",
    "application/vnd.mame_rom",
    "application/vnd.apple2.dsk",
    "application/vnd.apple2.bin",
    "application/vnd.rom",
    ]

pretty_mime = {
    "application/vnd.atari8bit.atr": "Atari 8-bit Disk Image",
    "application/vnd.atari8bit.xex": "Atari 8-bit Executable",
    "application/vnd.atari8bit.cart": "Atari 8-bit Cartridge",
    "application/vnd.atari5200.cart": "Atari 5200 Cartridge",
    "application/vnd.atari2600.cart": "Atari 2600 Cartridge",
    "application/vnd.atari2600.starpath": "Atari 2600 Starpath Cassette",
    "application/vnd.vectrex": "GCE Vectrex Cartridge",
    "application/vnd.mame_rom": "MAME",
    "application/vnd.rom": "ROM Image",
    "application/vnd.apple2.dsk": "Apple ][ Disk Image",
    "application/vnd.apple2.bin": "Apple ][ Binary",
}
