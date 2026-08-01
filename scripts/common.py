#!/usr/bin/env python3
"""Shared config loading + name normalisation."""
import json, os, re, sys, unicodedata

DEFAULT_CONFIG = "config.json"


def load_config(path=None):
    p = path or DEFAULT_CONFIG
    if not os.path.exists(p):
        sys.exit(f"config not found: {p}  (copy config.example.json -> config.json)")
    return json.load(open(p))


def arg_config():
    """--config <path> from argv."""
    if "--config" in sys.argv:
        return load_config(sys.argv[sys.argv.index("--config") + 1])
    return load_config()


SUFFIXES = (
    r"limited|ltd|llp|llc|plc|inc|incorporated|corp|corporation|company|co|"
    r"holdings?|group|international|intl|global|worldwide|europe|european|"
    r"uk|gb|england|scotland|wales|britain|british|"
    r"services?|solutions?|systems?|technolog(?:y|ies)|tech|labs?|"
    r"consult(?:ing|ants?|ancy)|partners(?:hip)?|associates?|ventures?|"
    r"enterprises?|trading|operations?|management|"
    r"branch|establishment|subsidiary|division|the|and|of|for|a|an"
)
SUFFIX_RE = re.compile(r"\b(?:%s)\b" % SUFFIXES, re.I)
TA_RE = re.compile(r"\b(?:t/a|t\.a\.|trading\s+as)\b\s*(.+)$", re.I)
TA_PAREN_RE = re.compile(r"\(\s*trading\s+as\s+([^)]+)\)", re.I)


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c))


def normalise(name):
    """Aggressive: brand core only. For fuzzy matching."""
    s = strip_accents(name).lower()
    s = re.sub(r"[‘’“”]", "'", s)
    s = re.sub(r"&", " and ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = SUFFIX_RE.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def light_normalise(name):
    """Conservative: punctuation + case only. For exact lookup."""
    s = strip_accents(name).lower()
    s = re.sub(r"&", " and ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tokens(s):
    return frozenset(t for t in s.split() if len(t) > 1)


def extract_trading_as(raw):
    """Return (trading_as_or_None, legal_part)."""
    m = TA_PAREN_RE.search(raw)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip(" .,-"), raw[:m.start()].strip(" .,-")
    m = TA_RE.search(raw)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip(" .,-"), raw[:m.start()].strip(" .,-")
    return None, raw


def all_targets(cfg):
    out, seen = [], set()
    for sector, names in cfg["targets"].items():
        for n in names:
            if n.lower() in seen:
                continue
            seen.add(n.lower())
            out.append({"brand": n, "sector": sector})
    return out


def slug_variants(brand):
    b = brand.lower().replace("&", "and")
    nodot = re.sub(r"\.(com|io|ai|co|uk|net|org)$", "", b)
    cands = [
        re.sub(r"[^a-z0-9]+", "", b),
        re.sub(r"[^a-z0-9]+", "-", b).strip("-"),
        re.sub(r"[^a-z0-9]+", "", nodot),
        re.sub(r"[^a-z0-9]+", "-", nodot).strip("-"),
    ]
    seen, out = set(), []
    for s in cands:
        if s and len(s) > 1 and s not in seen:
            seen.add(s)
            out.append(s)
    return out
