"""The editor's texts in Serbian and English. The Serbian text is the key (as in stabla and rodoslovi):
translate('Poništi', 'en') -> 'Undo'. An app can replace any text with TreeEditor(texts={...}):
{Serbian key: text to show}, e.g. {'Novi čvor na vrhu': 'Nova kategorija'} — used in every language."""
from __future__ import annotations

LANGUAGES = ('sr', 'en')

EN = {
    # toolbar, menu
    'Filter': 'Filter',
    'Novi čvor na vrhu': 'New top-level node',
    'Otvori sve': 'Expand all',
    'Zatvori sve': 'Collapse all',
    'Poništi': 'Undo',
    'Vraća poslednju izmenu (svaki klik jednu)': 'Reverts the last change (one per click)',
    'Pronađeno: {0}': 'Found: {0}',
    '{0} čvorova · {1} listova · dubina {2}': '{0} nodes · {1} leaves · depth {2}',
    'Uvezi (zameni celo stablo)…': 'Import (replace the whole tree)…',
    'Uvezi na vrh stabla…': 'Import at the top level…',
    'Izvezi kao tekst (putanje)': 'Export as text (paths)',
    'Izvezi kao JSON': 'Export as JSON',
    'Sortiraj vrh stabla': 'Sort top level',
    'Uputstvo →': 'User guide →',
    'Pređite mišem preko čvora za dugmad · dupli klik = izmena · prevucite čvor na drugi: '
    'gore = ispred, sredina = unutra, dole = iza.':
        'Hover over a node for its buttons · double click = edit · drag a node onto another: '
        'top = before, middle = inside, bottom = after.',
    'Samo pregled — kliknite na 🗒 da pročitate belešku; ⋮ pored čvora izvozi njegovo podstablo.':
        'View only — click 🗒 to read a note; ⋮ next to a node exports its subtree.',
    'Samo pregled.': 'View only.',
    'Stablo je prazno — dodajte prvi čvor.': 'The tree is empty — add the first node.',
    'Stablo je prazno.': 'The tree is empty.',
    'Nema rezultata.': 'No results.',
    '⤒ Prevucite čvor ovde da postane čvor na vrhu stabla': '⤒ Drag a node here to move it to the top level',
    'Stablo je obrisano.': 'The tree has been deleted.',
    'Ovo stablo vam više nije dostupno.': 'This tree is no longer available to you.',
    'Nema ranijih verzija.': 'There are no earlier versions.',
    'Nemate pravo da menjate ovo stablo.': 'You are not allowed to change this tree.',

    # node buttons
    'Dodaj podčvor': 'Add child node',
    'Izmeni': 'Edit',
    'Obriši': 'Delete',
    'Pomeri gore': 'Move up',
    'Pomeri dole': 'Move down',
    'Sortiraj podčvorove': 'Sort child nodes',
    'Premesti na vrh stabla': 'Move to top level',
    'Uvezi ispod ovog čvora…': 'Import under this node…',
    'Izvezi podstablo — tekst (.txt)': 'Export subtree — text (.txt)',
    'Izvezi podstablo — JSON': 'Export subtree — JSON',
    'Beleška — kliknite da je otvorite (linkovi se otvaraju u novoj kartici)':
        'Note — click to open it (links open in a new tab)',

    # node dialog
    'Izmena čvora': 'Edit node',
    'Novi čvor na vrhu stabla': 'New node at the top level',
    'Novi čvor ispod „{0}”': 'New node under “{0}”',
    'Naziv': 'Name',
    'Beleška (nije obavezna) — adrese (https://…, www.…) postaju linkovi':
        'Note (optional) — addresses (https://…, www.…) become links',
    'Oznaka grane (nije obavezna)': 'Branch tag (optional)',
    'Otkaži': 'Cancel',
    'Dodaj i nastavi': 'Add and continue',
    'Enter u nazivu radi isto — za brzo dodavanje više čvorova':
        'Enter in the name does the same — for adding many nodes quickly',
    'Dodaj': 'Add',
    'Sačuvaj': 'Save',
    'Taj čvor više ne postoji.': 'That node no longer exists.',
    'Obrisati „{0}” i svih {1} čvorova ispod njega?': 'Delete “{0}” and all {1} nodes under it?',
    'Obrisati „{0}”?': 'Delete “{0}”?',
    '(Može se vratiti dugmetom Poništi.)': '(This can be reverted with Undo.)',
    'Potvrda': 'Please confirm',

    # import
    'Uvoz — zamenjuje celo stablo': 'Import — replaces the whole tree',
    'Uvoz na vrh stabla': 'Import at the top level',
    'Uvoz ispod „{0}”': 'Import under “{0}”',
    '**.txt**: jedan red = jedna putanja, nazivi odvojeni zarezom (kao pasovi.txt): `Koren,Dete,Unuče`. '
    'Redovi sa istim početkom dele čvorove. Red VELIKIM SLOVIMA je oznaka grane.  \n'
    '**.json**: fajl izvezen iz ove aplikacije.':
        '**.txt**: one line = one path, names separated by commas (as in pasovi.txt): `Root,Child,Grandchild`. '
        'Lines that start the same way share nodes. A line in CAPITAL LETTERS is a branch tag.  \n'
        '**.json**: a file exported from this app.',
    'Uvezeno čvorova: {0}': 'Nodes imported: {0}',
    'Zatvori': 'Close',

    # errors (ops.py, stores.py)
    'Stablo više ne postoji.': 'The tree no longer exists.',
    'Naziv ne može biti prazan.': 'The name cannot be empty.',
    'Naziv je predugačak (najviše {0} znakova).': 'The name is too long (at most {0} characters).',
    'Taj čvor više ne postoji (možda ga je neko u međuvremenu obrisao).':
        'That node no longer exists (someone may have deleted it in the meantime).',
    'Nepoznato mesto.': 'Unknown position.',
    'Čvor ne može da se premesti u sopstveni podčvor.': 'A node cannot be moved into one of its own descendants.',
    'U fajlu nema nijednog reda sa nazivima.': 'The file has no lines with names.',
    'U fajlu nema nijednog čvora.': 'The file has no nodes.',
    'Neispravan JSON: {0}': 'Invalid JSON: {0}',
    'JSON mora imati listu "nodes".': 'The JSON must contain a "nodes" list.',
    'Stablo može imati najviše {0} čvorova.': 'The tree can have at most {0} nodes.',
}


def translate(text: str, language: str = 'sr', overrides: dict[str, str] | None = None) -> str:
    if overrides and text in overrides:
        return overrides[text]
    if language == 'en':
        return EN.get(text, text)
    return text
