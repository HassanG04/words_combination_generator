#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_combinations.py

Expand input words (Arabic + English) into many spelling variants:
- English leetspeak: a/@/4, e/3, i/1/!, o/0, s/$/5, t/7, ...
- Optional repeated letters (once)
- Optional separators between letters: "", ".", "_", " " (configurable)
- Arabic substitutions: ه/ة, ا/أ/إ/آ/ٱ, ى/ي, ؤ/و, ئ/ي, plus optional tatweel removal and diacritics stripping
- Case variants for English (lower/UPPER/Title)

Outputs a comma-separated list.

Usage examples:
  python generate_combinations.py --input words.txt --output output.csv
  echo "software" | python generate_combinations.py --stdin --max-per-word 400
  python generate_combinations.py --input words.txt --separators "" "." "_" " " --repeat --leet

Safety note: This script is content-agnostic; you supply the words.
"""

import argparse
import itertools
import re
import sys
from pathlib import Path

# ---------------- Defaults ----------------
DEFAULT_SEPARATORS = ["", ".", "_", " "]
DEFAULT_MAX_PER_WORD = 400

# Arabic diacritics range
AR_DIACRITICS = "".join([
    "\u0610", "\u0611", "\u0612", "\u0613", "\u0614",
    "\u0615", "\u0616", "\u0617", "\u0618", "\u0619", "\u061A",
    "\u064B", "\u064C", "\u064D", "\u064E", "\u064F", "\u0650", "\u0651", "\u0652",
    "\u0653", "\u0654", "\u0655", "\u0656", "\u0657", "\u0658", "\u0659", "\u065A",
    "\u065B", "\u065C", "\u065D", "\u065E", "\u065F", "\u0670"
])
AR_DIACRITICS_RE = re.compile("[" + re.escape(AR_DIACRITICS) + "]")

# Arabic substitution groups
AR_GROUPS = [
    {"ا", "أ", "إ", "آ", "ٱ"},
    {"ه", "ة"},
    {"ى", "ي"},
    {"ؤ", "و"},
    {"ئ", "ي"},
    {"ک", "ك"},    # Persian/Arabic kaf
    {"ـ"},         # tatweel
]

AR_GROUP_MAP = {}
for grp in AR_GROUPS:
    for ch in grp:
        AR_GROUP_MAP[ch] = grp

# English leetspeak
EN_LEET = {
    "a": ["a", "@", "4"],
    "b": ["b", "8"],
    "c": ["c", "("],
    "d": ["d"],
    "e": ["e", "3"],
    "f": ["f"],
    "g": ["g", "9"],
    "h": ["h"],
    "i": ["i", "1", "!"],
    "j": ["j"],
    "k": ["k", "|<"],
    "l": ["l", "1", "|"],
    "m": ["m"],
    "n": ["n"],
    "o": ["o", "0"],
    "p": ["p"],
    "q": ["q"],
    "r": ["r"],
    "s": ["s", "$", "5"],
    "t": ["t", "7"],
    "u": ["u", "v"],
    "v": ["v", "u"],
    "w": ["w"],
    "x": ["x"],
    "y": ["y"],
    "z": ["z", "2"],
}

def is_arabic_text(s: str) -> bool:
    for ch in s:
        # Arabic + Arabic Supplement blocks (common coverage)
        if "\u0600" <= ch <= "\u06FF" or "\u0750" <= ch <= "\u077F" or "\u08A0" <= ch <= "\u08FF":
            return True
    return False

def strip_arabic_diacritics(text: str) -> str:
    return AR_DIACRITICS_RE.sub("", text)

def normalize_arabic_base(s: str, rm_tatweel: bool, strip_diacritics: bool) -> str:
    repl = {
        "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
        "ة": "ه",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي",
        "ک": "ك",
    }
    for k, v in repl.items():
        s = s.replace(k, v)
    if rm_tatweel:
        s = s.replace("ـ", "")
    if strip_diacritics:
        s = strip_arabic_diacritics(s)
    return s

def arabic_variants(word: str,
                    separators,
                    max_variants_per_word: int,
                    enable_ar_subs: bool,
                    rm_tatweel: bool,
                    strip_diacritics: bool):
    base = word
    if rm_tatweel:
        base = base.replace("ـ", "")
    if strip_diacritics:
        base = strip_arabic_diacritics(base)

    choices = []
    for ch in base:
        if enable_ar_subs and ch in AR_GROUP_MAP:
            choices.append(sorted(AR_GROUP_MAP[ch]))
        else:
            choices.append([ch])

    variants = set()
    for prod in itertools.product(*choices):
        variants.add("".join(prod))

    # insert uniform separator between chars
    sep_forms = set()
    for v in variants:
        for sep in separators:
            sep_forms.add(sep.join(list(v)) if sep != "" else v)
    variants = sep_forms

    if len(variants) > max_variants_per_word:
        variants = set(list(variants)[:max_variants_per_word])
    return variants

def english_variants(word: str,
                     separators,
                     max_variants_per_word: int,
                     enable_leet: bool,
                     enable_repeat: bool,
                     enable_case: bool):
    w = word

    # Build choices per character
    def char_choices(ch: str):
        opts = [ch]
        if enable_leet and ch.lower() in EN_LEET:
            opts = EN_LEET[ch.lower()]
        return opts

    base_choices = [char_choices(ch) for ch in w]

    variants = set("".join(prod) for prod in itertools.product(*base_choices))

    # Optional repeats (double one character once)
    if enable_repeat:
        extra = set()
        for v in list(variants):
            for i in range(len(v)):
                extra.add(v[:i] + v[i]*2 + v[i+1:])
        variants |= extra

    # Case variants
    if enable_case:
        case_more = set()
        for v in list(variants):
            case_more.add(v.lower())
            case_more.add(v.upper())
            case_more.add(v.title())
        variants |= case_more

    # Separators
    sep_forms = set()
    for v in variants:
        for sep in separators:
            sep_forms.add(sep.join(list(v)) if sep != "" else v)
    variants = sep_forms

    if len(variants) > max_variants_per_word:
        variants = set(list(variants)[:max_variants_per_word])
    return variants

def load_words(args) -> list[str]:
    words = []
    if args.stdin:
        for line in sys.stdin:
            line = line.strip()
            if line:
                words.append(line)
    if args.input:
        p = Path(args.input)
        if p.exists():
            words += [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
        else:
            print(f"[warn] input file not found: {p}", file=sys.stderr)
    if not words and args.words:
        words = args.words
    return list(dict.fromkeys(words))  # dedupe, preserve order

def main():
    ap = argparse.ArgumentParser(description="Generate word variants (Arabic + English).")
    ap.add_argument("--input", help="UTF-8 text file (one word per line)")
    ap.add_argument("--stdin", action="store_true", help="Read words from STDIN (one per line)")
    ap.add_argument("--words", nargs="*", help="Words provided inline (space-separated)")
    ap.add_argument("--output", default="output.csv", help="Write comma-separated variants here (default: output.csv)")

    ap.add_argument("--max-per-word", type=int, default=DEFAULT_MAX_PER_WORD, help="Cap variants per word (default 400)")
    ap.add_argument("--separators", nargs="*", default=DEFAULT_SEPARATORS, help='List of separators between letters (default: "", ".", "_", " ")')

    # English toggles
    ap.add_argument("--leet", action="store_true", help="Enable English leetspeak substitutions")
    ap.add_argument("--repeat", action="store_true", help="Enable English single repeated letter inserts")
    ap.add_argument("--case", action="store_true", help="Enable English case variants (lower/UPPER/Title)")

    # Arabic toggles
    ap.add_argument("--ar-subs", action="store_true", help="Enable Arabic letter-group substitutions")
    ap.add_argument("--ar-strip-diacritics", action="store_true", help="Strip Arabic diacritics (tashkeel) before expansion")
    ap.add_argument("--ar-remove-tatweel", action="store_true", help="Remove tatweel (ـ) before expansion")
    ap.add_argument("--ar-normalize", action="store_true", help="Normalize Arabic word to canonical base before expansion")

    args = ap.parse_args()

    words = load_words(args)
    if not words:
        print("No words provided. Use --input, --stdin, or --words.", file=sys.stderr)
        sys.exit(1)

    all_out = set()

    for w in words:
        try:
            if is_arabic_text(w):
                base = w
                if args.ar_normalize:
                    base = normalize_arabic_base(
                        w,
                        rm_tatweel=args.ar_remove_tatweel,
                        strip_diacritics=args.ar_strip_diacritics
                    )
                vars_ar = arabic_variants(
                    base,
                    separators=args.separators,
                    max_variants_per_word=args.max_per_word,
                    enable_ar_subs=args.ar_subs,
                    rm_tatweel=args.ar_remove_tatweel,
                    strip_diacritics=args.ar_strip_diacritics
                )
                all_out |= vars_ar
            else:
                vars_en = english_variants(
                    w,
                    separators=args.separators,
                    max_variants_per_word=args.max_per_word,
                    enable_leet=args.leet,
                    enable_repeat=args.repeat,
                    enable_case=args.case
                )
                all_out |= vars_en
        except Exception as e:
            print(f"[warn] failed on word '{w}': {e}", file=sys.stderr)

    out_path = Path(args.output)
    out_path.write_text(",".join(sorted(all_out)), encoding="utf-8")
    print(f"[ok] {len(all_out)} variants written to {out_path}")

if __name__ == "__main__":
    main()
