#!/usr/bin/env python3
"""Refresh called_today.json (the dialer map's "not called today" pulse) from a list of today's calls.

Input: CSV or JSON of today's calls. Per row, at least one of
    contact_id | contact_email | contact_name
plus optional: am (Kahekili|Simran|Nick|Mia|Addie|Nathan, full names ok), time, outcome.
(Aliases accepted: hubspot_contact_id/id, email, name, call_time/timestamp, disposition.)
JSON may be a list of row objects or {"calls": [...]}.

Each row is resolved to a hubspot_contact_id using data.json, in order:
    1. contact_id (must exist in data.json; a HubSpot record URL also works)
    2. contact_email (case-insensitive)
    3. contact_name, case-insensitive exact match within that AM's companies
       (if no AM is given, only a unique match across all contacts counts)
Unresolved rows are reported and left out.

The output always replaces the file with *today's* list (America/Chicago date).

    python3 update_called_today.py calls.csv                 # write locally, report
    python3 update_called_today.py calls.json --publish      # + commit/push called_today.json to master
    python3 update_called_today.py --empty [--publish]       # reset to today's empty state

Month-to-date: every run also folds today's called contacts into called_mtd.json
({"month": "YYYY-MM", "entries": {"Kili": {"YYYY-MM-DD": [contact ids]}}}), deduped per rep/day/contact; the file resets
only when the month rolls over, and --empty never removes anything from it. Score on the page = number of rep/day/contact
entries this month (+ today's live Log Call queue). Rep = the contact's AM. Nothing is estimated.
    python3 update_called_today.py --backfill-git     # one-off: rebuild this month's entries from called_today.json history in git

--publish commits/pushes ONLY called_today.json and called_mtd.json, and only when the called contact set changed
or the date rolled over versus what is on origin/master (timestamp-only changes are skipped
unless --force). Exit codes: 0 ok, 1 error, 2 ok-but-unresolved rows with --strict.
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_NAME = "called_today.json"
MTD_NAME = "called_mtd.json"
DEFAULT_SOURCE = "HubSpot calls (browser sync)"
AM_ALIASES = {
    "kahekili": "Kahekili Barrozo", "kahekili barrozo": "Kahekili Barrozo", "kili": "Kahekili Barrozo",
    "arconic": "Kahekili Barrozo",
    "simran": "Simran Subramanian", "simran subramanian": "Simran Subramanian",
    "kaiser": "Simran Subramanian", "kaiser aluminum": "Simran Subramanian",
    "nick": "Nicholas McNamara", "nicholas": "Nicholas McNamara", "nicholas mcnamara": "Nicholas McNamara",
    "mia": "Mia Medjedovic", "mia medjedovic": "Mia Medjedovic",
    "addie": "Addison Parker", "addison": "Addison Parker", "addison parker": "Addison Parker",
    "nathan": "Nathan Beaver", "nathan beaver": "Nathan Beaver", "nbeaver": "Nathan Beaver", "beaver": "Nathan Beaver",
}
SHORT = {"Nicholas McNamara": "Nick", "Addison Parker": "Addie"}   # call-log / UI short names (others: first name)
FIELD_ALIASES = {
    "contact_id": ["contact_id", "hubspot_contact_id", "id", "contactid"],
    "contact_email": ["contact_email", "email", "contact email"],
    "contact_name": ["contact_name", "name", "contact", "contact name"],
    "am": ["am", "account_manager", "owner"],
    "time": ["time", "call_time", "timestamp", "called_at"],
    "outcome": ["outcome", "disposition", "call_outcome", "result"],
}


def norm_name(s):
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def norm_am(s):
    if not s:
        return None
    return AM_ALIASES.get(norm_name(s))


def short_am(full):
    return SHORT.get(full) or (full or "").split(" ")[0] or ""


def pick(row, field):
    low = {str(k).strip().lower(): v for k, v in row.items()}
    for a in FIELD_ALIASES[field]:
        v = low.get(a)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return ""


def load_rows(path):
    if path == "-":
        text = sys.stdin.read()
        is_json = text.lstrip().startswith(("[", "{"))
    else:
        with open(path, newline="", encoding="utf-8-sig") as f:
            text = f.read()
        is_json = path.lower().endswith(".json") or text.lstrip().startswith(("[", "{"))
    if is_json:
        data = json.loads(text)
        if isinstance(data, dict):
            data = data.get("calls", [])
        if not isinstance(data, list):
            raise SystemExit("JSON input must be a list of rows or {\"calls\": [...]}")
        return [r for r in data if isinstance(r, dict)]
    return list(csv.DictReader(text.splitlines()))


def norm_time(t, today):
    """'9:14 AM' / '14:05' / ISO → ISO with CT offset (sortable). Unparseable → kept as-is."""
    if not t:
        return ""
    s = t.strip()
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        d = d.replace(tzinfo=CT) if d.tzinfo is None else d.astimezone(CT)
        return d.isoformat(timespec="seconds")
    except ValueError:
        pass
    for fmt in ("%I:%M %p", "%I:%M%p", "%I:%M:%S %p", "%H:%M", "%H:%M:%S", "%I %p"):
        try:
            tm = datetime.strptime(s.upper(), fmt).time()
            return datetime.combine(datetime.fromisoformat(today).date(), tm, tzinfo=CT).isoformat(timespec="seconds")
        except ValueError:
            continue
    return s


def build_index(data):
    by_id, by_email, by_name = {}, {}, {}
    for c in data["contacts"]:
        cid = str(c.get("hubspot_contact_id") or "")
        if not cid:
            m = re.search(r"/record/0-1/(\d+)", c.get("hubspot_url") or "")
            cid = m.group(1) if m else ""
        if not cid:
            continue
        by_id[cid] = c
        if c.get("email"):
            by_email.setdefault(c["email"].strip().lower(), []).append((cid, c))
        if c.get("name"):
            by_name.setdefault(norm_name(c["name"]), []).append((cid, c))
    return by_id, by_email, by_name


def pins_by_contact(data):
    """contact_id -> [pin labels] it lights up on the map: its plant pin plus every supplier pin
    (kind == "supplier") whose contact_ids list it. Mirrors the page's inLoc() logic."""
    out = {}
    locs = {l["id"]: l for l in data.get("locations", [])}
    for c in data["contacts"]:
        cid = str(c.get("hubspot_contact_id") or "")
        l = locs.get(c.get("plant_id"))
        if cid and l and l.get("pin"):
            out.setdefault(cid, []).append(l.get("label") or l.get("name"))
    for l in data.get("locations", []):
        if l.get("pin") and isinstance(l.get("contact_ids"), list):
            for cid in l["contact_ids"]:
                out.setdefault(str(cid), []).append(l.get("label") or l.get("name"))
    return out


