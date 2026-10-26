#!/usr/bin/env python3
"""Use Ukrainian in the Russian slot and Cyrillic Russian in its Latin slot."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

BUILD_ID = '62e9dc6da6f75b55948d32ca41e07d36f8f2bb09'
INPUT_SHA256 = 'f57bcdfe2d1cf9ce925f11aa101b9884d1608348334dc3cff2cf8d9fefa444a2'
TABLES = {
    0x44f550: '1234567890ъйцукенгшщзхфывапролджэячсмитьбюё.',
    0x44f5a8: '!?":;()-_@ЪЙЦУКЕНГШЩЗХФЫВАПРОЛДЖЭЯЧСМИТЬБЮЁ,',
}
REPLACE = dict(zip('ъыэёЪЫЭЁ', 'їієґЇІЄҐ'))
SECONDARY_TABLES = {
    0x44f658: ('1234567890-qwertyuiop/asdfghjkl:\'zxcvbnm,.?!', TABLES[0x44f550]),
    0x44f6b0: ('#£€$%^&*()_QWERTYUIOP@ASDFGHJKL;"ZXCVBNM<>+=', TABLES[0x44f5a8]),
}


def build(data):
    if data[:4] != b'NSO0' or data[0x40:0x60].rstrip(b'\0').hex() != BUILD_ID:
        raise ValueError('Unsupported keyboard build ID')
    if hashlib.sha256(data).hexdigest() != INPUT_SHA256:
        raise ValueError('Expected the exact uncompressed, unmodified keyboard NSO')
    if struct.unpack_from('<I', data, 0xc)[0] & 7:
        raise ValueError('Input must be uncompressed')
    ro_file, _, ro_size = struct.unpack_from('<III', data, 0x20)
    patch = bytearray(b'PATCH')
    changes = []
    for offset, expected in TABLES.items():
        raw = expected.encode('utf-16-le')
        if not ro_file <= offset < offset + len(raw) <= ro_file + ro_size:
            raise ValueError('Keyboard table is outside read-only data')
        if data[offset:offset + len(raw)] != raw:
            raise ValueError('Unexpected Russian keyboard table')
        for index, source in enumerate(expected):
            if source not in REPLACE:
                continue
            target = REPLACE[source]
            position = offset + index * 2
            patch += position.to_bytes(3, 'big') + b'\x00\x02' + target.encode('utf-16-le')
            changes.append({'offset': position, 'from': source, 'to': target})
    if len(changes) != 8:
        raise ValueError('Expected exactly eight lowercase/uppercase replacements')
    # These are dedicated tables: English UK/US use separate addresses. Keep
    # the symbol page and all executable instructions unchanged.
    for offset, (expected, target) in SECONDARY_TABLES.items():
        raw, replacement = expected.encode('utf-16-le'), target.encode('utf-16-le')
        if len(raw) != 88 or len(replacement) != len(raw):
            raise ValueError('Secondary tables must have exactly 44 characters')
        if not ro_file <= offset < offset + len(raw) <= ro_file + ro_size:
            raise ValueError('Secondary keyboard table is outside read-only data')
        if data[offset:offset + len(raw)] != raw:
            raise ValueError('Unexpected Russian Latin keyboard table')
        patch += offset.to_bytes(3, 'big') + len(replacement).to_bytes(2, 'big') + replacement
        changes.append({'offset': offset, 'from': expected, 'to': target})
    patch += b'EOF'
    return bytes(patch), changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nso', type=Path, required=True, help='Owner-extracted, uncompressed swkbd main NSO')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    patch, changes = build(args.nso.read_bytes())
    destination = args.output / 'atmosphere/exefs_patches/nx-ukrainian-keyboard' / (BUILD_ID + '.ips')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(patch)
    metadata = {'firmware': '23.0.1', 'program_id': '0100000000001008', 'build_id': BUILD_ID,
                'patch_sha256': hashlib.sha256(patch).hexdigest(), 'changes': changes,
                'replaces': {'Russian': 'Ukrainian', 'Russian (Latin)': 'Russian (Cyrillic)'},
                'console_tests': {'primary_ukrainian': True, 'secondary_russian': False}}
    (args.output / 'manifest.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')
    print('Created keyboard patch: Ukrainian primary and Russian Cyrillic secondary')


if __name__ == '__main__':
    main()
