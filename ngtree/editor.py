"""TreeEditor — a tree you change right in the tree view, as one NiceGUI element for any page.

    from ngtree import TreeEditor, JsonFileStore, MemoryStore

    TreeEditor(JsonFileStore('data/org.json'))                                   # file, live, undo
    TreeEditor(MemoryStore(nodes, on_change=save), editable=is_admin(),         # your data, you save
               features={'add', 'edit', 'delete', 'drag', 'notes'}, on_select=show_details)

In the view (when editable): hover a node for  +  ✎  🗑  ⋮ (up / down / sort / to top / import / export
subtree); double click = edit; drag a node onto another (upper quarter = before, middle = inside, lower
quarter = after) or onto the strip under the tree (= top level). Only the tree is redrawn after a change —
in every browser showing the same store. Node ids are stable, so open branches stay open.

The language is fixed per editor (language= 'sr' | 'en' or a function returning it, called once), because
redraws may run in ANOTHER browser's context (the one that made the change).
"""
from __future__ import annotations

import copy
from typing import Any, Callable, Iterable

from nicegui import events, ui

from . import ops
from .i18n import translate
from .ops import TreeError
from .stores import TreeStore
from .text import fold, slugify

FEATURES = frozenset({'add', 'edit', 'delete', 'move', 'drag', 'sort', 'notes', 'tags',
                      'import', 'export', 'undo', 'filter'})

CSS = '''
.st-node { border-top: 2px solid transparent; border-bottom: 2px solid transparent; border-radius: 4px; padding: 0 4px; }
.st-node.dz-before { border-top-color: var(--q-primary); }
.st-node.dz-after  { border-bottom-color: var(--q-primary); }
.st-node.dz-inside { background: rgba(127, 127, 127, .18); }
.st-actions { visibility: hidden; }
.q-tree__node-header:hover .st-actions { visibility: visible; }
@media (hover: none) { .st-actions { visibility: visible; } }
.st-note { white-space: pre-wrap; overflow-wrap: anywhere; font-size: .9rem; line-height: 1.45; }
.st-note a { text-decoration: underline; }
.st-top-drop.dz-inside { background: rgba(127, 127, 127, .18); border-color: var(--q-primary); }
'''

# ---------------------------------------------------------------- the node template (Vue, runs in the browser)
# The server only gets 'act' {a, id}, 'move' {src, dst, where} and 'select' id events.

_DRAG = r'''draggable="true"
     @dragstart.stop="(e) => { e.dataTransfer.setData('text/plain', '@@TREE@@:' + props.node.id); e.dataTransfer.effectAllowed = 'move'; }"
     @dragover.prevent.stop="(e) => { const el = e.currentTarget, r = el.getBoundingClientRect(), y = (e.clientY - r.top) / r.height;
                                        el.dataset.where = y < 0.25 ? 'before' : y > 0.75 ? 'after' : 'inside';
                                        el.classList.remove('dz-before', 'dz-after', 'dz-inside'); el.classList.add('dz-' + el.dataset.where); }"
     @dragleave="(e) => e.currentTarget.classList.remove('dz-before', 'dz-after', 'dz-inside')"
     @drop.prevent.stop="(e) => { const el = e.currentTarget, w = el.dataset.where || 'inside', d = e.dataTransfer.getData('text/plain').split(':');
                                  el.classList.remove('dz-before', 'dz-after', 'dz-inside');
                                  if (d.length === 2 && d[0] === '@@TREE@@' && Number(d[1]) !== props.node.id)
                                      $parent.$emit('move', {src: Number(d[1]), dst: props.node.id, where: w}); }"'''

_DBLCLICK = r'''@dblclick.stop="() => $parent.$emit('act', {a: 'edit', id: props.node.id})"'''

_LABEL = r'''<span :class="props.node.hit ? 'text-weight-bold text-primary' : ''">{{ props.node.label }}</span>'''
_LABEL_SELECT = r'''<span class="cursor-pointer" :class="props.node.hit ? 'text-weight-bold text-primary' : ''"
        @click.stop="() => $parent.$emit('select', props.node.id)">{{ props.node.label }}</span>'''