def resolve(row, idx):
    by_id, by_email, by_name = idx
    cid_in, email, name = pick(row, "contact_id"), pick(row, "contact_email"), pick(row, "contact_name")
    am_raw = pick(row, "am")
    am = norm_am(am_raw)
    if am_raw and not am:
        return None, None, f"unknown AM '{am_raw}'"
    tried = []
    if cid_in:
        m = re.search(r"/record/0-1/(\d+)", cid_in)
        cid = m.group(1) if m else re.sub(r"\D", "", cid_in)
        if cid in by_id:
            return cid, "id", None
        tried.append(f"id {cid_in} not in data.json")
    if email:
        hits = by_email.get(email.lower(), [])
        if len(hits) == 1:
            return hits[0][0], "email", None
        tried.append(f"email {email} " + ("ambiguous" if hits else "not found"))
    if name:
        hits = by_name.get(norm_name(name), [])
        if am:
            hits = [h for h in hits if h[1].get("am") == am]
        if len(hits) == 1:
            return hits[0][0], "name" + ("" if am else " (no AM; unique)"), None
        tried.append(f"name '{name}'" + (f" within {short_am(am)}" if am else "") + (" ambiguous" if hits else " not found"))
    if not (cid_in or email or name):
        tried.append("row has no contact_id / contact_email / contact_name")
    return None, None, "; ".join(tried)


def load_mtd(path, month):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        if d.get("month") == month and isinstance(d.get("entries"), dict):
            return d
    except (OSError, ValueError):
        pass
    return {"month": month, "entries": {}}


def mtd_add(mtd, rep_short, day, ids):
    """Union ids into entries[rep][day]; returns number newly added."""
    if not rep_short or not day.startswith(mtd["month"]):
        return 0
    cur = mtd["entries"].setdefault(rep_short, {}).setdefault(day, [])
    new = [i for i in map(str, ids) if i not in cur]
    cur.extend(new)
    cur.sort(key=lambda s: (len(s), s))
    return len(new)


