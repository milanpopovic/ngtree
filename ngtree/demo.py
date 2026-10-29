"""ngtree demo — three editors on one page:

  1. a JSON file: everything on, undo, live updates in every browser
  2. the same file, view only, in English — changes from (1) appear at once
  3. data kept in memory (as if from a database): limited features, a click on a name shows the node

    ngtree-demo                         # after: pip install "git+https://github.com/milanpopovic/ngtree"
    ngtree-demo --port 8100 --data /tmp/demo
    python -m ngtree.demo               # the same
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from nicegui import ui

from . import ops
from .editor import TreeEditor
from .stores import JsonFileStore, MemoryStore

SAMPLE = [
    {'label': 'Evropa', 'tag': 'Evropa', 'children': [
        {'label': 'Srbija', 'note': 'https://sr.wikipedia.org/wiki/Србија', 'children': [
            {'label': 'Beograd'}, {'label': 'Novi Sad'}, {'label': 'Niš'}]},
        {'label': 'Nemačka', 'children': [{'label': 'Berlin'}, {'label': 'Minhen'}]},
    ]},
    {'label': 'Azija', 'children': [{'label': 'Japan', 'children': [{'label': 'Tokio'}]}]},
]

CATEGORIES = [
    {'label': 'Predmeti', 'children': [
        {'label': 'Izvršenje', 'children': [{'label': 'Komunalne usluge'}, {'label': 'Krediti'}]},
        {'label': 'Parnica', 'note': 'Vidi https://www.paragraf.rs'},
    ]},
    {'label': 'Klijenti', 'children': [{'label': 'JKP'}, {'label': 'Banke'}]},
]


def build(data: Path) -> None:
    """Register the demo page; the tree file lives in `data` (made with a sample tree the first time)."""
    path = data / 'primer.json'
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(ops.new_doc(SAMPLE, name='Primer'), ensure_ascii=False, indent=1),
                        encoding='utf-8')
    file_store = JsonFileStore(path)
    memory = MemoryStore(CATEGORIES, on_change=lambda nodes: print('[demo] save to database:', len(nodes),
                                                                   'top-level nodes'))

    @ui.page('/')
    def index() -> None:
        with ui.column().classes('w-full max-w-5xl mx-auto p-4 gap-6'):
            ui.label('ngtree — primer / demo').classes('text-3xl font-bold')
            ui.markdown('Pređite mišem preko čvora za **+ ✎ 🗑 ⋮**, prevucite naziv na drugi čvor. '
                        'Otvorite stranu u još jednom prozoru: izmene se vide odmah.  \n'
                        'Hover a node for **+ ✎ 🗑 ⋮**, drag a name onto another node. Open the page in a second '
                        'window: changes show up at once.').classes('text-sm text-gray-600')

            with ui.card().classes('w-full'):
                ui.label('1. Fajl (JsonFileStore) — sve mogućnosti').classes('text-lg font-semibold')
                TreeEditor(file_store, filename='primer')

            with ui.card().classes('w-full'):
                ui.label('2. The same file — view only, English').classes('text-lg font-semibold')
                TreeEditor(file_store, editable=False, language='en', filename='primer')

            with ui.card().classes('w-full'):
                ui.label('3. U memoriji (MemoryStore) — dodaj / izmeni / prevuci, klik na naziv'
                         ).classes('text-lg font-semibold')
                picked = ui.label('Kliknite na naziv.').classes('text-sm text-primary')
                TreeEditor(memory, features={'add', 'edit', 'delete', 'drag', 'notes', 'undo', 'filter'},
                           texts={'Novi čvor na vrhu': 'Nova kategorija'}, show_stats=False,
                           on_select=lambda n: picked.set_text(f'Izabrano: {n["label"]} (id {n["id"]})'))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog='ngtree-demo', description='ngtree TreeEditor demo')
    p.add_argument('--host', default='0.0.0.0')
    p.add_argument('--port', type=int, default=8098)
    p.add_argument('--data', default='ngtree-demo-data', help='folder for the demo tree file (default: %(default)s)')
    a = p.parse_args(argv)
    build(Path(a.data))
    print(f'ngtree demo: http://localhost:{a.port}  (data: {Path(a.data).resolve()})')
    ui.run(host=a.host, port=a.port, title='ngtree demo', show=False, reload=False)


if __name__ in {'__main__', '__mp_main__'}:
    main()
