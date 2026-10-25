#!/usr/bin/env python3
"""Exercise the exact on-device parser with an independent MessagePack codec."""
from pathlib import Path
import copy
import json
import os
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

    def call(self, raw, valid=True, table=None, native=False):
        with tempfile.TemporaryDirectory(dir=WORK) as tmp:
            root = Path(tmp)
            (root / 'input').write_bytes(raw)
            command = [str(self.tool), str(table or self.table), str(root / 'input'), str(root / 'output')]
            if native:
                command.append('--native-buffer')
            r = subprocess.run(command,
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

    def test_zero_padded_news_storage_is_translated_as_one_serialized_map(self):
        original = self.article()
        raw = msgpack.packb(original, use_bin_type=True)
        expected = copy.deepcopy(original)
        expected['subject']['text'] = self.target
        for padding in [1, 512, 524288 - len(raw)]:
            report, after = self.call(raw + b'\0' * padding)
            self.assertTrue(report['tutorial'])
            self.assertEqual(msgpack.unpackb(after, raw=False), expected)
            again, unchanged = self.call(after + b'\0' * 4096)
            self.assertEqual(again['changes'], 0)
            self.assertEqual(unchanged, after)

    def test_nonzero_trailers_and_non_map_roots_are_rejected(self):
        raw = msgpack.packb(self.article(), use_bin_type=True)
        for suffix in [b'\1', b'\0' * 32 + b'\xc0', b'\0' * 32 + b'\xcc\0']:
            self.call(raw + suffix, valid=False)
        for raw in [b'\0' * 1024, b'\x90', b'\xa1x', b'\xc0']:
            self.call(raw, valid=False)
            self.call(raw, valid=False, native=True)

    def test_native_buffers_with_previous_article_bytes_preserve_current_article(self):
        previous = self.article()
        previous['body']['old_article_only'] = b'old image and text' * 4096
        previous = msgpack.packb(previous, use_bin_type=True)
        current = self.article()
        current['body'] = {'text': self.source, 'main_image': b'short image'}
        raw = msgpack.packb(current, use_bin_type=True)
        buffer = raw + previous[len(raw):]
        self.assertGreater(len(buffer), len(raw))
        self.call(buffer, valid=False)
        report, after = self.call(buffer, native=True)
        expected = copy.deepcopy(current)
        expected['subject']['text'] = expected['body']['text'] = self.target
        self.assertEqual(report['payload_bytes'], len(raw))
        self.assertEqual(msgpack.unpackb(after, raw=False), expected)

    @unittest.skipUnless(os.environ.get('NX_NEWS_CAPTURE_DIR'), 'private console capture set not provided')
    def test_all_private_native_records_and_changing_service_buffer_tails(self):
        captures = sorted(Path(os.environ['NX_NEWS_CAPTURE_DIR']).glob('article-*.bin'))
        self.assertGreaterEqual(len(captures), 7)
        table = {source: target for source, target, _ in self.rows}
        subjects = {source for source, _, flags in self.rows if flags}
        allowed = {'topic_name', 'subject.text', 'body.text', 'footer.text',
                   'more.system_applet.text', 'more.text'}

        def expected_value(value, path=''):
            if isinstance(value, str) and path in allowed:
                return table.get(value, value)
            if isinstance(value, dict):
                return {key: expected_value(child, path + ('.' if path else '') + str(key))
                        for key, child in value.items()}
            if isinstance(value, list):
                return [expected_value(child, path + '[]') for child in value]
            return value

        translated = untouched = nonzero_tails = 0
        rng = random.Random(230104)
        for capture in captures:
            with self.subTest(capture=capture.name):
                raw = capture.read_bytes()
                unpacker = msgpack.Unpacker(raw=False, strict_map_key=False)
                unpacker.feed(raw)
                original = unpacker.unpack()
                used = unpacker.tell()
                if any(raw[used:]):
                    nonzero_tails += 1
                    self.call(raw, valid=False)
                report, after = self.call(raw, native=True)
                self.assertEqual(report['payload_bytes'], used)
                known = original.get('language') == 'ru' and original.get('topic_id') == 'nx_notice' and original.get('subject', {}).get('text') in subjects
                self.assertEqual(report['tutorial'], known)
                if not known:
                    untouched += 1
                    self.assertEqual(after, raw)
                    continue
                translated += 1
                self.assertGreater(report['changes'], 0)
                self.assertEqual(msgpack.unpackb(after, raw=False), expected_value(original))
                # The same article may arrive with a different buffer tail on its
                # next read. Neither comparison nor transformation may use it.
                altered = raw[:used] + rng.randbytes(len(raw) - used)
                changed_tail, same_result = self.call(altered, native=True)
                self.assertEqual(changed_tail, report)
                self.assertEqual(same_result, after)
                self.assertLessEqual(len(after), len(raw))
                returned = after + raw[len(after):]
                repeated, unchanged = self.call(returned, native=True)
                self.assertEqual(repeated['changes'], 0)
                self.assertEqual(unchanged, after)
        self.assertEqual(translated, 6)
        self.assertEqual(untouched, 1)
        self.assertEqual(nonzero_tails, 4)

    @unittest.skipUnless(os.environ.get('NX_NEWS_CAPTURE'), 'private console sample not provided')
    def test_private_console_snapshot_preserves_every_untranslated_field(self):
        raw = Path(os.environ['NX_NEWS_CAPTURE']).read_bytes()
        unpacker = msgpack.Unpacker(raw=False, strict_map_key=False)
        unpacker.feed(raw)
        original = unpacker.unpack()
        consumed = unpacker.tell()
        self.assertGreater(len(raw), consumed)
        self.assertFalse(any(raw[consumed:]))
        table = {source: target for source, target, _ in self.rows}
        allowed = {'topic_name', 'subject.text', 'body.text', 'footer.text',
                   'more.system_applet.text', 'more.text'}

        def expected_value(value, path=''):
            if isinstance(value, str) and path in allowed:
                return table.get(value, value)
            if isinstance(value, dict):
                return {key: expected_value(child, path + ('.' if path else '') + str(key))
                        for key, child in value.items()}
            if isinstance(value, list):
                return [expected_value(child, path + '[]') for child in value]
            return value

        report, after = self.call(raw)
        self.assertTrue(report['tutorial'])
        self.assertGreater(report['changes'], 0)
        self.assertEqual(msgpack.unpackb(after, raw=False), expected_value(original))
        self.assertLess(len(after), len(raw))
        report, again = self.call(after + b'\0' * (len(raw) - len(after)))
        self.assertEqual(report['changes'], 0)
        self.assertEqual(again, after)


if __name__ == '__main__':
    unittest.main()
