"""
config.py
=========
EVERY tunable number in the game lives here, so you can change odds, prices,
and grading behaviour WITHOUT touching the logic files.

Rule of thumb:
  * Money is always stored in CENTS (integers) to avoid floating-point rounding
    problems.  5000 cents == $50.00.
  * Probabilities written as "pct" are 0-100.  Probabilities written as
    "chance" are 0.0-1.0.
"""

# ---------------------------------------------------------------------------
# FILES
# ---------------------------------------------------------------------------
DATABASE_FILE = "pennyhunt.db"        # SQLite save file (created automatically)
BASE_CSV = "pennyfigures.csv"         # one row per date/mint mark (the "book")
VARIETIES_CSV = "varieties.csv"       # common varieties that split a base coin
SPECIALS_CSV = "specials.csv"         # proofs, big errors, collector-only coins

# ---------------------------------------------------------------------------
# MONEY
# ---------------------------------------------------------------------------
STARTING_BALANCE_CENTS = 5000         # $50.00 for a brand-new save
ROLL_SIZE = 50                        # coins per roll
ROLL_PRICE_CENTS = 50                 # $0.50 per roll
BOX_ROLLS = 50                        # rolls per box
BOX_PRICE_CENTS = 2500                # $25.00 per box
RETURN_VALUE_CENTS = 1                # face value you get back when you return a coin

# ---------------------------------------------------------------------------
# DISTRIBUTION: ERA SUPPRESSION ("reroll") RULES
# ---------------------------------------------------------------------------
# This is the C++ rerollID() logic, now driven by YEAR instead of hard-coded IDs
# (the old code accidentally gave 1940-P the pre-1940 rate because ID 87 is 1940-P).
#
# How it works: after a coin is picked by mintage weight, the FIRST rule whose
# max_year >= coin's year is checked.  With probability reroll_pct/100 the coin
# is thrown away and a brand-new coin is picked by mintage weight.
#
# Add more rules to model other effects, e.g. {"max_year": 1981, "reroll_pct": 10}
# to simulate copper-hoarders pulling pre-1982 cents.  Keep the list sorted by
# max_year ascending.
ERA_REROLL_RULES = [
    {"max_year": 1939, "reroll_pct": 95, "label": "Pre-1940 wheat"},
    {"max_year": 1958, "reroll_pct": 80, "label": "1940-1958 wheat"},
]

# The C++ version accepted whatever the reroll landed on (even another wheat).
# False = keep that original behaviour (matches the feel you tuned).
# True  = run the rules again on the rerolled coin (wheats get rarer).
REROLL_RECHECK = False

# ---------------------------------------------------------------------------
# DISTRIBUTION: SPECIAL BUCKET (proofs, major errors, collector-only coins)
# ---------------------------------------------------------------------------
# Every coin has this chance to be replaced by something from specials.csv.
# Which special you get is then chosen by the "weight" column in that file.
SPECIAL_CHANCE = 1 / 2500

# ---------------------------------------------------------------------------
# CONDITION (hidden "true" grade)
# ---------------------------------------------------------------------------
# Circulated coins: normal (bell-curve) distribution, same as the C++ version
# (mean 35, standard deviation 12, then +1).  The result is clamped to 1-70 and
# snapped to the nearest real PCGS grade (there is no "VF-31").
CONDITION_MEAN = 36
CONDITION_SD = 12

# Optional age effect: subtract this many points from the mean for every decade
# of age.  0 = off (original behaviour).  Try 2.0 to make old coins more worn.
CONDITION_AGE_SHIFT_PER_DECADE = 0.0
CURRENT_YEAR = 2026

# Specials use a "grade_profile" column: circulated / mint_state / proof
MINT_STATE_MEAN, MINT_STATE_SD = 64, 2.0
PROOF_MEAN, PROOF_SD = 67, 1.5

# How fuzzy YOUR estimate is.  Measured in steps along the PCGS grade list
# (e.g. one step from VF-30 is VF-25 or VF-35).  Bigger = worse eyesight.
ESTIMATE_SD_STEPS = 1.3

# ---------------------------------------------------------------------------
# PCGS GRADING SERVICE (flat fee per coin)
# ---------------------------------------------------------------------------
# Prices/turnarounds from the PCGS US-coin table you provided.
# max_declared_value is stored for when you add coin values (unused for now).
# "Rarities" also charges +1% of value (GP); not applied until values exist.
PCGS_TIERS = {
    "economy":     {"name": "Economy",     "fee_cents": 2400,  "days": 50, "max_declared_value": 300},
    "regular":     {"name": "Regular",     "fee_cents": 4200,  "days": 40, "max_declared_value": 3000},
    "express":     {"name": "Express",     "fee_cents": 7000,  "days": 20, "max_declared_value": 10000},
    "walkthrough": {"name": "Walkthrough", "fee_cents": 15000, "days": 5,  "max_declared_value": 50000},
    "rarities":    {"name": "Rarities",    "fee_cents": 30000, "days": 2,  "max_declared_value": None},
}

# The game clock: opening a roll moves time forward this many business days.
# There is also an "advance a day" button on the Grading page.
BUSINESS_DAYS_PER_ROLL = 1

# ---------------------------------------------------------------------------
# KEY / SEMI-KEY DATES (shown as badges when you flip one)
# Format: "YEAR|MINTMARK" exactly as written in pennyfigures.csv
# ---------------------------------------------------------------------------
KEY_DATES = {"1909|S-VDB", "1909|S", "1914|D", "1931|S"}
SEMI_KEY_DATES = {
    "1909|P-VDB", "1910|S", "1911|D", "1911|S", "1912|S", "1913|S", "1914|S",
    "1915|S", "1922|D", "1924|D", "1926|S", "1931|D", "1933|D",
}
