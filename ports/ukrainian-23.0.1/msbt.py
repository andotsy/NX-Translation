"""Conservative UTF-16LE MSBT editing: preserve every non-TXT2 byte."""
from dataclasses import dataclass
import struct
from compare_resources import decompress


@dataclass
class Section:
    tag: str
    header: bytes
    body: bytes
    padding: bytes


def tokens(message):
    """Return literal UTF-16 text and opaque, length-delimited control commands."""
    result = []
    pos = 0
    start = 0
    while pos < len(message):
        assert pos + 2 <= len(message)
        code = struct.unpack_from('<H', message, pos)[0]
        if code not in (0, 0x0E, 0x0F):
            pos += 2
            continue
        if pos > start:
            result.append(('text', message[start:pos].decode('utf-16-le')))
        if code == 0:
            assert pos + 2 == len(message), ('Unexpected data after terminator', message[pos:])
            return result
        size = 6
        if code == 0x0E:
            assert pos + 8 <= len(message)
            size = 8 + struct.unpack_from('<H', message, pos + 6)[0]
        assert pos + size <= len(message)
        result.append(('command', message[pos:pos + size]))
        pos += size
        start = pos
    raise AssertionError('Missing string terminator')


def commands(message):
    return [v for k, v in tokens(message) if k == 'command']


def text(message):
    return ''.join(v for k, v in tokens(message) if k == 'text')


class Msbt:
    def __init__(self, original):
        self.data = decompress(original)
        assert self.data[:8] == b'MsgStdBn' and self.data[8:10] == b'\xff\xfe'
        assert self.data[12:14] == b'\x01\x03'
        assert struct.unpack_from('<I', self.data, 18)[0] == len(self.data)
        count = struct.unpack_from('<H', self.data, 14)[0]
        self.header = self.data[:32]
        self.sections = []
        pos = 32
        for _ in range(count):
            size = struct.unpack_from('<I', self.data, pos + 4)[0]
            end = pos + 16 + size
            aligned = (end + 15) // 16 * 16
            self.sections.append(Section(self.data[pos:pos + 4].decode('ascii'),
                                         self.data[pos:pos + 16], self.data[pos + 16:end],
                                         self.data[end:aligned]))
            pos = aligned
        assert pos == len(self.data)
        self.by_tag = {s.tag: s for s in self.sections}
        assert len(self.by_tag) == len(self.sections)
        lbl = self.by_tag['LBL1'].body
        self.labels = {}
        for bucket in range(struct.unpack_from('<I', lbl)[0]):
            count, off = struct.unpack_from('<II', lbl, 4 + bucket * 8)
            for _ in range(count):
                length = lbl[off]
                off += 1
                label = lbl[off:off + length].decode('utf-8')
                off += length
                index = struct.unpack_from('<I', lbl, off)[0]
                off += 4
                assert label not in self.labels
                self.labels[label] = index
        body = self.by_tag['TXT2'].body
        count = struct.unpack_from('<I', body)[0]
        offsets = list(struct.unpack_from('<' + 'I' * count, body, 4))
        assert offsets[0] == 4 + 4 * count
        assert offsets == sorted(offsets)
        self.messages = [body[off:(offsets[i + 1] if i + 1 < count else len(body))]
                         for i, off in enumerate(offsets)]
        assert all(i < count for i in self.labels.values())
        for message in self.messages:
            tokens(message)

    def build(self, messages):
        assert len(messages) == len(self.messages)
        for message in messages:
            tokens(message)
        body = bytearray(struct.pack('<I', len(messages)))
        offset = 4 + 4 * len(messages)
        for message in messages:
            body += struct.pack('<I', offset)
            offset += len(message)
        body += b''.join(messages)
        out = bytearray(self.header)
        for section in self.sections:
            if section.tag != 'TXT2':
                out += section.header + section.body + section.padding
                continue
            header = bytearray(section.header)
            struct.pack_into('<I', header, 4, len(body))
            out += header + body
            pad = (-len(out)) % 16
            if pad == len(section.padding):
                out += section.padding
            else:
                assert len(set(section.padding)) <= 1
                fill = section.padding[:1] or b'\xab'
                out += fill * pad
        struct.pack_into('<I', out, 18, len(out))
        result = Msbt(bytes(out))
        assert result.labels == self.labels
        for section in self.sections:
            if section.tag != 'TXT2':
                assert result.by_tag[section.tag] == section
        assert result.messages == messages
        return bytes(out)