def mtd_from_called(called, idx, mtd):
    """Fold a called_today-style dict into mtd (rep = contact's AM from data.json, else the call's own am)."""
    day = called.get("date") or ""
    added = 0
    call_am = {str(c.get("contact_id")): c.get("am") for c in called.get("calls", [])}
    for cid in called.get("called_contact_ids", []):
        c = idx[0].get(str(cid))
        rep = short_am(c.get("am")) if c else short_am(norm_am(call_am.get(str(cid))) or "")
        added += mtd_add(mtd, rep, day, [cid])
    return added


def mtd_write(path, mtd, now):
    mtd["updated_at"] = now.isoformat(timespec="seconds")
    mtd["source"] = "accumulated from called_today.json syncs + Log Call queue (update_called_today.py)"
    mtd["counts"] = {r: sum(len(v) for v in d.values()) for r, d in sorted(mtd["entries"].items())}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(mtd, f, indent=1, ensure_ascii=False)
        f.write("\n")


def git(repo, *args, check=True):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed:\n{r.stdout}{r.stderr}")
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?", help="CSV or JSON of today's calls ('-' = stdin)")
    ap.add_argument("--empty", action="store_true", help="write today's empty state (no input needed)")
    ap.add_argument("--data", default=os.path.join(HERE, "data.json"))
    ap.add_argument("--out", default=os.path.join(HERE, OUT_NAME))
    ap.add_argument("--source", default=DEFAULT_SOURCE)
    ap.add_argument("--publish", action="store_true", help="git commit + push called_today.json to master if it meaningfully changed")
    ap.add_argument("--force", action="store_true", help="with --publish: push even if only the timestamp changed")
    ap.add_argument("--branch", default="master")
    ap.add_argument("--backfill-git", action="store_true", help="rebuild this month's called_mtd.json entries from the git history of called_today.json, then exit")
    ap.add_argument("--mtd-out", default=os.path.join(HERE, MTD_NAME))
    ap.add_argument("--strict", action="store_true", help="exit 2 if any row is unresolved")
    a = ap.parse_args()
    if not a.input and not a.empty and not a.backfill_git:
        ap.error("give an input file (or '-') or --empty")

    now = datetime.now(CT)
    today = now.date().isoformat()
    with open(a.data, encoding="utf-8") as f:
        data = json.load(f)
    idx = build_index(data)
    if a.backfill_git:
        month = today[:7]
        mtd = load_mtd(a.mtd_out, month)
        rel0 = os.path.relpath(os.path.abspath(a.out), HERE)
        revs = git(HERE, "log", "--format=%H", "--", rel0).stdout.split()
        for rev in revs:
            r = git(HERE, "show", f"{rev}:{rel0}", check=False)
            try:
                snap = json.loads(r.stdout)
            except ValueError:
                continue
            n = mtd_from_called(snap, idx, mtd)
            if n:
                print(f"  {rev[:7]} {snap.get('date')}: +{n}")
        mtd_write(a.mtd_out, mtd, now)
        print(f"Wrote {a.mtd_out}: {mtd['counts']}")
        return
    pin_map = pins_by_contact(data)
    rows = [] if a.empty else load_rows(a.input)

    calls, ids, unresolved = [], [], []
    for i, row in enumerate(rows, 1):
        cid, how, why = resolve(row, idx)
        if not cid:
            unresolved.append((i, row, why))
            continue
        c = idx[0][cid]
        given_am = norm_am(pick(row, "am"))
        if given_am and given_am != c.get("am"):
            print(f"  ! row {i}: AM '{pick(row, 'am')}' differs from contact's AM ({short_am(c.get('am'))}); using contact's", file=sys.stderr)
        calls.append({
            "contact_id": cid,
            "contact_name": c.get("name", ""),
            "am": short_am(c.get("am")),
            "time": norm_time(pick(row, "time"), today),
            "outcome": pick(row, "outcome"),
        })
        if cid not in ids:
            ids.append(cid)
        pins = pin_map.get(cid, [])
        print(f"  ✓ row {i}: {c.get('name')} ({short_am(c.get('am'))}) → {cid} [by {how}]"
              f" · pins: {', '.join(pins) if pins else 'none (Unassigned)'}")
    for i, row, why in unresolved:
        print(f"  ✗ row {i} UNRESOLVED: {why} :: {json.dumps(row, ensure_ascii=False)}")

    calls.sort(key=lambda x: (x["time"] or "", x["contact_name"]))
    out = {
        "date": today,
        "updated_at": now.isoformat(timespec="seconds"),
        "synced_at": now.isoformat(timespec="seconds"),   # time of THIS sync run (the page's "synced Xh ago" stamp)
        "source": a.source,
        "called_contact_ids": sorted(ids, key=lambda s: (len(s), s)),
        "calls": calls,
    }

    # Baseline for change detection: origin/<branch> when publishing (what's live), else the file on disk.
    out_abs = os.path.abspath(a.out)
    repo = rel = None
    baseline = None
    if a.publish:
        r = git(os.path.dirname(out_abs), "rev-parse", "--show-toplevel", check=False)
        if r.returncode != 0:
            raise SystemExit(f"--publish: {os.path.dirname(out_abs)} is not inside a git checkout")
        repo = r.stdout.strip()
        rel = os.path.relpath(out_abs, repo)
        git(repo, "fetch", "-q", "origin", a.branch)
        cur = git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        if cur != a.branch:
            raise SystemExit(f"--publish: checkout is on '{cur}', expected '{a.branch}'")
        ahead = git(repo, "rev-list", f"origin/{a.branch}..HEAD").stdout.split()
        if ahead:
            raise SystemExit(f"--publish: local {a.branch} has {len(ahead)} unpushed commit(s); refusing so only {rel} is pushed")
        r = git(repo, "show", f"origin/{a.branch}:{rel}", check=False)
        if r.returncode == 0:
            try:
                baseline = json.loads(r.stdout)
            except ValueError:
                baseline = None
    elif os.path.exists(out_abs):
        try:
            with open(out_abs, encoding="utf-8") as f:
                baseline = json.load(f)
        except ValueError:
            baseline = None

    if baseline is None:
        changed, reason = True, "no previous file"
    elif baseline.get("date") != today:
        changed, reason = True, f"date rolled over ({baseline.get('date')} → {today})"
    elif set(map(str, baseline.get("called_contact_ids") or [])) != set(ids):
        changed, reason = True, f"called list changed ({len(baseline.get('called_contact_ids') or [])} → {len(ids)})"
    else:
        changed, reason = False, "no change apart from timestamp/details"

    with open(out_abs, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")
    mtd = load_mtd(a.mtd_out, today[:7])
    before = json.dumps(mtd["entries"], sort_keys=True)
    mtd_from_called(out, idx, mtd)
    mtd_changed = json.dumps(mtd["entries"], sort_keys=True) != before or not os.path.exists(a.mtd_out)
    if mtd_changed:
        mtd_write(a.mtd_out, mtd, now)
    try:
        import rank_history
        rank_history.update(HERE, today=today)   # daily rank snapshot -> rank_history.json (rank-change arrows)
    except Exception as e:   # never block a sync on the cosmetic snapshot
        print(f"  ! rank_history skipped: {e}", file=sys.stderr)
    print(f"MTD {today[:7]}: {mtd.get('counts') or {r: sum(len(v) for v in d.values()) for r, d in mtd['entries'].items()} or 'no data'} ({'updated' if mtd_changed else 'unchanged'})")
    lit = sorted({p for cid in ids for p in pin_map.get(cid, [])})
    print(f"Wrote {out_abs}: date={today} called={len(ids)} calls={len(calls)} unresolved={len(unresolved)} · {reason}")
    print(f"Pins marked called ({len(lit)}): {', '.join(lit) if lit else 'none'}")

    if a.publish:
        if mtd_changed:
            changed = True
        if not changed and not a.force:
            print("Publish skipped (nothing meaningful changed vs origin). Use --force to push anyway.")
        else:
            git(repo, "pull", "-q", "--rebase", "--autostash", "origin", a.branch)
            mrel = os.path.relpath(os.path.abspath(a.mtd_out), repo)
            rrel = os.path.relpath(os.path.join(HERE, "rank_history.json"), repo)
            files = [rel, mrel] + ([rrel] if os.path.exists(os.path.join(HERE, "rank_history.json")) else [])
            git(repo, "add", "--", *files)
            if git(repo, "diff", "--cached", "--quiet", "--", *files, check=False).returncode == 0:
                print("Publish skipped (file identical to HEAD).")
            else:
                msg = f"called_today: {today} · {len(ids)} called ({now.strftime('%-I:%M %p')} CT)"
                git(repo, "commit", "-q", "-m", msg, "--", *files)
                git(repo, "push", "-q", "origin", f"HEAD:{a.branch}")
                sha = git(repo, "rev-parse", "--short", "HEAD").stdout.strip()
                print(f"Published {rel} → origin/{a.branch} @ {sha}")

    if unresolved and a.strict:
        sys.exit(2)


if __name__ == "__main__":
    main()