_NOTE = r'''<q-icon v-if="props.node.note" name="sticky_note_2" size="xs" color="grey-7" class="q-ml-xs cursor-pointer"
          @click.stop @dblclick.stop @mousedown.stop>
    <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 6]">@@NOTE@@</q-tooltip>
    <q-menu anchor="bottom left" self="top left" max-width="32rem">
      <div class="st-note q-pa-md" @click.stop @dblclick.stop>
        <template v-for="(part, i) in props.node.note.split(/((?:https?:\/\/|www\.)[^\s\x3c\x3e\x22\x27]*[^\s\x3c\x3e\x22\x27.,;:!?)\]])/g)" :key="i">
          <a v-if="i % 2" :href="part.startsWith('www.') ? 'https://' + part : part" target="_blank"
             rel="noopener noreferrer" class="text-primary">{{ part }}</a>
          <template v-else>{{ part }}</template>
        </template>
      </div>
    </q-menu>
  </q-icon>'''

_REST = r'''<q-badge v-if="props.node.tag" outline color="primary" class="q-ml-sm">{{ props.node.tag }}</q-badge>
  <span v-if="props.node.children && props.node.children.length" class="text-caption text-grey-6 q-ml-xs">({{ props.node.children.length }})</span>'''

_BTN = r'''<q-btn flat dense round size="sm" icon="{icon}" color="{color}" @click.stop="() => $parent.$emit('act', {{a: '{a}', id: props.node.id}})"><q-tooltip>@@{key}@@</q-tooltip></q-btn>'''
_ITEM = r'''<q-item clickable @click="() => $parent.$emit('act', {{a: '{a}', id: props.node.id}})"><q-item-section avatar><q-icon name="{icon}" /></q-item-section><q-item-section>@@{key}@@</q-item-section></q-item>'''

SLOT_TEXTS = {
    'ADD': 'Dodaj podčvor', 'EDIT': 'Izmeni', 'DELETE': 'Obriši', 'UP': 'Pomeri gore', 'DOWN': 'Pomeri dole',
    'SORT': 'Sortiraj podčvorove', 'TOP': 'Premesti na vrh stabla', 'IMPORT': 'Uvezi ispod ovog čvora…',
    'EXPORT_TXT': 'Izvezi podstablo — tekst (.txt)', 'EXPORT_JSON': 'Izvezi podstablo — JSON',
    'NOTE': 'Beleška — kliknite da je otvorite (linkovi se otvaraju u novoj kartici)',
}

FAIL = object()  # what _run() returns when a change was refused


