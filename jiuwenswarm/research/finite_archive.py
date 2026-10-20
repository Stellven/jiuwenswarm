"""Bounded validation of opaque original ZIP bytes, without member imports.

This adapter returns usage only. It creates no paths, Refs, records, permissions
or execution authority. Protected qualification owns all custody and budgets.
"""
from __future__ import annotations

import binascii
import io
import stat
import struct
import unicodedata
import zipfile
import zlib

from .contracts import ResearchError


def _require(condition, message):
    if not condition:
        raise ResearchError('finite_fixture', message)


def _member_path(info):
    name = info.orig_filename
    _require(name == info.filename and bool(name) and '\\' not in name
             and ':' not in name and not name.startswith('/')
             and all(not unicodedata.category(char).startswith('C') for char in name),
             'Archive member path is not a safe relative original')
    parts = name.split('/')
    _require(all(part not in {'', '.', '..'} for part in parts),
             'Archive member path has an empty, dot or parent component')
    mode = stat.S_IFMT(info.external_attr >> 16)
    _require(not info.is_dir() and not (info.external_attr & 0x10)
             and mode in {0, stat.S_IFREG},
             'Archive directories, links and special members are unsupported')
    return tuple(unicodedata.normalize('NFC', part).casefold() for part in parts)


def _bounded_directory(raw, max_members):
    # Bound cardinality before ZipFile allocates its complete metadata index.
    # The only scan window is ZIP's fixed EOCD plus its uint16 comment length.
    end = raw.rfind(b'PK\x05\x06', max(0, len(raw) - 65557))
    _require(end >= 0 and end + 22 <= len(raw), 'Archive end directory is absent')
    _, disk, directory_disk, disk_count, count, size, offset, comment = struct.unpack_from('<4s4H2IH',raw,end)
    _require(end + 22 + comment == len(raw), 'Archive end directory/comment length differs')
    if disk or directory_disk or disk_count != count:
        raise ResearchError('unavailable', 'Finite opaque multidisk ZIP adapter is unavailable')
    if (count == 65535 or size == 0xffffffff or offset == 0xffffffff
            or (end >= 20 and raw[end-20:end-16] == b'PK\x06\x07')):
        raise ResearchError('unavailable', 'Finite opaque ZIP64 adapter is unavailable')
    _require(count <= max_members, 'Archive member count exceeds protected case budget')
    start = end - size
    _require(0 <= offset <= start <= end, 'Archive central directory range differs')
    cursor, actual = start, 0
    while cursor < end:
        _require(cursor + 46 <= end and raw[cursor:cursor+4] == b'PK\x01\x02',
                 'Archive central directory has an invalid member record')
        filename, extra, member_comment, member_disk = struct.unpack_from('<4H',raw,cursor+28)
        if member_disk:
            raise ResearchError('unavailable', 'Finite opaque multidisk ZIP adapter is unavailable')
        compressed, inflated = struct.unpack_from('<2I',raw,cursor+20)
        local_offset = struct.unpack_from('<I',raw,cursor+42)[0]
        if 0xffffffff in {compressed,inflated,local_offset}:
            raise ResearchError('unavailable', 'Finite opaque ZIP64 adapter is unavailable')
        actual += 1
        _require(actual <= max_members and actual <= count,
                 'Archive actual directory count exceeds declared or protected bound')
        cursor += 46 + filename + extra + member_comment
        _require(cursor <= end, 'Archive central member metadata exceeds directory bounds')
    _require(cursor == end and actual == count, 'Archive actual and declared directory counts differ')


def _compressed_member(archive, info, raw):
    # ZipFile.open independently checks the original local name, unsupported
    # flags and overlap with the next member/directory. No decoder read occurs.
    with archive.open(info, 'r'):
        pass
    header = struct.unpack_from('<4s5H3I2H', raw, info.header_offset)
    signature, _, flags, method, _, _, crc, compressed, size, name_len, extra_len = header
    _require(signature == b'PK\x03\x04' and flags == info.flag_bits
             and method == info.compress_type, 'Archive local and indexed metadata differ')
    if not flags & 8:  # A data descriptor may own these values instead.
        _require(crc == info.CRC and compressed in {info.compress_size, 0xffffffff}
                 and size in {info.file_size, 0xffffffff},
                 'Archive local and indexed content lengths or CRC differ')
    start = info.header_offset + 30 + name_len + extra_len
    end = start + info.compress_size
    _require(0 <= start <= end <= len(raw), 'Archive member bytes exceed original custody')
    return memoryview(raw)[start:end]


