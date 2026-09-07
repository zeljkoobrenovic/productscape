#!/usr/bin/env python3
"""Check KPI-pyramid shape + coherence for one domain.

Usage: python3 check-kpi-pyramids.py <domain-id>

Verifies, for every persona's customerOutcomes/businessOutcomes pyramid:
  - shape: every non-leaf node has >=2 children; leaves have 0 (NO single-child nodes)
  - each top has >=2 branches
  - KPI ids unique within a persona (across both pyramids)
  - every load-bearing KPI name (referenced by insights.json kpis and by
    productStrategy northStar/supporting) resolves to a node in that persona's pyramids
Exit code 0 = clean, 1 = problems (printed).
"""
import json, sys, os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / '_wiring'))
from domain_paths import resolve_domain_dir

def main(dom):
    base = resolve_domain_dir(dom) / 'customers'
    d = json.load(open(os.path.join(base, 'customers.json')))
    ins_path = os.path.join(base, 'insights.json')
    ins = json.load(open(ins_path)) if os.path.exists(ins_path) else {'items': []}

    problems = []

    def walk_single(n, path, out):
        k = len(n.get('children', []))
        if k == 1:
            out.append(' > '.join(path + [n['name']]))
        for c in n.get('children', []):
            walk_single(c, path + [n['name']], out)

    def names(n, acc):
        if n.get('name'):
            acc.add(n['name'])
        for c in n.get('children', []):
            names(c, acc)

    def ids(n, acc, where):
        if n.get('id'):
            acc.append(n['id'])
        else:
            problems.append(f"{where}: pyramid node missing id: '{n.get('name', '<unnamed>')}'")
        for c in n.get('children', []):
            ids(c, acc, where)

    # load-bearing names per customer
    ref = {}
    for it in ins.get('items', []):
        for lc in it.get('linkedCustomers', []):
            ref.setdefault(lc['customerId'], set()).update(lc.get('kpis', []))
    for g in d:
        for c in g.get('customers', []):
            s = ref.setdefault(c['id'], set())
            horizons = c.get('productStrategy', {}).get('timeHorizons', {})
            # tolerate both the dict form ({"1_year": {...}}) and list-form drift
            horizon_values = horizons.values() if isinstance(horizons, dict) else (horizons or [])
            for hd in horizon_values:
                if not isinstance(hd, dict):
                    continue
                for kk in ('customerKPI', 'businessKPI'):
                    b = hd.get(kk)
                    if not isinstance(b, dict):
                        continue
                    if b.get('northStar'):
                        s.add(b['northStar'])
                    for x in b.get('supporting', []):
                        s.add(x)

    for g in d:
        for c in g.get('customers', []):
            cid = c['id']
            all_names = set()
            all_ids = []
            for key in ('customerOutcomes', 'businessOutcomes'):
                p = c.get('kpiPyramids', {}).get(key)
                if not p:
                    continue
                if len(p.get('branches', [])) < 2:
                    problems.append(f"{cid}/{key}: top has {len(p.get('branches', []))} branch(es), need >=2")
                single = []
                top = p.get('top', {})
                names(top, all_names)
                if top.get('id'):
                    all_ids.append(top['id'])
                else:
                    problems.append(f"{cid}/{key}: pyramid top missing id: '{top.get('name', '<unnamed>')}'")
                for b in p.get('branches', []):
                    walk_single(b, [f"{cid}/{key}"], single)
                    names(b, all_names)
                    ids(b, all_ids, f"{cid}/{key}")
                for s in single:
                    problems.append(f"{cid}/{key}: single-child node: {s}")
            dups = sorted({x for x in all_ids if all_ids.count(x) > 1})
            if dups:
                problems.append(f"{cid}: duplicate KPI ids: {dups}")
            low = {n.lower() for n in all_names}
            for nm in sorted(ref.get(cid, set())):
                if nm.lower() not in low:
                    problems.append(f"{cid}: load-bearing KPI name not in pyramids: '{nm}'")

    if problems:
        print(f"{dom}: {len(problems)} problem(s):")
        for p in problems:
            print("  -", p)
        return 1
    print(f"{dom}: KPI pyramids OK — fan out at every level, ids unique, all names resolve.")
    return 0

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("usage: check-kpi-pyramids.py <domain-id>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
