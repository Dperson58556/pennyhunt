"""
grading.py
==========
Everything about the PCGS 1-70 (Sheldon) scale.

PCGS only uses certain numbers.  Below 60 the scale jumps (4, 6, 8, 10 ...);
from 60 to 70 every number is valid.  All grades in the game are snapped to
this list.
"""
import random

import config

PCGS_GRADES = [1, 2, 3, 4, 6, 8, 10, 12, 15, 20, 25, 30, 35, 40, 45,
               50, 53, 55, 58, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70]

rng = random.Random()


def snap_grade(value, low=1, high=70):
    """Clamp a raw number to [low, high] and return the nearest real PCGS grade."""
    value = max(low, min(high, value))
    allowed = [g for g in PCGS_GRADES if low <= g <= high]
    return min(allowed, key=lambda g: abs(g - value))


def grade_prefix(grade, is_proof=False):
    """The letters that go before the number (MS-65, VF-30, PR-69 ...)."""
    if is_proof:
        return "PR"
    if grade >= 60: return "MS"   # Mint State
    if grade >= 50: return "AU"   # About Uncirculated
    if grade >= 40: return "XF"   # Extremely Fine
    if grade >= 20: return "VF"   # Very Fine
    if grade >= 12: return "F"    # Fine
    if grade >= 8:  return "VG"   # Very Good
    if grade >= 4:  return "G"    # Good
    if grade == 3:  return "AG"   # About Good
    if grade == 2:  return "FR"   # Fair
    return "PO"                   # Poor


def grade_label(grade, is_proof=False):
    if grade is None:
        return "?"
    return f"{grade_prefix(grade, is_proof)}-{grade}"


def estimate_grade(true_grade, is_proof=False):
    """
    Your eyeball guess.  Starting from the hidden true grade, we move a random
    number of steps up or down the PCGS_GRADES list (bell curve, centred on 0).
    """
    idx = PCGS_GRADES.index(true_grade)
    step = round(rng.gauss(0, config.ESTIMATE_SD_STEPS))
    new_idx = max(0, min(len(PCGS_GRADES) - 1, idx + step))
    guess = PCGS_GRADES[new_idx]
    if is_proof:                       # proofs never get guessed below PR-60
        guess = max(guess, 60)
    return guess
