"""Tree operations — pure functions on a tree document, no files, no UI.

A document is a dict with at least
    {"next_id": int, "nodes": [node, ...]}
    node = {"id": int, "label": str, "note"?: str, "tag"?: str, "children": [node, ...]}
Any other keys (name, owner, ...) belong to the app and are left alone.

Node ids are stable: next_id only grows, so a tree view keeps what was open across changes.
Functions that change the tree change `doc` in place; stores (stores.py) call them on a fresh copy and save.
"""
from __future__ import annotations

import copy
import json

from .text import clean, fold, is_header, sort_key, split, words

MAX_LABEL = 200
MAX_NOTE = 4000
MAX_TAG = 60
MAX_FILTER_MATCHES = 300
WHERE = ('before', 'after', 'inside')


class TreeError(Exception):
    """text = Serbian message (also the translation key, see i18n.py), values = for its {0}, {1}... placeholders."""

    def __init__(self, text: str, *values) -> None:
        super().__init__(text.format(*values))
        self.text, self.values = text, values


# ---------------------------------------------------------------- documents

def new_doc(nodes: list[dict] | None = None, **extra) -> dict:
    """A new document; `nodes` may come with or without ids (missing ids are given)."""
    doc = {**extra, 'next_id': 1, 'nodes': []}
    if nodes:
        doc['nodes'] = normalize(doc, nodes)
    return doc


def normalize(doc: dict, nodes: list[dict]) -> list[dict]:
    """Nodes from outside (a list you built, a database): every node gets a label, children and a unique id.
    Existing unique integer ids are kept; next_id is moved past them."""
    seen: set[int] = set()

    def ids(level):
        for n in level:
            if isinstance(n.get('id'), int):
                seen.add(n['id'])
            ids(n.get('children') or [])

    ids(nodes)
    doc['next_id'] = max([doc.get('next_id', 1)] + [i + 1 for i in seen])
    used: set[int] = set()

    def walk(level):
        out = []
        for n in level:
            c = {k: v for k, v in n.items() if k != 'children'}
            c['label'] = clean(str(c.get('label', ''))) or '?'
            if not isinstance(c.get('id'), int) or c['id'] in used:
                c['id'] = doc['next_id']
                doc['next_id'] += 1
            used.add(c['id'])
            c['children'] = walk(n.get('children') or [])
            out.append(c)
        return out

    return walk(nodes)


def find(nodes: list[dict], node_id: int, parent: dict | None = None):
    """(list that holds the node, its index, parent node or None) or None."""
    for i, n in enumerate(nodes):
        if n['id'] == node_id:
            return nodes, i, parent
        hit = find(n.get('children', []), node_id, n)
        if hit:
            return hit
    return None


def get(doc: dict, node_id: int):
    hit = find(doc['nodes'], node_id)
    if not hit:
        raise TreeError('Taj čvor više ne postoji (možda ga je neko u međuvremenu obrisao).')
    return hit


def node(doc: dict, node_id: int) -> dict | None:
    hit = find(doc['nodes'], node_id)
    return hit[0][hit[1]] if hit else None


def check_label(label: str) -> str:
    label = clean(label)
    if not label:
        raise TreeError('Naziv ne može biti prazan.')
    if len(label) > MAX_LABEL:
        raise TreeError('Naziv je predugačak (najviše {0} znakova).', MAX_LABEL)
    return label


def _set_note(n: dict, note: str) -> None:
    note = (note or '').strip()[:MAX_NOTE]
    if note:
        n['note'] = note
    else:
        n.pop('note', None)


def _set_tag(n: dict, tag: str) -> None:
    tag = clean(tag)[:MAX_TAG]
    if tag:
        n['tag'] = tag
    else:
        n.pop('tag', None)


# ---------------------------------------------------------------- changes (in place)

def add(doc: dict, parent_id: int | None, label: str, note: str = '') -> int:
    """New node as the last child of parent_id (None = new top-level node). Returns its id."""
    label = check_label(label)
    n = {'id': doc['next_id'], 'label': label, 'children': []}
    doc['next_id'] += 1
    _set_note(n, note)
    if parent_id is None:
        doc['nodes'].append(n)
    else:
        siblings, i, _ = get(doc, parent_id)
        siblings[i].setdefault('children', []).append(n)
    return n['id']


def update(doc: dict, node_id: int, label: str, note: str | None = None, tag: str | None = None) -> None:
    """New label; note / tag too unless None (None = leave as it is)."""
    label = check_label(label)
    siblings, i, _ = get(doc, node_id)
    n = siblings[i]
    n['label'] = label
    if note is not None:
        _set_note(n, note)
    if tag is not None:
        _set_tag(n, tag)


