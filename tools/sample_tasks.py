"""
Random task sampling for the thesis experiment.

Methodik:
- CWE-Kategorien (crash_types) werden GEZIELT gewählt (Coverage/Variety).
- Innerhalb jeder Kategorie werden Tasks ZUFÄLLIG gezogen (fester Seed -> reproduzierbar).
- Das verhindert Cherry-Picking einzelner Tasks (Scandariatos Einwand).

Benutzung:
  # Standard: 1 Task pro Kategorie ziehen
  python3 sample_tasks.py

  # Nachziehen: eine weitere Task aus EINER Kategorie ziehen
  # (z.B. wenn die erste technisch nicht laeuft), die bereits gezogenen werden ausgeschlossen
  python3 sample_tasks.py --redraw "Heap-double-free"

  # Anderen Seed verwenden (dokumentieren!)
  python3 sample_tasks.py --seed 123

  # Mehr als 1 pro Kategorie (Phase 2)
  python3 sample_tasks.py --n 3
"""
import json
import re
import random
import argparse
from pathlib import Path

# ---- Konfiguration ----------------------------------------------------------
SEED = 42  # fest -> reproduzierbar. Bei Aenderung im Bericht dokumentieren!

# Die 5 gewaehlten Kategorien (normalisierte crash_types).
# Diese Strings muessen mit der Normalisierung unten matchen.
CATEGORIES = [
    "Heap-buffer-overflow READ",
    "Heap-buffer-overflow WRITE",
    "Heap-use-after-free",
    "Heap-double-free",
    "Index-out-of-bounds",
]

SELECTED_FILE = "selected_tasks.json"
METADATA_FILE = "sample_metadata.json"
# -----------------------------------------------------------------------------


def normalize_crash_type(ct: str) -> str:
    """'Heap-buffer-overflow READ 4' -> 'Heap-buffer-overflow READ'
    Entfernt angehaengte Byte-Groessen / Zahlen, vereinheitlicht Schreibweise."""
    ct = ct.strip()
    # Zahl(en) am Ende entfernen (Byte-Groesse des Overflows)
    ct = re.sub(r"\s+\d+\s*$", "", ct)
    # vereinheitliche bekannte Varianten
    lower = ct.lower()
    if "use-after-free" in lower or "use after free" in lower:
        return "Heap-use-after-free"
    if "double-free" in lower or "double free" in lower:
        return "Heap-double-free"
    if "index-out-of-bounds" in lower or "index out of bounds" in lower \
       or "container-overflow" in lower:
        return "Index-out-of-bounds"
    if "buffer-overflow" in lower:
        if "write" in lower:
            return "Heap-buffer-overflow WRITE"
        if "read" in lower:
            return "Heap-buffer-overflow READ"
    return ct  # unveraendert wenn nichts matcht


def load_metadata():
    with open(METADATA_FILE) as f:
        return json.load(f)


def group_by_category(data):
    """gibt {kategorie: [(task_id, project_name), ...]} zurueck, nur fuer gewaehlte Kategorien"""
    groups = {c: [] for c in CATEGORIES}
    for tid, t in data.items():
        cat = normalize_crash_type(t.get("crash_type", ""))
        if cat in groups:
            groups[cat].append((tid, t.get("project_name", "?")))
    # innerhalb jeder Kategorie nach task_id sortieren -> deterministische Basis vor dem Shuffle
    for c in groups:
        groups[c].sort(key=lambda x: int(x[0]))
    return groups


def load_selected():
    if Path(SELECTED_FILE).exists():
        with open(SELECTED_FILE) as f:
            return json.load(f)
    return {"seed": SEED, "selections": {}}


def save_selected(sel):
    with open(SELECTED_FILE, "w") as f:
        json.dump(sel, f, indent=2)


def draw(groups, n, seed, exclude=None):
    """Zieht n Tasks pro Kategorie, schliesst exclude-IDs aus. Reproduzierbar via seed+Kategorie."""
    exclude = set(exclude or [])
    result = {}
    for cat in CATEGORIES:
        pool = [(tid, proj) for (tid, proj) in groups[cat] if tid not in exclude]
        # eigener RNG pro Kategorie -> stabil & unabhaengig
        rng = random.Random(f"{seed}:{cat}")
        rng.shuffle(pool)
        result[cat] = pool[:n]
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--n", type=int, default=1, help="Tasks pro Kategorie")
    ap.add_argument("--redraw", type=str, default=None,
                    help="Eine weitere Task aus DIESER Kategorie ziehen (schliesst bereits gezogene aus)")
    args = ap.parse_args()

    data = load_metadata()
    groups = group_by_category(data)

    # Verfuegbarkeit anzeigen
    print("=== Verfuegbare Tasks pro Kategorie ===")
    for cat in CATEGORIES:
        print(f"  {cat:32} {len(groups[cat]):3} Tasks")
    print()

    sel = load_selected()
    sel["seed"] = args.seed

    if args.redraw:
        cat = normalize_crash_type(args.redraw)
        if cat not in CATEGORIES:
            print(f"FEHLER: '{args.redraw}' -> '{cat}' ist keine gewaehlte Kategorie.")
            return
        already = set()
        for c, tasks in sel["selections"].items():
            already.update(t["id"] for t in tasks)
        # eine zusaetzliche ziehen, bereits gezogene ausschliessen
        drawn = draw(groups, args.n, args.seed, exclude=already)[cat]
        if not drawn:
            print(f"Keine weiteren Tasks in '{cat}' verfuegbar (alle gezogen).")
            return
        sel["selections"].setdefault(cat, [])
        for tid, proj in drawn:
            sel["selections"][cat].append({"id": tid, "project": proj})
            print(f"NACHGEZOGEN [{cat}]: Task {tid} ({proj})")
        save_selected(sel)
        return

    # Normaler Lauf: frisch ziehen
    drawn = draw(groups, args.n, args.seed)
    sel["selections"] = {}
    print(f"=== Gezogene Tasks (seed={args.seed}, n={args.n}) ===")
    for cat in CATEGORIES:
        sel["selections"][cat] = []
        for tid, proj in drawn[cat]:
            sel["selections"][cat].append({"id": tid, "project": proj})
            print(f"  [{cat:32}] Task {tid} ({proj})")
    save_selected(sel)

    # ids.txt-freundliche Ausgabe
    all_ids = [t["id"] for tasks in sel["selections"].values() for t in tasks]
    print()
    print("=== Alle IDs (fuer ids.txt) ===")
    print("\n".join(all_ids))
    print()
    print(f"Gespeichert in {SELECTED_FILE} (inkl. Seed zur Reproduzierbarkeit).")


if __name__ == "__main__":
    main()