"""
app.py
======
The Flask web app.  Run with:   python app.py   then open http://127.0.0.1:5000

Pages (GET):
    /          home: wallet, store, stats
    /open      flip through the current roll one coin at a time
    /album     the "book" (base set, varieties, specials)
    /jar       duplicates
    /grading   PCGS submissions

Actions (POST): buying, opening, keep/return (JSON for the flip page), grading.

Pattern used everywhere: a POST changes the database, then REDIRECTS to a GET
page (so refreshing the browser never buys a second box by accident).
"""
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, url_for

import config
import db
import grading
from catalog import Catalog
from distribution import PennyGenerator

app = Flask(__name__)
app.secret_key = "local-only-change-me"   # needed for flash() messages

CATALOG = Catalog()                 # loaded once at startup
GENERATOR = PennyGenerator(CATALOG)
db.init_app(app)


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------
def money(cents):
    return f"${cents / 100:,.2f}"


def describe(coin, reveal_true=False):
    """
    Turn a database row into everything a template / the JS needs to display it.
    The true grade is NEVER included unless PCGS has returned the coin.
    """
    entry = CATALOG.get(coin["catalog_key"])
    variety = CATALOG.get(coin["variety_key"]) if coin["variety_key"] else None
    proof = bool(coin["is_proof"])
    badges = []
    if entry["rarity"] == "key":
        badges.append("KEY DATE")
    elif entry["rarity"] == "semi-key":
        badges.append("SEMI-KEY")
    elif entry["rarity"] == "special":
        badges.append(entry["category"].upper())
    if entry["kind"] == "base" and entry["date"] <= 1958:
        badges.append("WHEAT")
    if variety:
        badges.append(variety["label"])
    official = coin.get("official_grade")
    return {
        "id": coin["id"],
        "title": entry["title"],
        "variety": variety["label"] if variety else "",
        "badges": badges,
        "special": entry["kind"] == "special",
        "est_label": "~" + grading.grade_label(coin["est_grade"], proof),
        "official_label": grading.grade_label(official, proof) if official is not None else None,
        "tier": config.PCGS_TIERS[coin["grading_tier"]]["name"] if coin.get("grading_tier") else None,
        "due_day": coin.get("grading_due_day"),
        "in_book": coin.get("in_book"),
    }


app.jinja_env.filters["money"] = money


@app.context_processor
def inject_globals():
    """Variables available in EVERY template (used by the header in base.html)."""
    return {"state": db.get_state(), "cfg": config, "pending_count": len(db.pending_coins())}


def advance_days(n):
    """Move the game clock forward and collect any finished PCGS submissions."""
    db.add_to_state(business_day=n)
    returned = db.complete_due_grading(db.get_state()["business_day"])
    if returned:
        db.rearrange()   # an official grade can change which copy sits in the book
        names = ", ".join(f"{describe(c)['title']} {grading.grade_label(c['true_grade'], c['is_proof'])}"
                          for c in returned)
        flash(f"PCGS returned {len(returned)} coin(s): {names}", "success")


# ---------------------------------------------------------------------------
# Home + store
# ---------------------------------------------------------------------------
@app.get("/")
def home():
    slots = db.compute_slots(db.kept_coins())
    stats = {
        "base_have": sum(1 for b in CATALOG.base if b["key"] in slots),
        "base_total": len(CATALOG.base),
        "var_have": sum(1 for v in CATALOG.varieties if v["key"] in slots),
        "var_total": len(CATALOG.varieties),
        "spec_have": sum(1 for s in CATALOG.specials if s["key"] in slots),
        "spec_total": len(CATALOG.specials),
        "jar": len(db.jar_coins()),
    }
    return render_template("home.html", stats=stats)


@app.post("/buy/<item>")
def buy(item):
    if item == "roll":
        cost, rolls = config.ROLL_PRICE_CENTS, 1
    elif item == "box":
        cost, rolls = config.BOX_PRICE_CENTS, config.BOX_ROLLS
    else:
        abort(404)
    if db.get_state()["balance_cents"] < cost:
        flash(f"Not enough money for that ({money(cost)}).", "error")
    else:
        db.add_to_state(balance_cents=-cost, unopened_rolls=rolls, total_spent_cents=cost)
        flash(f"Bought {rolls} roll(s) for {money(cost)}.", "success")
    return redirect(url_for("home"))