def delete(doc: dict, node_id: int) -> int:
    """Removes the node with everything under it. Returns how many nodes were removed."""
    siblings, i, _ = get(doc, node_id)
    removed = siblings.pop(i)
    return count(removed.get('children', [])) + 1


def shift(doc: dict, node_id: int, delta: int) -> None:
    """Up (-1) / down (+1) among its siblings."""
    siblings, i, _ = get(doc, node_id)
    j = max(0, min(len(siblings) - 1, i + delta))
    if j != i:
        siblings.insert(j, siblings.pop(i))


def move(doc: dict, src: int, dst: int | None, where: str = 'inside') -> None:
    """Move src (with its subtree) before / after / inside dst. dst None = to the end of the top level."""
    if where not in WHERE:
        raise TreeError('Nepoznato mesto.')
    if src == dst:
        return
    siblings, i, _ = get(doc, src)
    n = siblings[i]
    if dst is not None and find(n.get('children', []), dst):
        raise TreeError('Čvor ne može da se premesti u sopstveni podčvor.')
    if dst is not None:
        get(doc, dst)  # exists?
    siblings.pop(i)
    if dst is None:
        doc['nodes'].append(n)
        return
    target, j, _ = get(doc, dst)
    if where == 'inside':
        target[j].setdefault('children', []).append(n)
    else:
        target.insert(j if where == 'before' else j + 1, n)


def sort_children(doc: dict, node_id: int | None) -> None:
    """Children of node_id (None = top level) in alphabetical order (Serbian alphabet)."""
    if node_id is None:
        level = doc['nodes']
    else:
        siblings, i, _ = get(doc, node_id)
        level = siblings[i].setdefault('children', [])
    level.sort(key=lambda n: sort_key(n['label']))


def insert_nodes(doc: dict, nodes: list[dict], parent_id: int | None = None, replace: bool = False) -> int:
    """Nodes without ids (from parse_paths / parse_json) into the tree; replace=True first empties it."""
    if replace:
        doc['nodes'] = []
        parent_id = None
    new = with_ids(doc, nodes)
    if parent_id is None:
        doc['nodes'] += new
    else:
        siblings, i, _ = get(doc, parent_id)
        siblings[i].setdefault('children', []).extend(new)
    return count(new)


def with_ids(doc: dict, nodes: list[dict]) -> list[dict]:
    out = []
    for n in nodes:
        c = {k: v for k, v in n.items() if k not in ('id', 'children')}
        c['id'] = doc['next_id']
        doc['next_id'] += 1
        c['children'] = with_ids(doc, n.get('children', []))
        out.append(c)
    return out


# ---------------------------------------------------------------- reading

def count(nodes: list[dict]) -> int:
    return sum(1 + count(n.get('children', [])) for n in nodes)


def stats(nodes: list[dict]) -> dict:
    total = leaves = depth = 0
    stack = [(n, 1) for n in nodes]
    while stack:
        n, d = stack.pop()
        total += 1
        depth = max(depth, d)
        kids = n.get('children') or []
        if not kids:
            leaves += 1
        stack += [(c, d + 1) for c in kids]
    return {'nodes': total, 'leaves': leaves, 'depth': depth}


def all_ids(nodes: list[dict]) -> list[int]:
    out = []
    for n in nodes:
        out.append(n['id'])
        out += all_ids(n.get('children', []))
    return out


def path_ids(nodes: list[dict], node_id: int) -> list[int]:
    """Ids from the top level down to the node's parent (what has to be open to see the node)."""
    def walk(level, trail):
        for n in level:
            if n['id'] == node_id:
                return trail
            found = walk(n.get('children', []), trail + [n['id']])
            if found is not None:
                return found
        return None
    return walk(nodes, []) or []


def path_labels(nodes: list[dict], node_id: int) -> list[str]:
    """Labels from the top level down to the node itself."""
    def walk(level, trail):
        for n in level:
            if n['id'] == node_id:
                return trail + [n['label']]
            found = walk(n.get('children', []), trail + [n['label']])
            if found is not None:
                return found
        return None
    return walk(nodes, []) or []


def filter_tree(nodes: list[dict], query: str) -> tuple[list[dict], list[int], int]:
    """Copy of the tree keeping only paths to nodes with a word starting with `query`.
    Returns (nodes, ids to expand, matches). Nodes keep their ids, so editing still works while filtered."""
    q = fold(query)
    expand: list[int] = []
    matches = 0

    def walk(level: list[dict]) -> list[dict]:
        nonlocal matches
        kept = []
        for n in level:
            if matches >= MAX_FILTER_MATCHES:
                break
            hit = any(w.startswith(q) for w in words(n['label'])) or fold(n['label']).startswith(q)
            children = walk(n.get('children', []))
            if hit:
                matches += 1
            if hit or children:
                c = {k: v for k, v in n.items() if k != 'children'}
                c['children'] = children
                if children:
                    expand.append(n['id'])
                if hit:
                    c['hit'] = True
                kept.append(c)
        return kept

    return walk(nodes), expand, matches


