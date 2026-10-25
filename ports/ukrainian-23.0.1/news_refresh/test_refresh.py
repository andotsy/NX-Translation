#!/usr/bin/env python3
"""Exercise the exact on-device parser with an independent MessagePack codec."""
from pathlib import Path
import copy
import json
import random
import struct
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from port_config import WORK, OUTPUT
sys.path.insert(0, str(WORK / 'python-deps'))
import msgpack


class RefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = Path(__file__).resolve().parent
        cls.tool = WORK / 'news-refresh-host-test'
        subprocess.run(['clang++', '-std=c++17', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=address,undefined', str(cls.folder / 'host_test.cpp'), '-o', str(cls.tool)], check=True)
        cls.table = OUTPUT / 'news-refresh/translations.bin'
        data = cls.table.read_bytes()
        assert data[:8] == b'NXUKNEWS' and struct.unpack_from('<I', data, 8)[0] == 41
        cls.rows = []
        pos = 12
        for _ in range(41):
            flags, a, b = struct.unpack_from('<III', data, pos)
            pos += 12
            source = data[pos:pos + a].decode(); pos += a
            target = data[pos:pos + b].decode(); pos += b
            cls.rows.append((source, target, flags))
        assert pos == len(data)
        cls.source, cls.target, _ = next(row for row in cls.rows if row[2])

    def call(self, raw, valid=True, table=None):
        with tempfile.TemporaryDirectory(dir=WORK) as tmp:
            root = Path(tmp)
            (root / 'input').write_bytes(raw)
            r = subprocess.run([str(self.tool), str(table or self.table), str(root / 'input'), str(root / 'output')],
                               capture_output=True, text=True)
            if valid:
                self.assertEqual(r.returncode, 0, r.stderr)
                return json.loads(r.stdout), (root / 'output').read_bytes()
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertFalse((root / 'output').exists())

    def article(self):
        return {'news_id': 10000, 'topic_id': 'nx_notice', 'language': 'ru',
                'published_at': 1751302719, 'supported_languages': ['ru', 'en-GB'],
                'subject': {'caption': 1, 'text': self.source}, 'topic_name': 'unchanged',
                'list_image': bytes(range(256)), 'body': {'main_image': b'\x00\xff' * 4096},
                'footer': {'text': 'unknown original'}, 'opaque': msgpack.ExtType(1, b'1234')}

    def test_all_translations_only_touch_allowlisted_fields(self):
        for source, target, _ in self.rows:
            with self.subTest(source=source[:30]):
                article = self.article()
                article['body']['text'] = source
                article['footer']['text'] = source
                article['more'] = {'system_applet': {'type': 4, 'text': source}}
                article['opaque_text'] = source
                article['array'] = [source, {'text': source}]
                article[source] = source
                expected = copy.deepcopy(article)
                expected['subject']['text'] = self.target
                expected['body']['text'] = expected['footer']['text'] = target
                expected['more']['system_applet']['text'] = target
                report, raw = self.call(msgpack.packb(article, use_bin_type=True))
                self.assertTrue(report['tutorial'])
                self.assertEqual(report['changes'], 4)
                actual = msgpack.unpackb(raw, raw=False, strict_map_key=False)
                self.assertEqual(actual, expected)
                again, second = self.call(raw)
                self.assertEqual(again['changes'], 0)
                self.assertEqual(second, raw)

    def test_other_languages_topics_and_unrecognized_articles_stay_byte_identical(self):
        for key, value in [('language', 'en-GB'), ('topic_id', 'different-channel'),
                           ('subject', {'text': 'unrecognized tutorial'})]:
            article = self.article(); article[key] = value
            original = msgpack.packb(article, use_bin_type=True)
            result, after = self.call(original)
            self.assertFalse(result['tutorial'])
            self.assertEqual(after, original)

    def test_binary_extensions_arrays_numbers_and_long_string_sizes(self):
        rng = random.Random(2301)
        for index in range(25):
            article = self.article()
            article['unknown'] = [None, True, False, -33, -(2 ** 63), 2 ** 64 - 1, 1.25,
                                  rng.randbytes(index * 123), 'Ї' * (index * 99),
                                  msgpack.ExtType(index, rng.randbytes(index + 1)),
                                  {str(i): i for i in range(index)}]
            expected = copy.deepcopy(article); expected['subject']['text'] = self.target
            _, after = self.call(msgpack.packb(article, use_bin_type=True))
            self.assertEqual(msgpack.unpackb(after, raw=False), expected)

    def test_malformed_and_truncated_data_are_rejected_without_output(self):
        raw = msgpack.packb(self.article(), use_bin_type=True)
        for bad in [b'', b'\xc1', b'\xdb\xff\xff\xff\xff', b'\xdf\xff\xff\xff\xff',
                    b'\x91' * 35 + b'\xc0', raw + b'\xc0', *[raw[:n] for n in [1, 8, 31, len(raw) - 1]]]:
            self.call(bad, valid=False)
        with tempfile.TemporaryDirectory(dir=WORK) as tmp:
            p = Path(tmp) / 'bad-table'; p.write_bytes(self.table.read_bytes()[:-1])
            self.call(raw, valid=False, table=p)


if __name__ == '__main__':
    unittest.main()