# ---------------------------------------------------------------------------
# Opening rolls
# ---------------------------------------------------------------------------
@app.post("/open")
def open_roll():
    if db.pending_coins():                     # finish the current roll first
        return redirect(url_for("open_page"))
    state = db.get_state()
    if state["unopened_rolls"] < 1:
        flash("You have no unopened rolls. Buy some first!", "error")
        return redirect(url_for("home"))
    roll_no = state["rolls_opened"] + 1
    db.insert_pending(GENERATOR.generate_roll(), roll_no, state["business_day"])
    db.add_to_state(unopened_rolls=-1, rolls_opened=1)
    advance_days(config.BUSINESS_DAYS_PER_ROLL)
    return redirect(url_for("open_page"))


@app.get("/open")
def open_page():
    return render_template("open.html")


@app.get("/api/pending")
def api_pending():
    """JSON list of the coins in the open roll (used by static/open.js)."""
    return jsonify([describe(c) for c in db.pending_coins()])


@app.post("/api/coin/<int:coin_id>/<action>")
def api_coin(coin_id, action):
    coin = db.get_coin(coin_id)
    if coin is None or coin["status"] != "pending":
        return jsonify(error="That coin is not in an open roll."), 400
    placed = "returned"
    if action == "keep":
        db.keep_coin(coin_id)
        db.rearrange()
        placed = "book" if db.get_coin(coin_id)["in_book"] else "jar"
    elif action == "return":
        db.return_coin(coin_id)
    else:
        abort(404)
    return jsonify(ok=True, placed=placed, balance=money(db.get_state()["balance_cents"]))


@app.post("/api/return-rest")
def api_return_rest():
    for c in db.pending_coins():
        db.return_coin(c["id"])
    return jsonify(ok=True, balance=money(db.get_state()["balance_cents"]))


# ---------------------------------------------------------------------------
# Album and jar
# ---------------------------------------------------------------------------
@app.get("/album")
def album():
    slots = db.compute_slots(db.kept_coins())
    shown = {key: describe(c) for key, c in slots.items()}   # slot key -> display dict
    return render_template("album.html", slots=shown,
                           base_sections=CATALOG.base_sections(),
                           varieties=CATALOG.varieties,
                           special_sections=CATALOG.special_sections())


@app.get("/jar")
def jar():
    return render_template("jar.html", coins=[describe(c) for c in db.jar_coins()],
                           tiers=config.PCGS_TIERS)


# ---------------------------------------------------------------------------
# PCGS grading
# ---------------------------------------------------------------------------
@app.get("/grading")
def grading_page():
    eligible, in_progress, graded = db.grading_lists()
    return render_template("grading.html", tiers=config.PCGS_TIERS,
                           eligible=[describe(c) for c in eligible],
                           in_progress=[describe(c) for c in in_progress],
                           graded=[describe(c) for c in graded])


@app.post("/grade/<int:coin_id>")
def submit_grade(coin_id):
    tier_key = request.form.get("tier")
    tier = config.PCGS_TIERS.get(tier_key)
    coin = db.get_coin(coin_id)
    if tier is None or coin is None or coin["status"] != "kept" or coin["grading_tier"]:
        flash("That coin can't be submitted.", "error")
    elif db.get_state()["balance_cents"] < tier["fee_cents"]:
        flash(f"{tier['name']} costs {money(tier['fee_cents'])}; you can't afford it.", "error")
    else:
        due = db.get_state()["business_day"] + tier["days"]
        db.submit_for_grading(coin_id, tier_key, due)
        db.add_to_state(balance_cents=-tier["fee_cents"], grading_fees_cents=tier["fee_cents"])
        flash(f"Submitted to PCGS ({tier['name']}). Due back on business day {due}.", "success")
    return redirect(request.referrer or url_for("grading_page"))


@app.post("/advance")
def advance():
    advance_days(int(request.form.get("days", 1)))
    return redirect(url_for("grading_page"))


if __name__ == "__main__":
    app.run(debug=True)