# ---------------------------------------------------------------- import / export

def parse_paths(text: str) -> list[dict]:
    """Text with one path per line ('Root, Child, Grandchild') -> nested nodes without ids.
    Lines with the same beginning share nodes. ALL CAPS lines are branch headers: the header becomes the
    'tag' of the node where that branch starts (the longest common beginning of its lines) — as in rodoslovi."""
    header, lines = '', []
    for raw in (text or '').replace('\r\n', '\n').splitlines():
        s = raw.strip()
        if not s:
            continue
        if is_header(s) and ',' not in s:
            header = s
            continue
        names = [clean(n) for n in split(s)]
        if names:
            lines.append((header, names))

    groups: dict[str, list[list[str]]] = {}
    for h, names in lines:
        if h:
            groups.setdefault(h, []).append(names)
    starts: dict[tuple, list[str]] = {}
    for h, paths in groups.items():
        prefix = paths[0]
        for p in paths[1:]:
            i = 0
            while i < min(len(prefix), len(p)) and prefix[i] == p[i]:
                i += 1
            prefix = prefix[:i]
        if prefix:
            starts.setdefault(tuple(prefix), []).append(h.title())

    root: list[dict] = []
    index: dict[tuple, dict] = {}
    for _h, names in lines:
        level = root
        for d in range(len(names)):
            key = tuple(names[: d + 1])
            n = index.get(key)
            if n is None:
                n = {'label': names[d][:MAX_LABEL], 'children': []}
                if key in starts:
                    n['tag'] = ' · '.join(starts[key])[:MAX_TAG]
                index[key] = n
                level.append(n)
            level = n['children']
    if not root:
        raise TreeError('U fajlu nema nijednog reda sa nazivima.')
    return root


def parse_json(text: str) -> list[dict]:
    """A whole-tree export, a subtree export, or just a "nodes" list -> nodes without ids."""
    try:
        data = json.loads(text)
    except ValueError as e:
        raise TreeError('Neispravan JSON: {0}', e)
    nodes = data.get('nodes') if isinstance(data, dict) else data
    if not isinstance(nodes, list):
        raise TreeError('JSON mora imati listu "nodes".')

    def walk(level):
        out = []
        for n in level:
            if not isinstance(n, dict) or not clean(str(n.get('label', ''))):
                continue
            c = {'label': clean(str(n['label']))[:MAX_LABEL], 'children': walk(n.get('children') or [])}
            if n.get('note'):
                c['note'] = str(n['note'])[:MAX_NOTE]
            if n.get('tag'):
                c['tag'] = clean(str(n['tag']))[:MAX_TAG]
            out.append(c)
        return out

    nodes = walk(nodes)
    if not nodes:
        raise TreeError('U fajlu nema nijednog čvora.')
    return nodes


def subtree(doc: dict, node_id: int) -> dict:
    """The node with everything under it (a copy)."""
    siblings, i, _ = get(doc, node_id)
    return copy.deepcopy(siblings[i])


def export_paths(doc: dict, node_id: int | None = None) -> str:
    """One line per leaf, from the top level down ('A,B,C'); a tagged node starts a header line (ALL CAPS).
    node_id: only that node's subtree — the paths then start at the node, so the file can be imported anywhere."""
    nodes = [subtree(doc, node_id)] if node_id is not None else doc['nodes']
    out: list[str] = []
    current = ['']

    def walk(level, trail, tag):
        for n in level:
            t = n.get('tag', '').upper() or tag
            kids = n.get('children') or []
            if kids:
                walk(kids, trail + [n['label']], t)
            else:
                if t != current[0]:
                    out.append(t)
                    current[0] = t
                out.append(','.join(trail + [n['label']]))

    walk(nodes, [], '')
    return '\n'.join(out) + '\n'


def export_json(doc: dict, node_id: int | None = None) -> str:
    """Whole document, or (node_id) {"name": node's label, "nodes": [the node with its subtree]} — the same
    shape, so import takes either."""
    if node_id is None:
        return json.dumps(copy.deepcopy(doc), ensure_ascii=False, indent=1)
    n = subtree(doc, node_id)
    return json.dumps({'name': n['label'], 'subtree_of': doc.get('name', ''), 'nodes': [n]},
                      ensure_ascii=False, indent=1)
