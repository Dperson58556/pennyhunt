"""
distribution.py
===============
The coin generator: the Python version of the C++ main loop's random logic.

Order of operations for ONE coin (see generate_coin):
  1. Special bucket?  With SPECIAL_CHANCE the coin becomes a proof/error/collector
     coin picked from specials.csv by its weight.  Done.
  2. Otherwise pick a base coin weighted by mintage
     (same idea as std::discrete_distribution).
  3. Apply ERA_REROLL_RULES (wheat suppression, same idea as rerollID()).
  4. If the base coin has varieties (e.g. 1982 copper/zinc), pick one by "share".
  5. Roll a hidden true grade, then a fuzzy estimated grade.

To add a new factor later, write another small method and call it inside
generate_coin().  Each step only receives/returns a catalog entry, so steps
stay independent.
"""
import random

import config
import grading

rng = random.Random()   # seeded from the OS automatically (like the chrono seed in C++)


class PennyGenerator:
    def __init__(self, catalog):
        self.catalog = catalog
        # Pre-build the weight lists once; random.choices() uses them like
        # std::discrete_distribution did.
        self.base = catalog.base
        self.base_weights = [b["weight"] for b in self.base]
        self.specials = catalog.specials
        self.special_weights = [s["weight"] for s in self.specials]
        # Sort rules so the first match is the narrowest (earliest) era
        self.rules = sorted(config.ERA_REROLL_RULES, key=lambda r: r["max_year"])

    # ---- step 2 ----
    def pick_base(self):
        return rng.choices(self.base, weights=self.base_weights, k=1)[0]

    # ---- step 3 ----
    def apply_era_rules(self, coin, depth=0):
        for rule in self.rules:
            if coin["date"] <= rule["max_year"]:
                roll = rng.randint(1, 100)           # same 1-100 roll as rerollID()
                if roll <= rule["reroll_pct"]:
                    new_coin = self.pick_base()
                    if config.REROLL_RECHECK and depth < 10:
                        return self.apply_era_rules(new_coin, depth + 1)
                    return new_coin
                return coin   # survived the reroll: keep the wheat (and COUNT it - C++ bug fixed)
        return coin           # no rule applies (modern coin)

    # ---- step 4 ----
    def pick_variety(self, base_coin):
        options = self.catalog.varieties_by_parent.get(base_coin["key"])
        if not options:
            return None
        return rng.choices(options, weights=[v["share"] for v in options], k=1)[0]

    # ---- step 5 ----
    def roll_true_grade(self, year, profile="circulated"):
        if profile == "proof":
            return grading.snap_grade(rng.gauss(config.PROOF_MEAN, config.PROOF_SD), 60, 70)
        if profile == "mint_state":
            return grading.snap_grade(rng.gauss(config.MINT_STATE_MEAN, config.MINT_STATE_SD), 60, 70)
        decades_old = max(0, (config.CURRENT_YEAR - year) / 10)
        mean = config.CONDITION_MEAN - config.CONDITION_AGE_SHIFT_PER_DECADE * decades_old
        return grading.snap_grade(rng.gauss(mean, config.CONDITION_SD))

    # ---- the whole pipeline ----
    def generate_coin(self):
        # 1. special bucket
        if self.specials and rng.random() < config.SPECIAL_CHANCE:
            sp = rng.choices(self.specials, weights=self.special_weights, k=1)[0]
            is_proof = sp["grade_profile"] == "proof"
            true = self.roll_true_grade(sp["date"], sp["grade_profile"])
            return {"catalog_key": sp["key"], "variety_key": None, "is_proof": int(is_proof),
                    "true_grade": true, "est_grade": grading.estimate_grade(true, is_proof)}

        # 2-4. normal circulation coin
        coin = self.apply_era_rules(self.pick_base())
        variety = self.pick_variety(coin)
        true = self.roll_true_grade(coin["date"])
        return {"catalog_key": coin["key"], "variety_key": variety["key"] if variety else None,
                "is_proof": 0, "true_grade": true, "est_grade": grading.estimate_grade(true)}

    def generate_roll(self, size=None):
        return [self.generate_coin() for _ in range(size or config.ROLL_SIZE)]
