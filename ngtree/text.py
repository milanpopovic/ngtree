"""Text helpers: folding for search (Staniša = Stanisa = Станиша), Serbian alphabetical order, slugs, path lines."""
from __future__ import annotations

import re
import unicodedata

# Serbian Cyrillic -> Latin, so 'Петар' and 'Petar' match in the filter
_CYR = dict(zip('абвгдђежзијклљмнњопрстћуфхцчџш',
                ['a', 'b', 'v', 'g', 'd', 'dj', 'e', 'z', 'z', 'i', 'j', 'k', 'l', 'lj', 'm', 'n', 'nj', 'o', 'p',
                 'r', 's', 't', 'c', 'u', 'f', 'h', 'c', 'c', 'dz', 's']))
_LAT = {'č': 'c', 'ć': 'c', 'š': 's', 'ž': 'z', 'đ': 'dj'}
_ALPHABET = 'abcčćdđefghijklmnoprsštuvzž'
_ORDER = {ch: i for i, ch in enumerate(_ALPHABET)}

def fold_text(text: str) -> str:
    out = []
    for ch in text.lower():
        out.append(_CYR.get(ch) or _LAT.get(ch) or ch)
    s = ''.join(out)
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))


def fold(label: str) -> str:
    """Case-, script- and diacritics-insensitive key: 'Staniša' == 'stanisa' == 'СТАНИША'."""
    return fold_text(label).replace(' ', '')


def words(label: str) -> list[str]:
    """'Rade(monah Grigorije)+' -> ['rade', 'monah', 'grigorije']"""
    return re.findall(r'\w+', fold_text(label))


def sort_key(label: str):
    return [_ORDER.get(ch, 100 + ord(ch)) for ch in label.lower()]


def slugify(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', fold_text(text)).strip('-')[:40].strip('-')


def is_header(line: str) -> bool:
    """An all-caps line is a branch header (as in pasovi.txt)."""
    s = line.strip()
    return bool(s) and s.isupper()


def split(line: str) -> list[str]:
    """'A, B,C' -> ['A', 'B', 'C'] (';' also accepted)."""
    return [n.strip() for n in line.replace(';', ',').split(',') if n.strip()]


def clean(label: str) -> str:
    return re.sub(r'\s+', ' ', label or '').strip()
