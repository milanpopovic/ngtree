# ngtree — izmene po verzijama

Ista pravila kao za ngfw: svaka promena koda = nova verzija (`__version__` u `ngtree/__init__.py`) i stavka
ovde. Isti kod ide i u ngfw kao `ngfw.tree` (`bash build.sh --ngfw`), pa i ngfw tada dobija novu verziju.

## 0.1.1
- Primer se pokreće direktno sa GitHub-a: komanda `ngtree-demo` (`ngtree/demo.py`, `--port`, `--data`)
  i dugme „Open in GitHub Codespaces” (`.devcontainer/`). `examples/demo.py` sada samo poziva `ngtree.demo`.

## 0.1.0
- `TreeEditor` — stablo kao NiceGUI element (iz aplikacije stabla): dodavanje, izmena, brisanje,
  prevlačenje, gore/dole, sortiranje, beleške sa linkovima, oznake grana, filter, poništi,
  uvoz/izvoz (.txt putanje i JSON, celo stablo ili podstablo), samo-pregled, srpski/engleski.
- `JsonFileStore` (fajl, kopije pre svake izmene, poništi, žive izmene u svim pregledačima),
  `MemoryStore` (vaši podaci, `on_change`), `TreeStore` za sopstveni smeštaj.
- `ops` — sve operacije nad stablom bez UI-ja.
