"""Weekly complaint digest (markdown). Usage: python -m src.digest [--week 2026-06-22]"""
import argparse, pathlib, numpy as np, pandas as pd
from scipy import stats
from .features import build
from . import payout_guard
OUT = pathlib.Path(__file__).resolve().parents[1] / "out"
LABEL = {"order_not_received":"Order not received / tracking stuck","refund_not_received":"Refund not received","pairing_failure":"Bluetooth pairing failure",
 "payment_issue":"Payment deducted / duplicate charge","battery_drain":"Battery drain","connection_drops":"Connection drops","wrong_item_address":"Wrong item / address change",
 "app_crash":"App crash / won't open","return_pickup":"Return pickup missed","presales_compat":"Pre-sales / compatibility","delivery_delayed":"Delivery delayed",
 "audio_one_side":"One side silent","repair_warranty":"Repair / warranty status","invoice_gst":"Invoice / GST","coupon_discount":"Coupon / discount not applied",
 "cancellation":"Cancellation","audio_noise":"Crackle / hiss / distortion","firmware_update":"Firmware update stuck","login_otp":"Login / OTP","hardware_defect":"Strap / display / build defect",
 "mic_issue":"Mic issue","damaged_in_transit":"Damaged in transit","charging_case":"Charging case dead","bud_not_charging":"One earbud not charging","device_dead":"Device dead","unclassified":"Unclassified"}
STRICT = ["audio_noise","audio_one_side","bud_not_charging","charging_case","device_dead","hardware_defect","mic_issue"]

def lot_watch(t, orders, asof, bonf=0.05):
    """Poisson test per manufacturing lot: hardware-fault orders vs the base rate, Bonferroni-corrected over all lots."""
    o = orders[orders.order_date <= asof]
    d = t[t.theme.isin(STRICT) & t.order_link.eq("exact") & (t.created_at <= asof)]
    n = o.groupby("lot_code").order_id.nunique()
    k = d.groupby("lot_code").order_id_used.nunique().reindex(n.index).fillna(0)
    base = k.sum() / n.sum()
    p = [1 - stats.poisson.cdf(kk - 1, base * nn) if kk > 0 else 1 for kk, nn in zip(k, n)]
    x = pd.DataFrame({"orders": n, "fault_orders": k, "rate": k / n, "expected": base * n, "p": p}).sort_values("p")
    x["p_corrected"] = (x.p * len(x)).clip(upper=1)
    return x[(x.p < 0.001) & (x.fault_orders >= 8)], base

