"""Build a source-verified translation catalog and list manual work."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
from port_config import WORK, OLD_CONTENTS, YAML_SOURCE
sys.path.insert(0, str(WORK / 'python-deps'))
import yaml
from msbt import Msbt, tokens, text, commands

ROOT = WORK
BASE = ROOT / 'firmware-22.5.0-resources'
CURRENT = ROOT / 'firmware-23.0.1-resources'
UKRAINIAN = OLD_CONTENTS


def runtime(message):
    # Group 2 is substitution data; type 22 contains localized plural words.
    return Counter(c for c in commands(message)
                   if struct.unpack_from('<H', c, 2)[0] == 2
                   and struct.unpack_from('<H', c, 4)[0] != 22)


def semantic(message):
    # Source matching includes plural-word payloads: their text carries meaning.
    source_commands = Counter(c for c in commands(message)
                              if struct.unpack_from('<H', c, 2)[0] == 2)
    return (text(message).replace('\r\n', '\n'), tuple(sorted(source_commands.items())))


def printf_args(message):
    return Counter(re.findall(r'%(?:\d+\$)?(?:\d+)?(?:\.\d+)?[A-Za-z]', text(message)))


def render(message):
    out = ''
    index = 0
    for kind, value in tokens(message):
        if kind == 'text':
            assert not re.search(r'<C\d+/>', value)
            out += value
        else:
            out += '<C' + str(index) + '/>'
            index += 1
    return out


def compile_template(template, original):
    original_commands = commands(original)
    indices = [int(x) for x in re.findall(r'<C(\d+)/>', template)]
    assert indices == list(range(len(original_commands))), 'Commands must remain once each in order'
    parts = re.split(r'(<C\d+/>)', template)
    output = bytearray()
    for part in parts:
        match = re.fullmatch(r'<C(\d+)/>', part)
        if match:
            output += original_commands[int(match[1])]
        else:
            assert not any(c in part for c in ['\x00', '\x0e', '\x0f'])
            output += part.encode('utf-16-le')
    output += b'\x00\x00'
    assert commands(bytes(output)) == original_commands
    tokens(bytes(output))
    return bytes(output)


def main():
    assert BASE.is_dir()
    catalog = defaultdict(list)
    by_label = defaultdict(list)
    for p in sorted(UKRAINIAN.rglob('*')):
        if not p.is_file():
            continue
        rel = p.relative_to(UKRAINIAN)
        title = rel.parts[0].lower()
        path = str(Path(*rel.parts[2:]))
        uk = Msbt(p.read_bytes())
        en = Msbt((BASE / title / path.replace('EUru', 'EUen')).read_bytes())
        for label, index in uk.labels.items():
            assert label in en.labels
            english = en.messages[en.labels[label]]
            translated = uk.messages[index]
            entry = {'uk': translated, 'english': english, 'title': title, 'path': path, 'label': label}
            catalog[semantic(english)].append(entry)
            by_label[(label, semantic(english))].append(entry)
    yaml_rows = yaml.safe_load(YAML_SOURCE.read_text())['translations']
    yaml_map = defaultdict(set)
    for row in yaml_rows:
        def basic(value):
            value = value.replace('<NL/>', '\n')
            return re.sub(r'<0x([0-9A-Fa-f]+)/>', lambda m: chr(int(m[1], 16)), value)
        source, target = basic(row['source']), basic(row['target'])
        if not re.search(r'<[^>]+/>', source + target):
            yaml_map[source].add(target)
    results = []
    unresolved = {}
    counters = Counter()
    for p in sorted(CURRENT.rglob('*')):
        if not p.is_file() or 'EUru' not in p.parts or p.suffix == '.msbp':
            continue
        rel = p.relative_to(CURRENT)
        title = rel.parts[0]
        path = str(Path(*rel.parts[1:]))
        ru = Msbt(p.read_bytes())
        en = Msbt((CURRENT / title / path.replace('EUru', 'EUen')).read_bytes())
        assert set(ru.labels) == set(en.labels)
        index_to_labels = defaultdict(list)
        for label, index in ru.labels.items():
            index_to_labels[index].append(label)
        assert set(index_to_labels) == set(range(len(ru.messages)))
        for index, labels in sorted(index_to_labels.items()):
            label = sorted(labels)[0]
            english = en.messages[en.labels[label]]
            russian = ru.messages[index]
            assert all(en.messages[en.labels[x]] == english for x in labels)
            location = {'title': title, 'path': path, 'labels': labels, 'index': index}
            result = {**location, 'english_sha256': hashlib.sha256(english).hexdigest(),
                      'russian_sha256': hashlib.sha256(russian).hexdigest()}
            candidates = by_label.get((label, semantic(english)), [])
            source_kind = 'same_label_verified_source'
            if not candidates:
                candidates = catalog.get(semantic(english), [])
                source_kind = 'translation_memory_verified_source'
            same_title = [c for c in candidates if c['title'] == title and c['path'] == path]
            if same_title:
                candidates = same_title
            same_file = [c for c in candidates if Path(c['path']).name == Path(path).name]
            if same_file:
                candidates = same_file
            # Existing pack's substitution contract must agree with current EN or RU.
            candidates = [c for c in candidates if runtime(c['uk']) in (runtime(english), runtime(russian))]
            candidates = [c for c in candidates if printf_args(c['uk']) == printf_args(english)]
            candidates = [c for c in candidates if not re.search(r'[ЁёЫыЭэЪъ]', text(c['uk']))]
            translations = {c['uk'] for c in candidates}
            if len(translations) == 1:
                translated = next(iter(translations))
                result.update(method=source_kind, translated_hex=translated.hex())
            elif (not commands(english) and not commands(russian)
                  and len(yaml_map.get(text(english), set())) == 1):
                translated = next(iter(yaml_map[text(english)])).encode('utf-16-le') + b'\0\0'
                result.update(method='upstream_yaml_exact_plain_source', translated_hex=translated.hex())
            elif not re.search(r'[A-Za-zА-Яа-яЁё]', text(russian)):
                result.update(method='nonlinguistic_original', translated_hex=russian.hex())
            else:
                key = hashlib.sha256(english + b'\xff\xff' + russian).hexdigest()[:20]
                result.update(method='manual_required', manual_key=key)
                if key not in unresolved:
                    unresolved[key] = {'key': key, 'english': render(english),
                                       'russian': render(russian), 'locations': [],
                                       'candidate_ukrainian': sorted({render(c['uk']) for c in candidates})}
                unresolved[key]['locations'].append(location)
            counters[result['method']] += 1
            results.append(result)
    (ROOT / 'translation-catalog.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
    (ROOT / 'manual-required.json').write_text(json.dumps(list(unresolved.values()), ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'methods': dict(counters), 'manual_unique': len(unresolved),
                      'records': len(results)}, indent=2))


if __name__ == '__main__':
    main()
