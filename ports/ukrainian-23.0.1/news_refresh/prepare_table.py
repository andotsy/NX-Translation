#!/usr/bin/env python3
"""Generate the private refresh table from the owner's local firmware and build."""
from pathlib import Path
import hashlib
import struct
import sys
import zipfile
import json
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from port_config import WORK, OUTPUT
from msbt import Msbt, commands, text


def main():
    relative = 'atmosphere/contents/010000000000080B/romfs/message/EUru/localNews.msbt.szs'
    original = Msbt((WORK / 'firmware-23.0.1-resources/010000000000080b/message/EUru/localNews.msbt.szs').read_bytes())
    with zipfile.ZipFile(OUTPUT / 'ukrainian-23.0.1-EUru-full.zip') as archive:
        rows = json.loads(archive.read('ukrainian-23.0.1-manifest.json'))
        data = archive.read(relative)
        assert hashlib.sha256(data).hexdigest() == next(r['sha256'] for r in rows if r['path'] == relative)
        translated = Msbt(data)
    assert original.labels == translated.labels
    rows = []
    for label, index in original.labels.items():
        assert not commands(original.messages[index]) and not commands(translated.messages[index])
        source, target = text(original.messages[index]), text(translated.messages[index])
        if source:
            assert source != target
            rows.append((source, target, label.endswith('_Subject')))
    assert len(rows) == len({a for a, _, _ in rows}) == 41
    data = bytearray(b'NXUKNEWS' + struct.pack('<I', len(rows)))
    for source, target, subject in rows:
        a, b = source.encode('utf-8'), target.encode('utf-8')
        data += struct.pack('<III', subject, len(a), len(b)) + a + b
    output = OUTPUT / 'news-refresh/translations.bin'
    output.parent.mkdir(exist_ok=True)
    output.write_bytes(data)
    print('Prepared 41 local translations; private firmware text is not committed.')


if __name__ == '__main__':
    main()
