"""Where a tree lives. A TreeEditor talks only to a store; the store decides where the document is kept.

    JsonFileStore(path)              a JSON file: atomic writes, a backup before every change (undo walks back
                                     through them), live updates for every editor on the same file
    MemoryStore(nodes, on_change=)   in memory: you get the nodes after every change and save them yourself
                                     (database, your own file, app.storage ...); undo in memory

Every change goes through store.change(fn): fn gets a fresh copy of the document, changes it in place
(with the functions from ops.py) and may return a value. If fn raises TreeError nothing is saved.
After a successful change every editor showing this store is redrawn (subscribe / notify).

Write your own store by subclassing TreeStore and implementing _read(), _write(doc, before) and,
if you want undo, _undo() / can_undo().
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from . import ops
from .ops import TreeError

_listeners: dict[str, set[Callable[[], None]]] = {}
_locks: dict[str, threading.RLock] = {}
_guard = threading.Lock()


def _lock(key: str) -> threading.RLock:
    with _guard:
        return _locks.setdefault(key, threading.RLock())


class TreeStore:
    """Base class. `key` identifies the tree: editors on stores with the same key see each other's changes."""

    def __init__(self, *, key: str, max_nodes: int | None = None) -> None:
        self.key = key
        self.max_nodes = max_nodes

    # --- to implement
    def _read(self) -> dict | None:  # the current document (treat as read-only), None = it doesn't exist
        raise NotImplementedError

    def _write(self, doc: dict, before: dict) -> None:
        raise NotImplementedError

    def _undo(self) -> bool:
        return False

    def can_undo(self) -> bool:
        return False

    # --- used by TreeEditor and apps
    def load(self) -> dict | None:
        """The current document. Read-only: change it only through change()."""
        return self._read()

    def change(self, fn: Callable[[dict], Any]) -> Any:
        """fn(doc) changes a fresh copy; it is saved (and every editor redrawn) unless fn raises TreeError."""
        with _lock(self.key):
            current = self._read()
            if current is None:
                raise TreeError('Stablo više ne postoji.')
            doc = copy.deepcopy(current)
            result = fn(doc)
            if self.max_nodes is not None and ops.count(doc['nodes']) > self.max_nodes:
                raise TreeError('Stablo može imati najviše {0} čvorova.', self.max_nodes)
            self._write(doc, current)
        self.notify()
        return result

    def undo(self) -> bool:
        """Back to the state before the last change. False = nothing to undo."""
        with _lock(self.key):
            done = self._undo()
        if done:
            self.notify()
        return done

    def subscribe(self, fn: Callable[[], None]) -> None:
        """fn() is called after every change to this tree (from any browser / any editor)."""
        _listeners.setdefault(self.key, set()).add(fn)

    def unsubscribe(self, fn: Callable[[], None]) -> None:
        _listeners.get(self.key, set()).discard(fn)

    def notify(self) -> None:
        """Redraw every editor of this tree — call it yourself after changing the data behind the store."""
        for fn in list(_listeners.get(self.key, ())):
            try:
                fn()
            except Exception as e:  # a closed browser tab must not break the others
                print(f'[ngtree] osvežavanje nije uspelo: {e}')
                self.unsubscribe(fn)


