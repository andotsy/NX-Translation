#!/usr/bin/env python3
"""Compare the existing translation's structure with verified firmware inputs."""
import json
from pathlib import Path
import struct
from port_config import WORK, OLD_CONTENTS

ROOT = WORK
OLD = OLD_CONTENTS
NEW = ROOT / 'firmware-23.0.1-resources'


def decompress(data):
    if data[:4] != b'Yaz0':
        return data
    size = int.from_bytes(data[4:8], 'big')
    out = bytearray()
    pos = 16
    while len(out) < size:
        code = data[pos]
        pos += 1
        for bit in range(7, -1, -1):
            if len(out) == size:
                break
            if code & (1 << bit):
                out.append(data[pos])
                pos += 1
            else:
                a, b = data[pos:pos + 2]
                pos += 2
                distance = ((a & 15) << 8 | b) + 1
                length = a >> 4
                if not length:
                    length = data[pos] + 18
                    pos += 1
                else:
                    length += 2
                assert distance <= len(out)
                for _ in range(length):
                    out.append(out[-distance])
    assert len(out) == size
    return bytes(out)


def parse(data):
    data = decompress(data)
    assert data[:8] == b'MsgStdBn'
    endian = '<' if data[8:10] == b'\xff\xfe' else '>'
    u32 = lambda b, p: struct.unpack_from(endian + 'I', b, p)[0]
    assert u32(data, 18) == len(data)
    section_count = struct.unpack_from(endian + 'H', data, 14)[0]
    pos = 32
    sections = {}
    for _ in range(section_count):
        tag = data[pos:pos + 4].decode('ascii')
        size = u32(data, pos + 4)
        sections[tag] = data[pos + 16:pos + 16 + size]
        pos = (pos + 16 + size + 15) // 16 * 16
    labels = {}
    b = sections['LBL1']
    for bucket in range(u32(b, 0)):
        count, offset = struct.unpack_from(endian + 'II', b, 4 + 8 * bucket)
        for _ in range(count):
            length = b[offset]
            offset += 1
            label = b[offset:offset + length].decode('utf-8')
            offset += length
            index = u32(b, offset)
            offset += 4
            assert label not in labels
            labels[label] = index
    b = sections['TXT2']
    count = u32(b, 0)
    offsets = [u32(b, 4 + 4 * n) for n in range(count)]
    messages = [b[start:(offsets[n + 1] if n + 1 < count else len(b))]
                for n, start in enumerate(offsets)]
    assert all(index < count for index in labels.values())
    return {'endian': endian, 'encoding': data[12], 'version': data[13],
            'sections': sections, 'labels': labels, 'count': count, 'messages': messages}


def main():
    rows = []
    old_paths = set()
    for old_file in sorted(OLD.rglob('*')):
        if not old_file.is_file():
            continue
        relative = old_file.relative_to(OLD)
        title = relative.parts[0].lower()
        path = Path(*relative.parts[2:])
        if 'EUru' not in path.parts:
            continue
        old_paths.add((title, str(path)))
        new_file = NEW / title / path
        assert new_file.is_file(), 'Old translation path missing in 23.0.1: ' + str(relative)
        old, new = parse(old_file.read_bytes()), parse(new_file.read_bytes())
        added = sorted(set(new['labels']) - set(old['labels']))
        removed = sorted(set(old['labels']) - set(new['labels']))
        common = set(new['labels']) & set(old['labels'])
        moved = sorted(label for label in common if new['labels'][label] != old['labels'][label])
        row = {'title_id': title, 'path': str(path), 'old_messages': old['count'],
               'new_messages': new['count'], 'added_labels': added, 'removed_labels': removed,
               'reindexed_labels': moved,
               'format_equal': all(old[k] == new[k] for k in ['endian', 'encoding', 'version']),
               'section_names_equal': list(old['sections']) == list(new['sections']),
               'unchanged_nontext_sections': {k: old['sections'][k] == new['sections'].get(k)
                                             for k in old['sections'] if k != 'TXT2'}}
        rows.append(row)
    assert len(rows) == 51
    extras = []
    all_new = []
    for p in sorted(NEW.rglob('*')):
        if not p.is_file():
            continue
        relative = p.relative_to(NEW)
        if 'EUru' not in relative.parts:
            continue
        data = decompress(p.read_bytes())
        parsed = parse(data) if data[:8] == b'MsgStdBn' else None
        assert parsed is not None or data[:8] == b'MsgPrjBn', 'Unknown language resource format'
        row = {'title_id': relative.parts[0], 'path': str(Path(*relative.parts[1:])),
               'messages': parsed['count'] if parsed else None,
               'format': 'MSBT' if parsed else 'MSBP'}
        all_new.append(row)
        if (row['title_id'], row['path']) not in old_paths:
            extras.append(row)
    summary = {'old_files': len(rows), 'current_russian_files': len(all_new),
               'files_with_label_changes': sum(bool(r['added_labels'] or r['removed_labels']) for r in rows),
               'files_with_reindexed_labels': sum(bool(r['reindexed_labels']) for r in rows),
               'files_with_changed_nontext_sections': sum(not all(r['unchanged_nontext_sections'].values()) for r in rows),
               'added_labels': sum(len(r['added_labels']) for r in rows),
               'removed_labels': sum(len(r['removed_labels']) for r in rows),
               'additional_russian_resources': extras,
               'all_current_message_resources_parse': True}
    (ROOT / 'message-compatibility-comparison.json').write_text(json.dumps({'summary': summary, 'files': rows}, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
    for row in rows:
        if row['added_labels'] or row['removed_labels'] or not all(row['unchanged_nontext_sections'].values()):
            print(row['title_id'], row['path'], 'added', len(row['added_labels']),
                  'removed', len(row['removed_labels']), 'nontext', row['unchanged_nontext_sections'])


if __name__ == '__main__':
    main()