def _validate_content(info, compressed):
    actual, crc = 0, 0

    def consume(chunk):
        nonlocal actual, crc
        actual += len(chunk)
        _require(actual <= info.file_size, 'Archive inflated bytes exceed the original declared size')
        crc = binascii.crc32(chunk, crc)

    if info.compress_type == zipfile.ZIP_STORED:
        _require(len(compressed) == info.file_size, 'Stored archive member length differs')
        for offset in range(0, len(compressed), 65536):
            consume(compressed[offset:offset + 65536])
    else:
        decoder = zlib.decompressobj(-15)
        for offset in range(0, len(compressed), 65536):
            pending = compressed[offset:offset + 65536]
            _require(not decoder.eof, 'Archive compressed member has trailing bytes')
            while pending:
                # The original size has already passed every protected limit.
                # One extra output byte detects dishonest underreported sizes;
                # advertised size never clips the actual validation stream.
                consume(decoder.decompress(pending, min(65536, info.file_size - actual + 1)))
                pending = decoder.unconsumed_tail
                _require(not decoder.unused_data, 'Archive compressed member has trailing bytes')
        consume(decoder.decompress(b'', min(65536, info.file_size - actual + 1)))
        _require(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,
                 'Archive compressed member is incomplete or has trailing content')
    _require(actual == info.file_size and (crc & 0xffffffff) == info.CRC,
             'Archive actual content length or CRC differs from the original index')
    return actual


def validate_opaque_zip(raw, *, max_members, max_member_bytes,
                        max_uncompressed_bytes, max_total_bytes):
    """Validate exact bytes and return (member count, actual inflated bytes).

    Limits are explicit remaining protected budgets. Supported codecs are stored
    and raw DEFLATE; a different codec is unavailable, never silently accepted.
    """
    _require(type(raw) is bytes, 'Archive original must be captured bytes')
    _require(all(type(value) is int and value >= 0 for value in (
        max_members, max_member_bytes, max_uncompressed_bytes, max_total_bytes)),
        'Archive validation needs explicit nonnegative remaining bounds')
    try:
        _bounded_directory(raw, max_members)
        with zipfile.ZipFile(io.BytesIO(raw), 'r') as archive:
            members = archive.infolist()
            _require(len(members) <= max_members, 'Archive member count exceeds protected case budget')
            names, parents = set(), set()
            declared = 0
            for info in members:
                name = _member_path(info)
                prefixes = {name[:length] for length in range(1, len(name))}
                _require(name not in names and name not in parents and not (prefixes & names),
                         'Archive member tree has duplicate, case or file/descendant conflicts')
                names.add(name)
                parents.update(prefixes)
                _require(not (info.flag_bits & (1 | 32 | 64 | 8192)),
                         'Encrypted or patched archive members are unsupported')
                if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                    raise ResearchError('unavailable', 'Finite opaque ZIP codec adapter is unavailable')
                _require(0 <= info.file_size <= max_member_bytes and info.compress_size >= 0,
                         'Archive member advertised size exceeds protected bound')
                declared += info.file_size
                _require(declared <= max_uncompressed_bytes and declared <= max_total_bytes,
                         'Archive advertised inflated bytes exceed protected case budget')
            actual = sum(_validate_content(info, _compressed_member(archive, info, raw)) for info in members)
            _require(actual == declared and actual <= max_uncompressed_bytes and actual <= max_total_bytes,
                     'Archive actual inflated bytes exceed protected case budget')
            return len(members), actual
    except ResearchError:
        raise
    except NotImplementedError as error:
        raise ResearchError('unavailable', 'Finite opaque ZIP feature adapter is unavailable') from error
    except (zipfile.BadZipFile, RuntimeError, EOFError, ValueError, UnicodeError,
            struct.error, zlib.error, OverflowError) as error:
        raise ResearchError('finite_fixture', 'Original archive is malformed or fails bounded content validation') from error
