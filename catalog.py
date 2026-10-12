"""
catalog.py
==========
Loads the three CSV files into memory ONCE when the app starts.

Every collectible thing gets a string "key" that the database stores:
    "B123"            -> base coin with ID 123 from pennyfigures.csv
    "V:1982P-ZN-SD"   -> a variety from varieties.csv
    "S:1955-DDO"      -> a special (proof / error / collector) from specials.csv

Each catalog entry is a plain dict, so templates can read t["title"], etc.
"""
import csv
import os
from collections import defaultdict

import config

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def era_for(year):
    """Which album section a base coin belongs to."""
    if year <= 1958:
        return "Wheat Reverse (1909-1958)"
    if year <= 2008:
        return "Lincoln Memorial (1959-2008)"
    if year == 2009:
        return "Bicentennial (2009)"
    return "Union Shield (2010-2025)"


class Catalog:
    def __init__(self):
        self.by_key = {}                              # key -> entry (all kinds)
        self.base = []                                # base entries in ID order
        self.varieties = []                           # all variety entries
        self.varieties_by_parent = defaultdict(list)  # base key -> [variety entries]
        self.specials = []                            # all special entries
        self._load_base()
        self._load_varieties()
        self._load_specials()

    # ---------------- pennyfigures.csv (no header row) ----------------
    def _load_base(self):
        path = os.path.join(DATA_DIR, config.BASE_CSV)
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.reader(f):
                # Skip blank lines (this is what crashed the C++ eof() loop)
                if not row or not row[0].strip():
                    continue
                cid, year, mint, mintage, weight = [c.strip().lstrip("\ufeff") for c in row[:5]]
                year = int(year)
                rarity_id = f"{year}|{mint}"
                entry = {
                    "key": f"B{cid}",
                    "kind": "base",
                    "id": int(cid),
                    "date": year,
                    "mintmark": mint,
                    "mintage": int(mintage),
                    "weight": int(weight),
                    "era": era_for(year),
                    "title": f"{year} {mint}",
                    "rarity": ("key" if rarity_id in config.KEY_DATES
                               else "semi-key" if rarity_id in config.SEMI_KEY_DATES
                               else None),
                }
                self.base.append(entry)
                self.by_key[entry["key"]] = entry
        # lookup used by varieties.csv, which refers to coins by date + mintmark
        self._base_by_date_mint = {(b["date"], b["mintmark"]): b for b in self.base}

    # ---------------- varieties.csv ----------------
    def _load_varieties(self):
        path = os.path.join(DATA_DIR, config.VARIETIES_CSV)
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                parent = self._base_by_date_mint.get((int(row["date"]), row["mintmark"]))
                if parent is None:
                    print(f"WARNING: variety {row['key']} has no matching base coin")
                    continue
                entry = {
                    "key": "V:" + row["key"],
                    "kind": "variety",
                    "parent_key": parent["key"],
                    "date": parent["date"],
                    "mintmark": parent["mintmark"],
                    "label": row["label"],
                    "share": float(row["share"]),   # fraction of the parent's mintage
                    "title": f"{parent['title']} {row['label']}",
                    "rarity": None,
                }
                self.varieties.append(entry)
                self.varieties_by_parent[parent["key"]].append(entry)
                self.by_key[entry["key"]] = entry

    # ---------------- specials.csv ----------------
    def _load_specials(self):
        path = os.path.join(DATA_DIR, config.SPECIALS_CSV)
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                entry = {
                    "key": "S:" + row["key"],
                    "kind": "special",
                    "date": int(row["date"]),
                    "mintmark": row["mintmark"],
                    "category": row["category"],          # Proof / Error-Variety / Collector Issue
                    "label": row["label"],
                    "weight": float(row["weight"]),
                    "grade_profile": row["grade_profile"],  # circulated / mint_state / proof
                    "title": row["label"],
                    "notes": row.get("notes", ""),
                    "rarity": "special",
                }
                self.specials.append(entry)
                self.by_key[entry["key"]] = entry

    # ---------------- helpers for the album page ----------------
    def base_sections(self):
        """[(era name, [entries...]), ...] in date order."""
        sections = {}
        for b in self.base:
            sections.setdefault(b["era"], []).append(b)
        return list(sections.items())

    def special_sections(self):
        sections = {}
        for s in self.specials:
            sections.setdefault(s["category"], []).append(s)
        return list(sections.items())

    def get(self, key):
        return self.by_key.get(key)