class TreeEditor(ui.column):
    """A tree editor for any page.

    store       where the tree lives: JsonFileStore, MemoryStore or your own TreeStore
    editable    True / False, or a function (document) -> bool, asked again before every change
                (so taking away the right works at once)
    can_view    optional function (document) -> bool; False = the tree is emptied with a message
    features    which parts to offer (default: all of FEATURES): add, edit, delete, move (up / down / to top),
                drag, sort, notes, tags, import, export, undo, filter
    language    'sr' | 'en', or a function returning it (called once)
    texts       {Serbian text: your text} — replace any text of the editor
    on_change   function(nodes) after every change made in THIS editor
    on_select   function(node) when a name is clicked (the name becomes clickable)
    menu_extra  function(T) called inside the ⋮ menu at the top, to add your own ui.menu_item(...)s;
                T translates with the editor's language
    filename    base name for downloads ('stablo' -> stablo.txt, stablo-<node>.json)
    show_stats, hint, help_url   the "N čvorova · …" line, the help line under the toolbar, a guide link
    expand      'top' (top level open), 'all' or 'none'
    """

    def __init__(self, store: TreeStore, *, editable: bool | Callable[[dict], bool] = True,
                 can_view: Callable[[dict], bool] | None = None, features: Iterable[str] | None = None,
                 language: str | Callable[[], str] = 'sr', texts: dict[str, str] | None = None,
                 on_change: Callable[[list[dict]], None] | None = None,
                 on_select: Callable[[dict], None] | None = None,
                 menu_extra: Callable[[Callable[[str], str]], None] | None = None,
                 filename: str = 'stablo', show_stats: bool = True, hint: bool = True,
                 help_url: str | None = None, expand: str = 'top') -> None:
        super().__init__()
        self.classes('w-full gap-2')
        self.store = store
        self.language = language() if callable(language) else (language or 'sr')
        self.texts = texts or {}
        self.features = FEATURES if features is None else frozenset(features) & FEATURES
        unknown = set(features or ()) - FEATURES
        if unknown:
            raise ValueError(f'Nepoznate mogućnosti: {", ".join(sorted(unknown))} (postoje: {", ".join(sorted(FEATURES))})')
        self._editable = editable
        self._can_view = can_view
        self.on_change = on_change
        self.on_select = on_select
        self.filename = filename
        self._dialog_open = False

        doc = store.load() or ops.new_doc()
        self.editable = self._may_edit(doc)
        e, f = self.editable, self.features
        T = self.T
        ui.add_css(CSS)

        with self:
            # ---------------------------------------------------------- toolbar
            self._stats = ui.label().classes('text-sm text-grey-7')
            self._stats.set_visibility(show_stats)
            with ui.row().classes('w-full items-center gap-2'):
                self._filter = ui.input(T('Filter')).props('outlined dense clearable debounce=300').classes('w-64')
                self._filter.set_visibility('filter' in f)
                if e and 'add' in f:
                    ui.button(T('Novi čvor na vrhu'), icon='add', on_click=lambda: self._node_dialog(None, None)) \
                        .props('unelevated color=primary no-caps')
                ui.button(icon='unfold_more', on_click=self.expand_all).props('flat round color=grey-8').tooltip(T('Otvori sve'))
                ui.button(icon='unfold_less', on_click=self.collapse_all).props('flat round color=grey-8').tooltip(T('Zatvori sve'))
                self._found = ui.label().classes('text-sm text-grey-7')
                right = ui.row().classes('items-center gap-1 no-wrap ml-auto')  # Undo and ⋮ stay together
            with right:
                self._undo_btn = ui.button(T('Poništi'), icon='undo', on_click=self._do_undo) \
                    .props('flat no-caps color=grey-9').tooltip(T('Vraća poslednju izmenu (svaki klik jednu)'))
                self._undo_btn.set_visibility(e and 'undo' in f)
                has_menu = (e and ('import' in f or 'sort' in f)) or 'export' in f or menu_extra
                if has_menu:
                    with ui.button(icon='more_vert').props('flat round color=grey-9'):
                        with ui.menu():
                            if e and 'import' in f:
                                ui.menu_item(T('Uvezi (zameni celo stablo)…'), on_click=lambda: self._import_dialog(None, True))
                                ui.menu_item(T('Uvezi na vrh stabla…'), on_click=lambda: self._import_dialog(None, False))
                                ui.separator()
                            if 'export' in f:
                                ui.menu_item(T('Izvezi kao tekst (putanje)'), on_click=lambda: self.download('txt'))
                                ui.menu_item(T('Izvezi kao JSON'), on_click=lambda: self.download('json'))
                            if e and 'sort' in f:
                                ui.separator()
                                ui.menu_item(T('Sortiraj vrh stabla'), on_click=lambda: self._run(ops.sort_children, None))
                            if menu_extra:
                                ui.separator()
                                menu_extra(T)
            if hint:
                with ui.row().classes('items-center gap-2'):
                    if e:
                        text = ('Pređite mišem preko čvora za dugmad · dupli klik = izmena · prevucite čvor na drugi: '
                                'gore = ispred, sredina = unutra, dole = iza.')
                    elif 'export' in f:
                        text = 'Samo pregled — kliknite na 🗒 da pročitate belešku; ⋮ pored čvora izvozi njegovo podstablo.'
                    else:
                        text = 'Samo pregled.'
                    ui.label(T(text)).classes('text-xs text-grey-7')
                    if help_url:
                        ui.link(T('Uputstvo →'), help_url).classes('text-xs')

            # ---------------------------------------------------------- the tree
            empty = T('Stablo je prazno — dodajte prvi čvor.' if e and 'add' in f else 'Stablo je prazno.').replace('"', '')
            self.tree = ui.tree(doc['nodes'], node_key='id', label_key='label') \
                .classes('w-full').props(f'dense no-transition no-nodes-label="{empty}"')
            self.tree.props(f'no-results-label="{T("Nema rezultata.")}"')
            self.tree.add_slot('default-header', self._slot())
            if expand == 'all':
                self.tree.props['expanded'] = ops.all_ids(doc['nodes'])
            elif expand == 'top':
                self.tree.props['expanded'] = [n['id'] for n in doc['nodes']]
            self.tree.on('act', self._on_act)
            self.tree.on('move', self._on_move)
            if on_select:
                self.tree.on('select', self._on_select)

            if e and 'drag' in f:
                tag = self._drag_tag()
                drop = ui.label(T('⤒ Prevucite čvor ovde da postane čvor na vrhu stabla')) \
                    .classes('st-top-drop w-full text-center text-sm text-grey-6 border-2 border-dashed rounded p-2 mt-2')
                drop.on('dragover.prevent', js_handler='(e) => e.currentTarget.classList.add("dz-inside")')
                drop.on('dragleave', js_handler='(e) => e.currentTarget.classList.remove("dz-inside")')
                drop.on('drop.prevent', lambda ev: self._run(ops.move, int(ev.args), None),
                        js_handler='(e) => { e.currentTarget.classList.remove("dz-inside"); '
                                   'const d = e.dataTransfer.getData("text/plain").split(":"); '
                                   f'if (d.length === 2 && d[0] === "{tag}") emit(Number(d[1])); }}')

        self._filter.on_value_change(self._on_filter)
        store.subscribe(self.refresh)
        ui.context.client.on_delete(lambda: store.unsubscribe(self.refresh))
        self.refresh()

    # ---------------------------------------------------------------- public
    def T(self, text: str) -> str:
        """Translate with this editor's language and texts."""
        return translate(text, self.language, self.texts)

    @property
    def nodes(self) -> list[dict]:
        """The current nodes (a copy)."""
        doc = self.store.load()
        return copy.deepcopy(doc['nodes']) if doc else []

    def refresh(self) -> None:
        """Redraw from the store (done automatically after every change). Runs also from other browsers' events:
        no translations by the current language here, only self.T."""
        doc = self.store.load()
        if doc is None or (self._can_view and not self._can_view(doc)):
            self.tree.props['nodes'] = []
            self.tree.update()
            self._stats.text = self.T('Stablo je obrisano.') if doc is None else self.T('Ovo stablo vam više nije dostupno.')
            return
        s = ops.stats(doc['nodes'])
        self._stats.text = self.T('{0} čvorova · {1} listova · dubina {2}').format(s['nodes'], s['leaves'], s['depth'])
        query = (self._filter.value or '').strip()
        if len(fold(query)) >= 2:
            nodes, expand, n = ops.filter_tree(doc['nodes'], query)
            self.tree.props['nodes'] = nodes
            self.tree.props['expanded'] = sorted(set(self.tree.props.get('expanded') or []) | set(expand))
            self._found.text = self.T('Pronađeno: {0}').format(n) + ('+' if n >= ops.MAX_FILTER_MATCHES else '')
        else:
            self.tree.props['nodes'] = doc['nodes']
            self._found.text = ''
        self._undo_btn.set_enabled(self.store.can_undo())
        self.tree.update()

    def expand_all(self) -> None:
        self.tree.props['expanded'] = ops.all_ids(self.tree.props['nodes'])
        self.tree.update()

    def collapse_all(self) -> None:
        self.tree.props['expanded'] = []
        self.tree.update()

    def set_filter(self, text: str) -> None:
        self._filter.value = text

    def open_node(self, node_id: int, include_self: bool = False) -> None:
        """Open the branches down to a node."""
        doc = self.store.load() or ops.new_doc()
        ids = ops.path_ids(doc['nodes'], node_id) + ([node_id] if include_self else [])
        self.tree.props['expanded'] = sorted(set(self.tree.props.get('expanded') or []) | set(ids))
        self.tree.update()

    def download(self, kind: str, node_id: int | None = None) -> None:
        """'txt' or 'json'; the whole tree, or (node_id) that node with everything under it."""
        doc = self.store.load()
        if not doc or (self._can_view and not self._can_view(doc)):
            return
        name = self.filename
        if node_id is not None:
            n = ops.node(doc, node_id)
            if n is None:
                ui.notify(self.T('Taj čvor više ne postoji.'), type='warning')
                return
            name = f'{self.filename}-{slugify(n["label"]) or node_id}'
        try:
            if kind == 'txt':
                ui.download.content(ops.export_paths(doc, node_id), f'{name}.txt', 'text/plain; charset=utf-8')
            else:
                ui.download.content(ops.export_json(doc, node_id), f'{name}.json', 'application/json')
        except TreeError as e:
            ui.notify(self._error(e), type='warning')

    # ---------------------------------------------------------------- template
    def _drag_tag(self) -> str:
        return f't{self.tree.id}'  # nodes can be dropped only within the same tree

    def _slot(self) -> str:
        e, f = self.editable, self.features
        drag = _DRAG.replace('@@TREE@@', self._drag_tag()) if e and 'drag' in f else ''
        dbl = _DBLCLICK if e and 'edit' in f else ''
        buttons, items = [], []
        if e:
            if 'add' in f:
                buttons.append(_BTN.format(icon='add', color='primary', a='add', key='ADD'))
            if 'edit' in f:
                buttons.append(_BTN.format(icon='edit', color='grey-8', a='edit', key='EDIT'))
            if 'delete' in f:
                buttons.append(_BTN.format(icon='delete_outline', color='negative', a='delete', key='DELETE'))
            if 'move' in f:
                items += [_ITEM.format(a='up', icon='arrow_upward', key='UP'),
                          _ITEM.format(a='down', icon='arrow_downward', key='DOWN')]
            if 'sort' in f:
                items.append(_ITEM.format(a='sort', icon='sort_by_alpha', key='SORT'))
            if 'move' in f:
                items.append(_ITEM.format(a='top', icon='vertical_align_top', key='TOP'))
            if 'import' in f:
                items.append(_ITEM.format(a='import', icon='upload_file', key='IMPORT'))
        if 'export' in f:
            if items:
                items.append('<q-separator />')
            items += [_ITEM.format(a='export_txt', icon='download', key='EXPORT_TXT'),
                      _ITEM.format(a='export_json', icon='data_object', key='EXPORT_JSON')]
        menu = ''
        if items:
            menu = ('<q-btn flat dense round size="sm" icon="more_vert" color="grey-8" @click.stop>'
                    '<q-menu auto-close><q-list dense style="min-width: 12rem">' + ''.join(items) +
                    '</q-list></q-menu></q-btn>')
        actions = f'<span class="st-actions row no-wrap q-ml-sm">{"".join(buttons)}{menu}</span>' if buttons or menu else ''
        slot = (f'<div class="st-node row items-center no-wrap" {drag} {dbl}>\n  '
                f'{_LABEL_SELECT if self.on_select else _LABEL}\n  {_NOTE}\n  {_REST}\n  {actions}\n</div>')
        for key, text in SLOT_TEXTS.items():
            slot = slot.replace(f'@@{key}@@', self.T(text).replace('<', '&lt;'))
        return slot

    # ---------------------------------------------------------------- changes
    def _may_edit(self, doc: dict | None) -> bool:
        if doc is None:
            return False
        if self._can_view and not self._can_view(doc):
            return False
        return bool(self._editable(doc) if callable(self._editable) else self._editable)

    def _error(self, e: TreeError) -> str:
        return self.T(e.text).format(*e.values)

    def _run(self, fn: Callable[..., Any], *args) -> Any:
        """ops function on the store (fn(doc, *args)); errors become a notification and FAIL is returned."""
        if not self._may_edit(self.store.load()):
            ui.notify(self.T('Nemate pravo da menjate ovo stablo.'), type='warning')
            return FAIL
        try:
            result = self.store.change(lambda doc: fn(doc, *args))
        except TreeError as e:
            ui.notify(self._error(e), type='warning')
            self.refresh()  # someone else may have changed the tree: show the current state
            return FAIL
        if self.on_change:
            self.on_change(self.nodes)
        return result

    def _do_undo(self) -> None:
        if not self._may_edit(self.store.load()):
            ui.notify(self.T('Nemate pravo da menjate ovo stablo.'), type='warning')
            return
        if not self.store.undo():
            ui.notify(self.T('Nema ranijih verzija.'), type='info')
        elif self.on_change:
            self.on_change(self.nodes)

    def _node(self, node_id: int) -> dict | None:
        doc = self.store.load()
        return ops.node(doc, node_id) if doc else None

    def _label(self, node_id: int) -> str:
        n = self._node(node_id)
        return n['label'] if n else '?'

    async def _on_act(self, e: events.GenericEventArguments) -> None:
        a, node_id = e.args['a'], int(e.args['id'])
        if a in ('export_txt', 'export_json'):
            if 'export' in self.features:
                self.download(a[7:], node_id)
            return
        if not self.editable:
            return
        n = self._node(node_id)
        if n is None:
            ui.notify(self.T('Taj čvor više ne postoji.'), type='warning')
            self.refresh()
            return
        if a == 'add':
            self._node_dialog(node_id, None)
        elif a == 'edit':
            self._node_dialog(None, n)
        elif a == 'delete':
            k = ops.count(n.get('children', []))
            question = (self.T('Obrisati „{0}” i svih {1} čvorova ispod njega?').format(n['label'], k) if k
                        else self.T('Obrisati „{0}”?').format(n['label']))
            if 'undo' in self.features:
                question += ' ' + self.T('(Može se vratiti dugmetom Poništi.)')
            if await self._confirm(question, self.T('Obriši')):
                self._run(ops.delete, node_id)
        elif a in ('up', 'down'):
            self._run(ops.shift, node_id, -1 if a == 'up' else 1)
        elif a == 'sort':
            self._run(ops.sort_children, node_id)
        elif a == 'top':
            self._run(ops.move, node_id, None)
        elif a == 'import':
            self._import_dialog(node_id, False)

    def _on_move(self, e: events.GenericEventArguments) -> None:
        if not (self.editable and 'drag' in self.features):
            return
        src, dst, where = int(e.args['src']), int(e.args['dst']), e.args['where']
        if self._run(ops.move, src, dst, where) is not FAIL and where == 'inside':
            self.open_node(dst, include_self=True)

    def _on_select(self, e: events.GenericEventArguments) -> None:
        n = self._node(int(e.args))
        if n is not None and self.on_select:
            self.on_select(copy.deepcopy(n))

    def _on_filter(self, _e) -> None:
        if len(fold(self._filter.value or '')) < 2:
            self.tree.props['expanded'] = [n['id'] for n in (self.store.load() or ops.new_doc())['nodes']]
        else:
            self.tree.props['expanded'] = []
        self.refresh()

    # ---------------------------------------------------------------- dialogs
    async def _confirm(self, message: str, ok_text: str) -> bool:
        with ui.dialog() as dlg, ui.card().classes('w-[28rem] max-w-full'):
            ui.label(self.T('Potvrda')).classes('text-lg font-semibold')
            ui.label(message)
            with ui.row().classes('w-full justify-end'):
                ui.button(self.T('Otkaži'), on_click=lambda: dlg.submit(False)).props('flat no-caps')
                ui.button(ok_text, on_click=lambda: dlg.submit(True)).props('unelevated color=negative no-caps')
        result = await dlg
        dlg.delete()
        return bool(result)

    def _node_dialog(self, parent_id: int | None, n: dict | None) -> None:
        """New child of parent_id (n None) or edit n."""
        if self._dialog_open or not self.editable:
            return
        self._dialog_open = True
        T, f = self.T, self.features
        with ui.dialog() as dlg, ui.card().classes('w-[32rem] max-w-full'):
            if n:
                ui.label(T('Izmena čvora')).classes('text-lg font-semibold')
            elif parent_id is None:
                ui.label(T('Novi čvor na vrhu stabla')).classes('text-lg font-semibold')
            else:
                ui.label(T('Novi čvor ispod „{0}”').format(self._label(parent_id))).classes('text-lg font-semibold')
            label = ui.input(T('Naziv'), value=n['label'] if n else '').props('outlined autofocus').classes('w-full')
            note = ui.textarea(T('Beleška (nije obavezna) — adrese (https://…, www.…) postaju linkovi'),
                               value=(n or {}).get('note', '')).props('outlined autogrow').classes('w-full') \
                if 'notes' in f else None
            tag = ui.input(T('Oznaka grane (nije obavezna)'), value=(n or {}).get('tag', '')) \
                .props('outlined dense').classes('w-full') if n and 'tags' in f else None

            def save(keep_open: bool = False) -> None:
                note_text = (note.value or '') if note else None
                if n:
                    if self._run(ops.update, n['id'], label.value or '', note_text, (tag.value or '') if tag else None) is not FAIL:
                        dlg.close()
                    return
                if self._run(ops.add, parent_id, label.value or '', note_text or '') is FAIL:
                    return
                if parent_id is not None:
                    self.open_node(parent_id, include_self=True)
                if keep_open:
                    label.value = ''
                    if note:
                        note.value = ''
                    label.run_method('focus')
                else:
                    dlg.close()

            label.on('keydown.enter', lambda: save(keep_open=not n))
            with ui.row().classes('w-full justify-end'):
                ui.button(T('Otkaži'), on_click=dlg.close).props('flat no-caps')
                if not n:
                    ui.button(T('Dodaj i nastavi'), on_click=lambda: save(True)).props('outline color=primary no-caps') \
                        .tooltip(T('Enter u nazivu radi isto — za brzo dodavanje više čvorova'))
                ui.button(T('Sačuvaj') if n else T('Dodaj'), on_click=lambda: save(False)) \
                    .props('unelevated color=primary no-caps')

        def closed() -> None:
            self._dialog_open = False
            dlg.delete()

        dlg.on('hide', closed)
        dlg.open()

    def _import_dialog(self, parent_id: int | None, replace: bool) -> None:
        T = self.T
        with ui.dialog() as dlg, ui.card().classes('w-[34rem] max-w-full'):
            if replace:
                ui.label(T('Uvoz — zamenjuje celo stablo')).classes('text-lg font-semibold')
            elif parent_id is None:
                ui.label(T('Uvoz na vrh stabla')).classes('text-lg font-semibold')
            else:
                ui.label(T('Uvoz ispod „{0}”').format(self._label(parent_id))).classes('text-lg font-semibold')
            ui.markdown(T('**.txt**: jedan red = jedna putanja, nazivi odvojeni zarezom (kao pasovi.txt): '
                          '`Koren,Dete,Unuče`. Redovi sa istim početkom dele čvorove. '
                          'Red VELIKIM SLOVIMA je oznaka grane.  \n'
                          '**.json**: fajl izvezen iz ove aplikacije.')).classes('text-sm text-grey-8')

            async def handle(ev: events.UploadEventArguments) -> None:
                text = await ev.file.text()
                try:
                    nodes = ops.parse_json(text) if (ev.file.name or '').lower().endswith('.json') else ops.parse_paths(text)
                except TreeError as err:
                    ui.notify(self._error(err), type='warning')
                    return
                added = self._run(ops.insert_nodes, nodes, parent_id, replace)
                if added is not FAIL:
                    if parent_id is not None:
                        self.open_node(parent_id, include_self=True)
                    ui.notify(T('Uvezeno čvorova: {0}').format(added), type='positive')
                    dlg.close()

            ui.upload(on_upload=handle, auto_upload=True, max_files=1) \
                .props('accept=".txt,.json" flat bordered').classes('w-full')
            with ui.row().classes('w-full justify-end'):
                ui.button(T('Zatvori'), on_click=dlg.close).props('flat no-caps')
        dlg.on('hide', dlg.delete)
        dlg.open()
