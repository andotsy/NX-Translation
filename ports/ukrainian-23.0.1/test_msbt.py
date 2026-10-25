import sys
from pathlib import Path
import unittest
from port_config import WORK

ROOT = WORK
sys.path.insert(0, str(ROOT / 'python-deps'))
import oead
from compare_resources import parse
from msbt import Msbt, commands, decompress, tokens


class BinaryPreservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths = sorted(p for p in (ROOT / 'firmware-23.0.1-resources').rglob('*')
                           if p.is_file() and p.suffix in {'.msbt', '.szs'})
        assert len(cls.paths) == 106

    def test_all_current_files_roundtrip_byte_identically(self):
        for path in self.paths:
            with self.subTest(path=str(path)):
                msbt = Msbt(path.read_bytes())
                self.assertEqual(msbt.build(msbt.messages), msbt.data)

    def test_changed_lengths_preserve_labels_attributes_and_controls(self):
        for path in self.paths:
            with self.subTest(path=str(path)):
                original = Msbt(path.read_bytes())
                messages = list(original.messages)
                for index in {0, len(messages) // 2, len(messages) - 1}:
                    messages[index] = ('Їжак Ґанок Єдність ' * (index % 7 + 1)).encode('utf-16-le') + messages[index]
                data = original.build(messages)
                rebuilt = Msbt(data)
                independent = parse(data)
                self.assertEqual(rebuilt.labels, original.labels)
                self.assertEqual(independent['labels'], original.labels)
                self.assertEqual(independent['messages'], messages)
                for section in original.sections:
                    if section.tag != 'TXT2':
                        self.assertEqual(section, rebuilt.by_tag[section.tag])
                for before, after in zip(original.messages, rebuilt.messages):
                    self.assertEqual(commands(before), commands(after))

    def test_yaz0_matches_independent_native_codec(self):
        for path in self.paths:
            with self.subTest(path=str(path)):
                data = path.read_bytes()
                if data[:4] == b'Yaz0':
                    self.assertEqual(decompress(data), bytes(oead.yaz0.decompress(data)))
                raw = decompress(data)
                encoded = bytes(oead.yaz0.compress(raw))
                self.assertEqual(decompress(encoded), raw)
                self.assertEqual(bytes(oead.yaz0.decompress(encoded)), raw)

    def test_rejects_truncated_or_embedded_terminators(self):
        for data in [b'', b'A', b'A\0', b'\0\0A\0',
                     b'\x0e\0\x02\0\x07\0\xff\xff\0\0', b'\x0f\0\x01\0']:
            with self.subTest(data=data):
                with self.assertRaises(AssertionError):
                    tokens(data)


if __name__ == '__main__':
    unittest.main()