class MemoryStore(TreeStore):
    """The tree in memory. nodes: a list of nodes with or without ids ({'label', 'children', 'note'?, 'tag'?}).
    on_change(nodes) is called after every change and undo — save them wherever you keep them.

        store = MemoryStore(load_from_db(), on_change=save_to_db)

    Keep one MemoryStore per tree (e.g. module level) if several pages / browsers should share it live."""

    def __init__(self, nodes: list[dict] | None = None, *, on_change: Callable[[list[dict]], None] | None = None,
                 undo_limit: int = 50, max_nodes: int | None = None, key: str | None = None, **extra) -> None:
        super().__init__(key=key or f'memory-{id(self)}', max_nodes=max_nodes)
        self._doc = ops.new_doc(nodes, **extra)
        self._history: list[dict] = []
        self.undo_limit = undo_limit
        self.on_change = on_change

    @property
    def nodes(self) -> list[dict]:
        return self._doc['nodes']

    def set_nodes(self, nodes: list[dict]) -> None:
        """Replace the whole tree from outside (no undo step); open editors are redrawn."""
        with _lock(self.key):
            self._doc = ops.new_doc(nodes, **{k: v for k, v in self._doc.items() if k not in ('nodes', 'next_id')})
        self.notify()

    def _read(self) -> dict:
        return self._doc

    def _write(self, doc: dict, before: dict) -> None:
        self._history.append(before)
        del self._history[:-self.undo_limit]
        self._doc = doc
        if self.on_change:
            self.on_change(copy.deepcopy(doc['nodes']))

    def _undo(self) -> bool:
        if not self._history:
            return False
        self._doc = self._history.pop()
        if self.on_change:
            self.on_change(copy.deepcopy(self._doc['nodes']))
        return True

    def can_undo(self) -> bool:
        return bool(self._history)


_file_cache: dict[str, tuple[float, dict]] = {}


class JsonFileStore(TreeStore):
    """The tree in a JSON file: {"next_id", "nodes", ...any keys of your app}.

    backup_dir: where the copy before every change goes (default: <file>.backup/ next to the file),
    named <file stem>-<time>.json; the last `backups` are kept and undo walks back through them.
    create=True: a missing file is created as an empty tree (with `extra` keys, e.g. name="Moje stablo")."""

    def __init__(self, path: str | Path, *, backup_dir: str | Path | None = None, backups: int = 50,
                 max_nodes: int | None = None, create: bool = True, **extra) -> None:
        self.path = Path(path).resolve()
        super().__init__(key=f'file:{self.path}', max_nodes=max_nodes)
        self.backup_dir = Path(backup_dir).resolve() if backup_dir else self.path.with_name(self.path.name + '.backup')
        self.keep = backups
        if create and not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._save(ops.new_doc(**extra))

    def _read(self) -> dict | None:
        if not self.path.exists():
            return None
        mtime = self.path.stat().st_mtime
        hit = _file_cache.get(self.key)
        if hit and hit[0] == mtime:
            return hit[1]
        doc = json.loads(self.path.read_text(encoding='utf-8'))
        doc.setdefault('nodes', [])
        doc.setdefault('next_id', max([0] + ops.all_ids(doc['nodes'])) + 1)
        _file_cache[self.key] = (mtime, doc)
        return doc

    def _save(self, doc: dict) -> None:
        tmp = self.path.with_suffix(self.path.suffix + '.tmp')
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')
        os.replace(tmp, self.path)
        _file_cache.pop(self.key, None)

    def _write(self, doc: dict, before: dict) -> None:
        if self.keep and self.path.exists():
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            shutil.copy2(self.path, self.backup_dir / f'{self.path.stem}-{stamp}.json')
            for old in self.backups()[self.keep:]:
                old.unlink(missing_ok=True)
        self._save(doc)

    def backups(self) -> list[Path]:
        """Copies before each change, newest first."""
        if not self.backup_dir.exists():
            return []
        return sorted(self.backup_dir.glob(f'{self.path.stem}-*.json'), reverse=True)

    def _undo(self) -> bool:
        found = self.backups()
        if not found:
            return False
        os.replace(found[0], self.path)
        _file_cache.pop(self.key, None)
        return True

    def can_undo(self) -> bool:
        return bool(self.backups())

    def replace(self, doc: dict, *, clear_backups: bool = False) -> None:
        """Write a whole new document (no backup); clear_backups=True also forgets the undo history."""
        with _lock(self.key):
            if clear_backups and self.backup_dir.exists():
                shutil.rmtree(self.backup_dir)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._save(doc)
        self.notify()
