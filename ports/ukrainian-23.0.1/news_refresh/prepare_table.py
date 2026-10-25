#!/usr/bin/env python3
"""Generate the private refresh table from the owner's local firmware and build."""
from pathlib import Path
import argparse
import hashlib
import struct
import sys
import zipfile
import json
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from port_config import WORK, OUTPUT
from msbt import Msbt, commands, text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extra-article', type=Path,
                        help='private MessagePack capture of the channel-subscription article')
    args = parser.parse_args()
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
    if args.extra_article:
        sys.path.insert(0, str(WORK / 'python-deps'))
        import msgpack
        capture = args.extra_article.read_bytes()
        assert len(capture) <= 8 * 1024 * 1024
        unpacker = msgpack.Unpacker(raw=False, strict_map_key=False)
        unpacker.feed(capture)
        article = unpacker.unpack()
        additions = json.loads(Path(__file__).with_name('additional-ukrainian.json').read_text())
        for key in ('news_id', 'language', 'topic_id'):
            assert article[key] == additions[key], 'Unexpected additional article identity'
        assert article['version']['semantics'] == additions['version_semantics']
        for field in additions['fields']:
            source = article
            for key in field['path'].split('.'):
                source = source[key]
            assert hashlib.sha256(source.encode()).hexdigest() == field['source_sha256'], 'Additional article text changed'
            target = field['target']
            assert sorted(c for c in source if '\ue000' <= c <= '\uf8ff') == sorted(c for c in target if '\ue000' <= c <= '\uf8ff')
            rows.append((source, target, field['path'] == 'subject.text'))
        assert len(rows) == len({a for a, _, _ in rows}) == 45
    data = bytearray(b'NXUKNEWS' + struct.pack('<I', len(rows)))
    for source, target, subject in rows:
        a, b = source.encode('utf-8'), target.encode('utf-8')
        data += struct.pack('<III', subject, len(a), len(b)) + a + b
    output = OUTPUT / 'news-refresh/translations-0.1.6.bin'
    output.parent.mkdir(exist_ok=True)
    output.write_bytes(data)
    print(f'Prepared {len(rows)} local translations; private firmware text is not committed.')


if __name__ == '__main__':
    main()
