import numpy as np

from .. import errors
from ..segment import Segment
from ..filesystem import VTOC, Dirent, Directory, Filesystem

try:  # Expensive debugging
    _xd = _expensive_debugging
except NameError:
    _xd = False


class AtariDosBootSegment(Segment):
    boot_record_type = np.dtype([
        ('BFLAG', 'u1'),
        ('BRCNT', 'u1'),
        ('BLDADR', '<u2'),
        ('BWTARR', '<u2'),
        ])

    def __init__(self, filesystem):
        media = filesystem.media
        size = self.find_segment_size(media)
        Segment.__init__(self, media, 0, self.bldadr, name="Boot Sectors", length=size)
        self.segments = self.calc_boot_segments()

    def find_segment_size(self, media):
        self.first_sector = media.get_contiguous_sectors(1)
        self.values = media[0:6].view(dtype=self.boot_record_type)[0]
        self.bflag = self.values['BFLAG']
        if self.bflag == 0:
            # possible boot sector
            self.brcnt = self.values['BRCNT']
            if self.brcnt == 0:
                self.brcnt = 3
        else:
            self.brcnt = 3
        self.bldadr = self.values['BLDADR']
        index, _ = media.get_index_of_sector(1 + self.brcnt)
        return index

    def calc_boot_segments(self):
        header = Segment(self, 0, self.bldadr, "Boot Header", length=6)
        code = Segment(self, 6, self.bldadr + 6, name="Boot Code", length=len(self) - 6)
        return [header, code]