def make(week_start, t=None, orders=None, products=None, out_dir=OUT / "digests", quotes=True):
    t = build() if t is None else t
    orders = pd.read_csv("data/orders.csv", parse_dates=["order_date"]) if orders is None else orders
    products = pd.read_csv("data/products.csv") if products is None else products
    ws = pd.Timestamp(week_start); we = ws + pd.Timedelta(days=7)
    cur = t[(t.created_at >= ws) & (t.created_at < we)]
    base = t[(t.created_at >= ws - pd.Timedelta(weeks=4)) & (t.created_at < ws)]
    L = [f"# Vireo support digest: week of {ws:%d %b %Y}", "", f"*{len(cur)} tickets this week (prior 4-week average {len(base)/4:.0f}). Themes are read from what customers wrote, not the bot's tag.*", ""]
    # 1 themes
    c = cur.theme.value_counts(); b = base.theme.value_counts() / 4
    rows = []
    for th, n in c.items():
        if th == "unclassified": continue
        exp = max(b.get(th, 0), 0.5); p = 1 - stats.poisson.cdf(n - 1, exp)
        rows.append((th, n, exp, p))
    rows.sort(key=lambda r: -r[1])
    L += ["## What people complained about", "", "| Issue | Tickets | 4-wk avg | Signal |", "|---|---:|---:|---|"]
    for th, n, exp, p in rows[:8]:
        sig = "**Rising**" if (n >= 8 and n >= 1.5 * exp and p < 0.01) else ("up" if n > 1.25 * exp and n >= 8 else ("down" if n < 0.75 * exp else "steady"))
        L.append(f"| {LABEL[th]} | {n} | {exp:.1f} | {sig} |")
    rising = [(th, n, exp) for th, n, exp, p in rows if n >= 8 and n >= 1.5 * exp and p < 0.01]
    L += [""]
    if rising: L += [f"**Unusual this week:** " + "; ".join(f"{LABEL[th]} ({n} vs ~{exp:.0f} normal)" for th, n, exp in rising) + ".", ""]
    # 2 bot tag
    oth = cur[cur.category == "Other"]
    if len(oth):
        real = oth[oth.theme != "unclassified"].theme.value_counts().head(3)
        L += ["## Tagging", "", f"The bot tagged {len(oth)} tickets ({len(oth)/len(cur):.0%}) as 'Other'. Most were identifiable: " + ", ".join(f"{LABEL[k]} ({v})" for k, v in real.items()) + ".", ""]
    # 3 repeat contacts (trailing 13 weeks; last 30 days excluded so follow-ups have had time to arrive)
    tr = t[(t.created_at >= ws - pd.Timedelta(weeks=17)) & (t.created_at < ws - pd.Timedelta(days=30)) & (t.theme != "unclassified")]
    rc = tr.groupby("theme").agg(n=("ticket_id", "size"), back=("came_back", "mean"), cost=("came_back", "sum"), cc=("contact_cost", "mean"))
    rc["cost"] = rc.cost * rc.cc; rc = rc[rc.n >= 40].sort_values("back", ascending=False).head(4)
    L += ["## Issues customers come back about (same issue within 30 days, ~13 weeks to last month)", ""]
    L += [f"- {LABEL[i]}: {r.back:.0%} come back ({int(r.n)} tickets, about Rs {r.cost:,.0f} of repeat-contact cost)" for i, r in rc.iterrows()] + [""]
    # 4 payouts
    leaks = payout_guard.find(t, products)
    wk = leaks[(leaks.last_ticket >= ws) & (leaks.last_ticket < we)]
    L += ["## Money: orders paid out twice", ""]
    L += [f"{len(wk)} order(s) reached a second payout this week (Rs {wk.leak_inr.sum():,.0f}): " + ", ".join(wk.index[:8]) + "." if len(wk) else "None detected this week.", "",
          "Rule: any order with a refund and a replacement, or refunds totalling more than the order value (duplicate-charge and price-adjustment refunds excluded). Only orders where the customer quoted an order ID are checked.", ""]
    # 5 lots
    lw, lb = lot_watch(t, orders, we)
    L += ["## Product watch", ""]
    if len(lw):
        for lot, r in lw.head(3).iterrows():
            L.append(f"- Lot **{lot}**: {int(r.fault_orders)} of {int(r.orders)} orders reported a hardware fault ({r.rate:.0%} vs {lb:.0%} typical, ~{r.expected:.0f} expected). "
                     f"Corrected for testing all lots the evidence is {'strong' if r.p_corrected < 0.05 else 'not conclusive'} (p={r.p_corrected:.2f}): {'raise with QC/supplier' if r.p_corrected < 0.05 else 'keep watching, do not act yet'}.")
    else: L.append("No manufacturing lot is a statistical outlier.")
    # 6 SLA
    L += ["", "## First-response SLA", "", f"{cur.breach.mean():.1%} of tickets missed the first-response target (prior 4 weeks: {base.breach.mean():.1%}); each breach issues a Rs 350 credit, so about Rs {cur.breach.sum()*350:,.0f} this week."]
    # 7 examples (omitted in the public sample output: customer text can contain names)
    if quotes:
        L += ["", "## In their words", ""]
        for th, n, *_ in rows[:4]:
            m = cur[cur.theme == th].customer_message.iloc[0].replace("\n", " ").replace("[IVR transcript] ", "")
            L.append(f"- *{LABEL[th]}*: \u201c{m[:140]}\u201d")
    out_dir = pathlib.Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    f = out_dir / f"digest_{ws:%Y-%m-%d}.md"; f.write_text("\n".join(L) + "\n", encoding="utf-8"); return f

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--week", default=None); ap.add_argument("--last", type=int, default=1)
    a = ap.parse_args(); t = build()
    end = pd.Timestamp(a.week) if a.week else (t.created_at.max().normalize() - pd.Timedelta(days=t.created_at.max().weekday()) - pd.Timedelta(weeks=1))
    for i in range(a.last)[::-1]: print(make(end - pd.Timedelta(weeks=i), t))
