#!/usr/bin/env python3
"""ngtree demo — three editors on one page, no ngfw needed:

  1. a JSON file (examples/demo-data/primer.json): everything on, undo, live updates
  2. the same file, view only, in English — changes from (1) appear at once
  3. data kept in memory (as if from a database): limited features, on_select shows the clicked node

    pip install nicegui            # or: pip install ../dist/ngtree-*.whl
    python examples/demo.py        # http://localhost:8098
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # run from the source folder too

from nicegui import ui

from ngtree import JsonFileStore, MemoryStore, TreeEditor

HERE = Path(__file__).resolve().parent
FILE = JsonFileStore(HERE / 'demo-data' / 'primer.json', name='Primer')

CATEGORIES = MemoryStore([
    {'label': 'Predmeti', 'children': [
        {'label': 'Izvršenje', 'children': [{'label': 'Komunalne usluge'}, {'label': 'Krediti'}]},
        {'label': 'Parnica', 'note': 'Vidi https://www.paragraf.rs'},
    ]},
    {'label': 'Klijenti', 'children': [{'label': 'JKP'}, {'label': 'Banke'}]},
], on_change=lambda nodes: print('[demo] sačuvaj u bazu:', len(nodes), 'čvorova na vrhu'))


@ui.page('/')
def index() -> None:
    with ui.column().classes('w-full max-w-5xl mx-auto p-4 gap-6'):
        ui.label('ngtree — primer').classes('text-3xl font-bold')

        with ui.card().classes('w-full'):
            ui.label('1. Fajl (JsonFileStore) — sve mogućnosti').classes('text-lg font-semibold')
            TreeEditor(FILE, filename='primer')

        with ui.card().classes('w-full'):
            ui.label('2. Isti fajl — samo pregled, English').classes('text-lg font-semibold')
            TreeEditor(FILE, editable=False, language='en', filename='primer')

        with ui.card().classes('w-full'):
            ui.label('3. U memoriji (MemoryStore) — dodaj / izmeni / prevuci, klik na naziv').classes('text-lg font-semibold')
            picked = ui.label('Kliknite na naziv.').classes('text-sm text-primary')
            TreeEditor(CATEGORIES, features={'add', 'edit', 'delete', 'drag', 'notes', 'undo', 'filter'},
                       texts={'Novi čvor na vrhu': 'Nova kategorija'}, show_stats=False,
                       on_select=lambda n: picked.set_text(f'Izabrano: {n["label"]} (id {n["id"]})'))


if __name__ in {'__main__', '__mp_main__'}:
    ui.run(port=8098, title='ngtree', show=False, reload=False)