class AtariDos2VTOC(VTOC):
    vtoc_type = np.dtype([
        ('code', 'u1'),
        ('total','<u2'),
        ('unused','<u2'),
        ])

    def find_segment_location(self):
        media = self.media
        values = media[0:5].view(dtype=self.vtoc_type)[0]
        code = values[0]
        if code == 0 or code == 2:
            num = 1
        else:
            num = (code * 2) - 3
        self.first_vtoc = 360 - num + 1
        if not media.is_sector_valid(self.first_vtoc):
            raise errors.FilesystemError(f"Invalid first VTOC sector {self.first_vtoc}")
        self.num_vtoc = num
        if num < 0 or num > self.calc_vtoc_code():
            raise errors.InvalidDiskImage(f"Invalid number of VTOC sectors: {num}")
        self.total_sectors = values[1]
        self.unused_sectors = values[2]
        return media.get_contiguous_sectors_offsets(self.first_vtoc, self.num_vtoc)

    def unpack_vtoc(self):
        bits = np.unpackbits(self[0x0a:0x64])
        self.sector_map[0:720] = bits
        if _xd: log.debug("vtoc before:\n%s" % str(self))

    def pack_vtoc(self):
        if _xd: log.debug("vtoc after:\n%s" % str(self))
        packed = np.packbits(self.sector_map[0:720])
        self[0x0a:0x64] = packed

    def calc_vtoc_code(self):
        # From AA post: http://atariage.com/forums/topic/179868-mydos-vtoc-size/
        media = self.filesystem.media
        num = 1 + (media.num_sectors + 80) // (media.sector_size * 8)
        if media.sector_size == 128:
            if num == 1:
                code = 2
            else:
                if num & 1:
                    num += 1
                code = ((num + 1) // 2) + 2
        else:
            if media.num_sectors < 1024:
                code = 2
            else:
                code = 2 + num
        return code


class AtariDosDirent(Dirent):
    # ATR Dirent structure described at http://atari.kensclassics.org/dos.htm
    format = np.dtype([
        ('FLAG', 'u1'),
        ('COUNT', '<u2'),
        ('START', '<u2'),
        ('NAME','S8'),
        ('EXT','S3'),
        ])

    def __init__(self, filesystem, parent, file_num, start):
        Dirent.__init__(self, filesystem, parent, file_num, start, 16)
        self.flag = 0
        self.opened_output = False
        self.dos_2 = False
        self.mydos = False
        self.is_dir = False
        self.locked = False
        self._in_use = False
        self.deleted = False
        self.num_sectors = 0
        self.starting_sector = 0
        self.basename = b''
        self.ext = b''
        self.is_sane = True
        self.current_sector = 0
        self.current_read = 0
        self.sectors_seen = None
        self.parse_raw_dirent()

    def __str__(self):
        return "File #%-2d (%s) %03d %-8s%-3s  %03d" % (self.file_num, self.summary, self.starting_sector, self.basename.decode("latin1"), self.ext.decode("latin1"), self.num_sectors)

    def __eq__(self, other):
        return self.__class__ == other.__class__ and self.filename == other.filename and self.starting_sector == other.starting_sector and self.num_sectors == other.num_sectors

    @property
    def in_use(self):
        return self._in_use

    @property
    def filename(self):
        ext = (b'.' + self.ext) if self.ext else b''
        return (self.basename + ext).decode('latin1')

    @property
    def summary(self):
        output = "o" if self.opened_output else "."
        dos2 = "2" if self.dos_2 else "."
        mydos = "m" if self.mydos else "."
        in_use = "u" if self._in_use else "."
        deleted = "d" if self.deleted else "."
        locked = "*" if self.locked else " "
        flags = "%s%s%s%s%s%s" % (output, dos2, mydos, in_use, deleted, locked)
        return flags

    @property
    def verbose_info(self):
        flags = []
        if self.opened_output: flags.append("OUT")
        if self.dos_2: flags.append("DOS2")
        if self.mydos: flags.append("MYDOS")
        if self._in_use: flags.append("IN_USE")
        if self.deleted: flags.append("DEL")
        if self.locked: flags.append("LOCK")
        return "flags=[%s]" % ", ".join(flags)

    def extra_metadata(self, image):
        return self.verbose_info

    def parse_raw_dirent(self):
        data = self.data[0:16]
        values = data.view(dtype=self.format)[0]
        flag = values[0]
        self.flag = flag
        self.opened_output = (flag&0x01) > 0
        self.dos_2 = (flag&0x02) > 0
        self.mydos = (flag&0x04) > 0
        self.is_dir = (flag&0x10) > 0
        self.locked = (flag&0x20) > 0
        self._in_use = (flag&0x40) > 0
        self.deleted = (flag&0x80) > 0
        self.num_sectors = int(values[1])
        self.starting_sector = int(values[2])
        self.basename = bytes(values[3]).rstrip()
        self.ext = bytes(values[4]).rstrip()
        self.is_sane = self.sanity_check()

    def encode_dirent(self):
        data = np.zeros([self.format.itemsize], dtype=np.uint8)
        values = data.view(dtype=self.format)[0]
        flag = (1 * int(self.opened_output)) | (2 * int(self.dos_2)) | (4 * int(self.mydos)) | (0x10 * int(self.is_dir)) | (0x20 * int(self.locked)) | (0x40 * int(self._in_use)) | (0x80 * int(self.deleted))
        values[0] = flag
        values[1] = self.num_sectors
        values[2] = self.starting_sector
        values[3] = self.basename
        values[4] = self.ext
        return data

    def mark_deleted(self):
        self.deleted = True
        self._in_use = False

    def update_sector_info(self, sector_list):
        self.num_sectors = sector_list.num_sectors
        self.starting_sector = sector_list.first_sector

    def add_metadata_sectors(self, vtoc, sector_list, header):
        # no extra sectors are needed for an Atari DOS file; the links to the
        # next sector is contained in the sector.
        pass

    def sanity_check(self):
        media = self.filesystem.media
        if not self._in_use:
            return True
        if not media.is_sector_valid(self.starting_sector):
            return False
        if self.num_sectors < 0 or self.num_sectors > media.num_sectors:
            return False
        return True

    def get_sectors_in_vtoc(self, image):
        sector_list = BaseSectorList(image.header)
        self.start_read(image)
        while True:
            sector = WriteableSector(image.header.sector_size, None, self.current_sector)
            sector_list.append(sector)
            _, last, _, _ = self.read_sector(image)
            if last:
                break
        return sector_list

    def start_read(self, image):
        if not self.is_sane:
            raise errors.InvalidDirent("Invalid directory entry '%s'" % str(self))
        self.current_sector = self.starting_sector
        self.current_read = self.num_sectors
        self.sectors_seen = set()

    def read_sector(self, image):
        raw, pos, size = image.get_raw_bytes(self.current_sector)
        bytes, num_data_bytes = self.process_raw_sector(image, raw)
        return bytes, self.current_sector == 0, pos, num_data_bytes

    def process_raw_sector(self, image, raw):
        file_num = raw[-3] >> 2
        if file_num != self.file_num:
            raise errors.FileNumberMismatchError164("Expecting file %d, found %d" % (self.file_num, file_num))
        self.sectors_seen.add(self.current_sector)
        next_sector = ((raw[-3] & 0x3) << 8) + raw[-2]
        if next_sector in self.sectors_seen:
            raise errors.InvalidFile("Bad sector pointer data: attempting to reread sector %d" % next_sector)
        self.current_sector = next_sector
        num_bytes = raw[-1]
        return raw[0:num_bytes], num_bytes

    def set_values(self, filename, filetype, index):
        if type(filename) is not bytes:
            filename = filename.encode("latin1")
        if b'.' in filename:
            filename, ext = filename.split(b'.', 1)
        else:
            ext = b'   '
        self.basename = b'%-8s' % filename[0:8]
        self.ext = ext
        self.file_num = index
        self.dos_2 = True
        self._in_use = True
        if _xd: log.debug("set_values: %s" % self)


class AtariDos2Directory(Directory):
    def __init__(self, filesystem):
        self.filesystem = filesystem
        offset, length = self.find_segment_location()
        Segment.__init__(self, filesystem.media, offset, name="Directory", length=length)

        # Each segment is a dirent
        self.segments = self.calc_dirents()

    def find_segment_location(self):
        media = self.media
        if media.is_sector_valid(361):
            return media.get_contiguous_sectors_offsets(361, 8)
        else:
            raise errors.FilesystemError("Disk image too small to contain a directory")

    def calc_dirents(self):
        segments = []
        index = 0
        for filenum in range(64):
            dirent = AtariDosDirent(self.filesystem, self, filenum, index)
            if not dirent.in_use:
                continue
            dirent.set_comment_at(0x00, "FILE #%d: Flag" % filenum)
            dirent.set_comment_at(0x01, "FILE #%d: Number of sectors in file" % filenum)
            dirent.set_comment_at(0x03, "FILE #%d: Starting sector number" % filenum)
            dirent.set_comment_at(0x05, "FILE #%d: Filename" % filenum)
            dirent.set_comment_at(0x0d, "FILE #%d: Extension" % filenum)
            index += 16
            segments.append(dirent)
        return segments


class AtariDos2(Filesystem):
    default_executable_extension = "XEX"

    def check_media(self, media):
        try:
            media.get_contiguous_sectors
        except AttributeError:
            raise errors.IncompatibleMediaError("Atari DOS needs sector access")

    def calc_boot_segment(self):
        return AtariDosBootSegment(self)

    def calc_vtoc_segment(self):
        return AtariDos2VTOC(self)

    def calc_directory_segment(self):
        return AtariDos2Directory(self)
