#!/usr/bin/env python3
"""Translate the owner's 23.0.1 EUru Health and Safety HTML without changing markup."""
import argparse
from collections import Counter
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re

SOURCE_SHA256 = '832011405519224fb1e7eb0032cf703f9dceb13f0f3d96d3a13c834171ae6349'
ENGLISH_SHA256 = '72445c0190c40d2f72ca0cd84d74727738283d3d1dee36d34c514f0c1f6b13c4'
RELATIVE = 'safe.htdocs/html/EUru/index.html'
SPAN = re.compile(r'<span data-msgid="textbox_id-(\d+)">(.*?)</span>', re.S)
BREAK = re.compile(r'<br\s*/?>', re.I)


def semantic(value):
    value = BREAK.sub('<BR/>', value)
    if re.search(r'<(?!BR/>)', value):
        raise ValueError('Unexpected markup inside source text')
    return re.sub(r'\s+', ' ', html.unescape(value)).strip()


class Structure(HTMLParser):
    def __init__(self, value):
        super().__init__(convert_charrefs=True)
        self.events = []
        self.feed(value)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.events.append(('start', tag, [(k, 'locale' if tag == 'html' and k == 'lang' else v) for k, v in attrs]))

    def handle_endtag(self, tag):
        self.events.append(('end', tag))

    def handle_startendtag(self, tag, attrs):
        self.events.append(('empty', tag, attrs))


def build(romfs, output):
    original = (romfs / RELATIVE).read_bytes()
    english = (romfs / 'safe.htdocs/html/EUen/index.html').read_bytes()
    if hashlib.sha256(original).hexdigest() != SOURCE_SHA256 or hashlib.sha256(english).hexdigest() != ENGLISH_SHA256:
        raise ValueError('Unsupported Health and Safety source; expected the verified 23.0.1 files')
    if output.exists():
        raise ValueError('Output directory already exists')
    source = original.decode('utf-8')
    targets = json.loads(Path(__file__).with_name('ukrainian.json').read_text())
    pairs = SPAN.findall(source)
    if len(pairs) != len(dict(pairs)):
        raise ValueError('Duplicate message ID')
    required = {key for key, value in pairs if semantic(value) and key != '9'}
    if set(targets) != required:
        raise ValueError('Translation must cover every nonempty linguistic span')

    def replace(match):
        key, body = match.groups()
        if key not in targets:
            return match[0]
        target = targets[key]
        if re.search('[ЁёЫыЭэЪъ]', target):
            raise ValueError('Russian-only letter in Ukrainian target')
        if Counter(re.findall(r'\d+', body)) != Counter(re.findall(r'\d+', target)):
            raise ValueError('A safety number or product identifier changed')
        breaks = BREAK.findall(body)
        chunks = target.split('<BR/>')
        if len(chunks) != len(breaks) + 1:
            raise ValueError('Line-break markup changed')
        translated = html.escape(chunks[0], quote=False)
        for markup, text in zip(breaks, chunks[1:]):
            translated += markup + html.escape(text, quote=False)
        return match[0][:match[0].index('>') + 1] + translated + '</span>'

    translated = SPAN.sub(replace, source)
    translated, title_count = re.subn(r'<title>[^<]*</title>', '<title>' + html.escape(targets['74']) + '</title>', translated)
    assert title_count == 1 and translated.count('<html lang="ru-RU">') == 1
    translated = translated.replace('<html lang="ru-RU">', '<html lang="uk-UA">')
    assert Structure(source).events == Structure(translated).events
    # Removing only translated prose and normalizing the locale must leave the
    # exact native shell, including scripts, images, links, IDs and comments.
    def shell(value):
        value = SPAN.sub(lambda m: m[0][:m[0].index('>') + 1] + ''.join(BREAK.findall(m[2])) + '</span>' if m[1] in targets else m[0], value)
        value = re.sub(r'<title>[^<]*</title>', '<title></title>', value)
        return value.replace('lang="uk-UA"', 'lang="ru-RU"')
    assert shell(source) == shell(translated)
    for key, value in SPAN.findall(translated):
        if key in targets:
            assert semantic(value) == targets[key]
    assert '<BR/>' not in translated
    data = translated.encode('utf-8')
    destination = output / 'atmosphere/contents/0100000000000804/romfs' / RELATIVE
    destination.parent.mkdir(parents=True)
    destination.write_bytes(data)
    source_en = dict(SPAN.findall(english.decode('utf-8')))
    entries = [{'id': key, 'source': semantic(source_en[key]), 'target': value} for key, value in targets.items()]
    manifest = {'firmware': '23.0.1', 'data_id': '0100000000000804', 'path': str(destination.relative_to(output)),
                'source_sha256': SOURCE_SHA256, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
                'translated_spans': len(required), 'translated_title': True, 'native_shell_preserved': True,
                'safety_numbers_preserved': True, 'console_tested': False}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (output / 'catalog-entries.json').write_text(json.dumps(entries, ensure_ascii=False, indent=2) + '\n')
    print(f'Created Ukrainian safety page: {len(required)} spans plus title; native shell and safety numbers preserved')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--romfs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.romfs, args.output)
