# ngtree — stablo kao NiceGUI element

`TreeEditor` je ceo uređivač stabla iz aplikacije **stabla** kao jedan NiceGUI element: ubacite ga na bilo koju
stranicu, a vi odlučujete gde se stablo čuva, ko sme da ga menja i koje mogućnosti se vide.

Isti kod postoji na dva načina:

| | uvoz | za koga |
| --- | --- | --- |
| **ngtree** (ovaj paket) | `from ngtree import TreeEditor, JsonFileStore, MemoryStore` | bilo koja NiceGUI aplikacija, bez ngfw-a |
| **ngfw 0.4+** | `from ngfw.tree import TreeEditor, JsonFileStore, MemoryStore` | aplikacije na ngfw-u (jkp, Dunav, kalendar, rodoslovi, stabla) |

Izvorni kod je samo ovde (`ngtree/`); `bash build.sh --ngfw` ga kopira u ngfw
([milanpopovic/ngfw](https://github.com/milanpopovic/ngfw), `ngfw/tree/`).

```bash
pip install "ngtree @ git+https://github.com/milanpopovic/ngtree@v0.1.0"   # ili wheel iz GitHub release-a
```

## Primer

```python
from nicegui import ui
from ngtree import TreeEditor, JsonFileStore, MemoryStore

ORG = JsonFileStore('data/organizacija.json', name='Organizacija')      # fajl — pravi se ako ne postoji

@ui.page('/')
def index():
    TreeEditor(ORG)                                                     # sve mogućnosti
    TreeEditor(ORG, editable=False, language='en')                      # isti fajl, samo pregled, engleski

    store = MemoryStore(ucitaj_iz_baze(), on_change=sacuvaj_u_bazu)    # vaši podaci
    TreeEditor(store, features={'add', 'edit', 'delete', 'drag'},
               on_select=lambda node: ui.notify(node['label']))

ui.run()
```

Ceo primer sa tri stabla na jednoj strani: `python examples/demo.py` → http://localhost:8098

## U stablu (kad sme da se menja)

- pređite mišem preko čvora: **+** podčvor · **✎** izmena · **🗑** brisanje · **⋮** gore / dole / sortiraj /
  na vrh / uvezi ispod / izvezi podstablo (na telefonu su dugmad uvek vidljiva)
- dupli klik na naziv = izmena; Enter u prozoru za novi čvor = dodaj i nastavi
- prevucite naziv na drugi čvor: gornja četvrtina = ispred, sredina = unutra, donja = iza; traka ispod = na vrh
- 🗒 otvara belešku; adrese (`https://…`, `www.…`) su linkovi koji se otvaraju u novoj kartici
- filter (ne razlikuje velika/mala slova, kvačice ni pismo: Staniša = Stanisa = Станиша), **Poništi**
- **⋮** gore: uvoz (.txt putanje kao pasovi.txt, ili JSON; celo stablo, na vrh ili ispod čvora), izvoz

Posle svake izmene osvežava se samo stablo — u svim pregledačima koji prikazuju isti store; otvorene grane
ostaju otvorene (id čvorova se ne menjaju).

## TreeEditor

| parametar | značenje |
| --- | --- |
| `store` | gde je stablo: `JsonFileStore`, `MemoryStore` ili vaš `TreeStore` |
| `editable` | `True` / `False`, ili funkcija `(dokument) -> bool` — pita se pre **svake** izmene, pa oduzeto pravo važi odmah |
| `can_view` | funkcija `(dokument) -> bool`; `False` = stablo se isprazni uz poruku |
| `features` | skup od: `add edit delete move drag sort notes tags import export undo filter` (podrazumevano sve) |
| `language` | `'sr'` / `'en'` ili funkcija koja ga vraća (poziva se jednom) |
| `texts` | `{srpski tekst: vaš tekst}` — zamena bilo kog teksta, npr. `{'Novi čvor na vrhu': 'Nova kategorija'}` |
| `on_change` | `funkcija(nodes)` posle svake izmene napravljene u ovom uređivaču |
| `on_select` | `funkcija(node)` na klik na naziv (naziv postaje klikabilan) |
| `menu_extra` | `funkcija(T)` — dodaje vaše `ui.menu_item(...)` u **⋮** meni gore; `T` prevodi jezikom uređivača |
| `filename` | osnova imena za preuzimanje (`stablo.txt`, `stablo-<čvor>.json`) |
| `show_stats`, `hint`, `help_url` | red „N čvorova · …”, red sa uputstvom, link „Uputstvo →” |
| `expand` | `'top'` (podrazumevano), `'all'`, `'none'` |

Metode: `nodes` (kopija), `refresh()`, `expand_all()`, `collapse_all()`, `set_filter(tekst)`,
`open_node(id)`, `download('txt' | 'json', node_id=None)`, `T(tekst)`.

## Store-ovi

**`JsonFileStore(path, backup_dir=None, backups=50, max_nodes=None, create=True, **extra)`** — fajl
`{"next_id", "nodes", ...}`; ostali ključevi (naziv, vlasnik…) pripadaju aplikaciji i ne diraju se. Pre svake
izmene kopija u `backup_dir` (podrazumevano `<fajl>.backup/`, imena `<ime fajla>-<vreme>.json`); **Poništi**
ide unazad kroz njih. `replace(doc, clear_backups=False)` upisuje ceo novi dokument.
Svi `JsonFileStore`-ovi za isti fajl dele zaključavanje i žive izmene.

**`MemoryStore(nodes=None, on_change=None, undo_limit=50, max_nodes=None, **extra)`** — stablo u memoriji;
`nodes` sa ili bez `id`-jeva (`{'label', 'children', 'note'?, 'tag'?}`). `on_change(nodes)` posle svake izmene i
poništavanja — tu čuvate u bazu. Jedan `MemoryStore` po stablu (npr. na nivou modula) ako više stranica /
pregledača treba da ga deli uživo. `set_nodes(nodes)` zamenjuje stablo spolja.

**Svoj store** (npr. SQLite tabela):

```python
from ngtree import TreeStore, ops

class SqlStore(TreeStore):
    def __init__(self, tree_id):
        super().__init__(key=f'sql:{tree_id}')
        self.tree_id = tree_id
    def _read(self):                 # dokument {"next_id", "nodes"} ili None
        return ops.new_doc(ucitaj_cvorove(self.tree_id))
    def _write(self, doc, before):   # sačuvaj doc['nodes']
        sacuvaj_cvorove(self.tree_id, doc['nodes'])
```

Svaka izmena ide kroz `store.change(fn)`: `fn` dobija svežu kopiju dokumenta i menja je funkcijama iz `ops`
(`ops.add`, `ops.move`, …); ako baci `TreeError`, ništa se ne čuva. Posle izmene napravljene van uređivača
pozovite `store.notify()` da se stabla osveže.

## ops — bez UI-ja

`add, update, delete, shift, move, sort_children, insert_nodes, parse_paths, parse_json, export_paths,
export_json, subtree, filter_tree, stats, count, all_ids, path_ids, path_labels, find, node, new_doc, normalize`
— za skripte, testove i uvoz.

## Wheel

```bash
bash build.sh                  # dist/ngtree-<verzija>-py3-none-any.whl
bash build.sh --ngfw           # + isti kod u <ngfw>/ngfw/tree/ (pa nova verzija ngfw-a)
```

Folder ngfw-a: promenljiva `NGFW_DIR`, ili putanja u fajlu `ngfw.local` (nije u git-u), ili `../ngfw`.

U aplikaciji bez ngfw-a: wheel u `wheels/`, u requirements.txt `./wheels/ngtree-0.1.0-py3-none-any.whl`.
Zavisi samo od `nicegui>=3.15,<4`.

## Ograničenja

- Čvor se ne može prevući iz jednog stabla u drugo (svako stablo prima samo svoje čvorove).
- Žive izmene i poništavanje rade u okviru jednog procesa (jedan `ui.run`), kao i cela NiceGUI aplikacija.
