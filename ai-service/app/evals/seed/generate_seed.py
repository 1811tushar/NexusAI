"""Deterministic seed generator (AI-DM-01): python -m app.evals.seed.generate_seed
Writes V7__seed_business_data.sql, facts.json (the measured truth, used to build golden questions and corpus) and story.md.
Fixed random seed -> byte-identical output. The generator ASSERTS that the planted story is really in the numbers.
Planted story, Q2 2026 vs Q1 2026: revenue declines. PRIMARY: West / Home (supplier stock-out May-Jun + competitor price cut from mid-April).
SECONDARY: South marketing cut in Apr-May (lagged sales dip across categories). RED HERRING: East / Apparel dips slightly (normal seasonality, same in 2025).
GROWTH: North / Electronics. revenue = units x unit_price and cost = units x unit_cost EXACTLY."""
from __future__ import annotations

import json
import random
from decimal import Decimal
from pathlib import Path
from typing import Any

SEED = 20260101
HERE = Path(__file__).parent
MONTHS = [(2025 + (i // 12), i % 12 + 1) for i in range(21)]                     # 2025-01 .. 2026-09
REGIONS = [(1, "North"), (2, "South"), (3, "East"), (4, "West")]
REGION_W = {"North": 1.0, "South": 0.9, "East": 0.8, "West": 1.1}
# id, sku, name, category, unit_price, unit_cost, base monthly units for weight 1.0
PRODUCTS = [
    (1, "HOM-101", "Aero Air Purifier", "Home", "180.00", "110.00", 220), (2, "HOM-102", "Brew Master Coffee Maker", "Home", "120.00", "70.00", 180),
    (3, "HOM-103", "Cozy Throw Blanket Set", "Home", "60.00", "30.00", 300), (4, "HOM-104", "Chef Cookware Set", "Home", "150.00", "90.00", 140),
    (5, "ELE-201", "Pulse Wireless Earbuds", "Electronics", "90.00", "50.00", 160), (6, "ELE-202", "Vista 4K Monitor", "Electronics", "320.00", "220.00", 60),
    (7, "ELE-203", "Volt Power Bank", "Electronics", "45.00", "25.00", 400), (8, "ELE-204", "Nova Smart Speaker", "Electronics", "110.00", "65.00", 200),
    (9, "APP-301", "Trail Running Jacket", "Apparel", "130.00", "70.00", 150), (10, "APP-302", "Everyday Denim", "Apparel", "80.00", "40.00", 220),
    (11, "APP-303", "Merino Sweater", "Apparel", "100.00", "55.00", 120), (12, "APP-304", "Sport Socks 6-pack", "Apparel", "25.00", "10.00", 500),
]
CHANNELS = [("Search", 0.5), ("Social", 0.3), ("Email", 0.2)]
SPEND_BASE = {"North": 18000, "South": 22000, "East": 16000, "West": 20000}
CUST_BASE = {"North": 12000, "South": 10500, "East": 9000, "West": 12500}


def _season(category: str, month: int, region: str) -> float:
    if category == "Home":
        return {11: 1.06, 12: 1.10}.get(month, 1.0)
    if category == "Electronics":
        return {1: 0.92, 11: 1.18, 12: 1.25}.get(month, 1.0)
    east = region == "East"
    table = {3: 1.02, 4: 0.97 if east else 0.99, 5: 0.95 if east else 0.98, 6: 0.93 if east else 0.97, 7: 0.98, 10: 1.05, 11: 1.12, 12: 1.15}
    return table.get(month, 1.0)


def _event(year: int, month: int, region: str, category: str) -> float:
    if year != 2026:
        return 1.0
    f = 1.0
    if region == "West" and category == "Home":
        f *= {4: 0.90, 5: 0.40, 6: 0.35, 7: 0.70, 8: 0.90}.get(month, 1.0)
    if region == "South":
        f *= {4: 0.88, 5: 0.85, 6: 0.93, 7: 0.97}.get(month, 1.0)
    if region == "North" and category == "Electronics":
        f *= {4: 1.12, 5: 1.18, 6: 1.22, 7: 1.20, 8: 1.20, 9: 1.20}.get(month, 1.0)
    return f


def _marketing_event(year: int, month: int, region: str) -> float:
    return {4: 0.55, 5: 0.55, 6: 0.90}.get(month, 1.0) if (year == 2026 and region == "South") else 1.0


def build_dataset() -> dict[str, list[dict[str, Any]]]:
    rng = random.Random(SEED)
    sales, marketing, customers = [], [], []
    for t, (y, m) in enumerate(MONTHS):
        for rid, rname in REGIONS:
            for pid, _sku, _n, cat, price, cost, base in PRODUCTS:
                units = max(1, round(base * REGION_W[rname] * (1 + 0.003 * t) * _season(cat, m, rname) * _event(y, m, rname, cat) * (1 + rng.uniform(-0.03, 0.03))))
                sales.append({"month": f"{y}-{m:02d}-01", "region_id": rid, "region": rname, "product_id": pid, "category": cat, "units": units,
                              "revenue": Decimal(units) * Decimal(price), "cost": Decimal(units) * Decimal(cost)})
            for ch, share in CHANNELS:
                spend = SPEND_BASE[rname] * share * (1 + 0.002 * t) * _marketing_event(y, m, rname) * (1 + rng.uniform(-0.04, 0.04))
                marketing.append({"month": f"{y}-{m:02d}-01", "region_id": rid, "region": rname, "channel": ch, "spend": Decimal(f"{spend:.2f}")})
    active = dict(CUST_BASE)
    for y, m in MONTHS:
        for rid, rname in REGIONS:
            new_f = 0.6 if (y == 2026 and rname == "South" and m in (4, 5)) else 1.0
            churn_f = 1.8 if (y == 2026 and rname == "West" and m in (5, 6)) else 1.0
            new = round(active[rname] * 0.035 * new_f * (1 + rng.uniform(-0.05, 0.05)))
            churned = round(active[rname] * 0.022 * churn_f * (1 + rng.uniform(-0.05, 0.05)))
            active[rname] = active[rname] + new - churned
            customers.append({"month": f"{y}-{m:02d}-01", "region_id": rid, "region": rname, "active_customers": active[rname],
                              "new_customers": new, "churned_customers": churned})
    return {"sales": sales, "marketing": marketing, "customers": customers}


def _q(rows: list[dict[str, Any]], key: str, months: list[str], **flt: str) -> float:
    return float(sum(r[key] for r in rows if r["month"][:7] in months and all(r[k] == v for k, v in flt.items())))


def compute_facts(ds: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    q1, q2 = ["2026-01", "2026-02", "2026-03"], ["2026-04", "2026-05", "2026-06"]
    q1_25, q2_25 = ["2025-01", "2025-02", "2025-03"], ["2025-04", "2025-05", "2025-06"]
    s, mk = ds["sales"], ds["marketing"]
    rev = lambda months, **f: _q(s, "revenue", months, **f)  # noqa: E731
    pct = lambda a, b: round((b - a) / a * 100, 1) if a else None  # noqa: E731
    total_q1, total_q2 = rev(q1), rev(q2)
    net = total_q2 - total_q1
    groups = {}
    for r in ("North", "South", "East", "West"):
        for c in ("Home", "Electronics", "Apparel"):
            a, b = rev(q1, region=r, category=c), rev(q2, region=r, category=c)
            groups[f"{r}/{c}"] = {"q1": round(a, 2), "q2": round(b, 2), "change": round(b - a, 2), "pct": pct(a, b), "share_of_net_change_pct": round((b - a) / net * 100, 1)}
    by_region = {r: {"q1": round(rev(q1, region=r), 2), "q2": round(rev(q2, region=r), 2), "pct": pct(rev(q1, region=r), rev(q2, region=r))} for _, r in REGIONS}
    by_cat = {c: {"q1": round(rev(q1, category=c), 2), "q2": round(rev(q2, category=c), 2), "pct": pct(rev(q1, category=c), rev(q2, category=c))} for c in ("Home", "Electronics", "Apparel")}
    mk_s_q1, mk_s_q2 = _q(mk, "spend", q1, region="South"), _q(mk, "spend", q2, region="South")
    mk_total = {r: {"q1": round(_q(mk, "spend", q1, region=r), 2), "q2": round(_q(mk, "spend", q2, region=r), 2)} for _, r in REGIONS}
    cust = ds["customers"]
    churn_w = {"q1": _q(cust, "churned_customers", q1, region="West"), "q2": _q(cust, "churned_customers", q2, region="West")}
    new_s = {"q1": _q(cust, "new_customers", q1, region="South"), "q2": _q(cust, "new_customers", q2, region="South")}
    units_w_home = {"q1": _q(s, "units", q1, region="West", category="Home"), "q2": _q(s, "units", q2, region="West", category="Home")}
    ea_25 = pct(rev(q1_25, region="East", category="Apparel"), rev(q2_25, region="East", category="Apparel"))
    facts = {
        "seed": SEED, "total_revenue": {"q1_2026": round(total_q1, 2), "q2_2026": round(total_q2, 2), "change": round(net, 2), "pct": pct(total_q1, total_q2)},
        "by_region": by_region, "by_category": by_cat, "groups": groups,
        "ranking_by_decline": sorted(groups, key=lambda g: groups[g]["change"])[:4],
        "marketing_spend": mk_total, "south_marketing": {"q1": round(mk_s_q1, 2), "q2": round(mk_s_q2, 2), "pct": pct(mk_s_q1, mk_s_q2)},
        "west_churned_customers": churn_w, "south_new_customers": new_s, "west_home_units": units_w_home,
        "east_apparel_q2_vs_q1_2025_pct": ea_25, "east_apparel_q2_vs_q1_2026_pct": groups["East/Apparel"]["pct"],
        "revenue_2025_total": round(_q(s, "revenue", [f"2025-{m:02d}" for m in range(1, 13)]), 2),
        "months": [f"{y}-{m:02d}" for y, m in MONTHS],
        "sales_row_count": len(s),
        "total_revenue_q2_2025": round(rev(q2_25), 2), "yoy_q2_pct": pct(rev(q2_25), total_q2),
        "region_growth_ranking": sorted(by_region, key=lambda r: -by_region[r]["pct"]),
        "category_q2_revenue_ranking": sorted(by_cat, key=lambda c: -by_cat[c]["q2"]),
        "units_by_product_q2_2026": {str(p[0]): _q([r for r in s if r["product_id"] == p[0]], "units", q2) for p in PRODUCTS},
    }
    wh, so, ea, ne = groups["West/Home"], None, groups["East/Apparel"], groups["North/Electronics"]
    south_total = by_region["South"]["q2"] - by_region["South"]["q1"]
    facts["south_region_change"] = round(south_total, 2)
    facts["south_region_share_of_net_change_pct"] = round(south_total / net * 100, 1)
    # ---- the planted story must really be there
    assert net < 0 and -12 <= facts["total_revenue"]["pct"] <= -3, facts["total_revenue"]
    assert wh["share_of_net_change_pct"] >= 60 and facts["ranking_by_decline"][0] == "West/Home", wh
    assert 20 <= facts["south_region_share_of_net_change_pct"] <= 65 and south_total < 0, south_total
    assert so is None and mk_s_q2 < 0.7 * mk_s_q1, (mk_s_q1, mk_s_q2)
    assert -12 <= ea["pct"] <= -2 and ea_25 is not None and -12 <= ea_25 <= -2, (ea["pct"], ea_25)
    assert abs(ea["share_of_net_change_pct"]) < 15, ea
    assert ne["pct"] >= 10, ne
    return facts


def _vals(rows: list[str]) -> str:
    return ",\n".join(rows)


def render_sql(ds: dict[str, list[dict[str, Any]]]) -> str:
    out = ["-- V7__seed_business_data.sql: synthetic demo company (4 regions, 3 categories, 12 products, 2025-01..2026-09).",
           f"-- GENERATED by app/evals/seed/generate_seed.py with seed {SEED}. Do not edit by hand; regenerate. Contains no personal data.",
           "INSERT INTO regions (id, name) VALUES\n" + _vals([f"({i}, '{n}')" for i, n in REGIONS]) + ";",
           "INSERT INTO products (id, sku, name, category, unit_price, unit_cost) VALUES\n"
           + _vals([f"({p[0]}, '{p[1]}', '{p[2]}', '{p[3]}', {p[4]}, {p[5]})" for p in PRODUCTS]) + ";"]
    rows = [f"('{r['month']}', {r['region_id']}, {r['product_id']}, {r['units']}, {r['revenue']:.2f}, {r['cost']:.2f})" for r in ds["sales"]]
    for i in range(0, len(rows), 250):
        out.append("INSERT INTO sales (sale_month, region_id, product_id, units, revenue, cost) VALUES\n" + _vals(rows[i:i + 250]) + ";")
    mrows = [f"('{r['month']}', {r['region_id']}, '{r['channel']}', {r['spend']})" for r in ds["marketing"]]
    out.append("INSERT INTO marketing_spend (month, region_id, channel, spend) VALUES\n" + _vals(mrows) + ";")
    crows = [f"('{r['month']}', {r['region_id']}, {r['active_customers']}, {r['new_customers']}, {r['churned_customers']})" for r in ds["customers"]]
    out.append("INSERT INTO customer_metrics (month, region_id, active_customers, new_customers, churned_customers) VALUES\n" + _vals(crows) + ";")
    return "\n".join(out) + "\n"


def render_story(f: dict[str, Any]) -> str:
    g, t = f["groups"], f["total_revenue"]
    return f"""# The planted story (ground truth for the demo and the evaluation)

Generated with seed {SEED}. All numbers below are computed from the seed SQL, not typed by hand.

**Hero question:** Why did Q2 revenue decline compared to Q1, and what should management investigate?

* **Outcome:** total revenue fell from {t['q1_2026']:,.2f} (Q1 2026) to {t['q2_2026']:,.2f} (Q2 2026): {t['change']:,.2f} ({t['pct']}%).
* **PRIMARY cause - West / Home:** {g['West/Home']['q1']:,.2f} -> {g['West/Home']['q2']:,.2f} ({g['West/Home']['pct']}%), which is {g['West/Home']['share_of_net_change_pct']}% of the net change.
  Documents explain it: supplier stock-out (May-June) plus a competitor price cut in the West from mid-April. Only the documents give the *why*; only SQL gives the exact numbers.
* **SECONDARY cause - South marketing cut:** South marketing spend {f['south_marketing']['q1']:,.2f} -> {f['south_marketing']['q2']:,.2f} ({f['south_marketing']['pct']}%) in April-May.
  South revenue changed by {f['south_region_change']:,.2f} ({f['south_region_share_of_net_change_pct']}% of the net change); South new customers {f['south_new_customers']['q1']:,.0f} -> {f['south_new_customers']['q2']:,.0f}.
* **RED HERRING - East / Apparel:** {g['East/Apparel']['pct']}% Q2 vs Q1 2026, but the same seasonal dip appears in 2025 ({f['east_apparel_q2_vs_q1_2025_pct']}%). Not a cause.
* **GROWTH - North / Electronics:** {g['North/Electronics']['pct']}% Q2 vs Q1.
* **Conflicting document:** the regional digest claims East apparel was the main driver and that West revenue rose. The data says otherwise.
* **Facts only in documents:** supplier name and dates, competitor name and discount, approval thresholds, planned budgets. **Facts only in SQL:** per-product numbers, customer counts.
"""


def main() -> None:
    ds = build_dataset()
    facts = compute_facts(ds)
    (HERE / "V7__seed_business_data.sql").write_text(render_sql(ds), encoding="utf-8")
    (HERE / "facts.json").write_text(json.dumps(facts, indent=2, sort_keys=True), encoding="utf-8")
    (HERE / "story.md").write_text(render_story(facts), encoding="utf-8")
    print(f"wrote V7 ({facts['sales_row_count']} sales rows), facts.json, story.md")
    print("total revenue Q1->Q2 2026:", facts["total_revenue"])
    for k in ("West/Home", "South/Home", "East/Apparel", "North/Electronics"):
        print(k, facts["groups"][k])
    print("south marketing:", facts["south_marketing"], "south region share:", facts["south_region_share_of_net_change_pct"])


if __name__ == "__main__":
    main()
