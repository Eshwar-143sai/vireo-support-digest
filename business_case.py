"""Every rupee figure in the memo comes from here, using policy s4/s5 cost standards (never Arjun's Rs 180)."""
import json, pathlib, pandas as pd, numpy as np
from .features import build
from . import payout_guard
from .clean import BREACH_CREDIT, TRANSFER_COST
OUT = pathlib.Path(__file__).resolve().parents[1] / "out"

def compute(t=None, products=None):
    t = build() if t is None else t
    products = pd.read_csv("data/products.csv") if products is None else products
    months = (t.created_at.max() - t.created_at.min()).days / 30.44; q = months / 3
    L = payout_guard.find(t, products); s = payout_guard.summary(t, L)
    kinds = {"over_refund": float(L.leak_overrefund.gt(L.leak_refund_and_replace).mul(L.leak_inr).sum()),
             "refund_and_replace": float(L.leak_refund_and_replace.ge(L.leak_overrefund).mul(L.leak_inr).sum())}
    tgt = 0.02; cut = 1 - tgt / s["leak_rate"]
    rep = t[t.is_repeat]; rep_cost = float((rep.contact_cost).sum())
    top = t[t.theme != "unclassified"].groupby("theme").agg(n=("ticket_id", "size"), back=("came_back", "mean"), cost=("came_back", lambda x: float((x * t.loc[x.index, "contact_cost"]).sum()))).sort_values("cost", ascending=False)
    bc = dict(
        window_months=round(months, 1), tickets=int(len(t)), tickets_per_week=round(len(t) / (months * 4.345), 1),
        payout=dict(paid_orders_checked=s["paid_orders"], leak_orders=s["leak_orders"], leak_rate=round(s["leak_rate"], 4), leak_inr_total=round(s["leak_inr"]),
                    leak_inr_per_quarter=round(s["leak_per_quarter"]), by_kind=kinds, target_rate=tgt, share_prevented_at_target=round(cut, 3),
                    saving_per_quarter_at_target=round(s["leak_per_quarter"] * cut),
                    sensitivity_saving_per_quarter={f"{int(p*100)}% prevented": round(s["leak_per_quarter"] * p) for p in (0.5, 0.7, 0.9)}),
        repeat_contacts=dict(rate=round(float(t.is_repeat.mean()), 4), cost_total=round(rep_cost), cost_per_quarter=round(rep_cost / q),
                             top_themes_by_cost=top.head(5).round(3).reset_index().to_dict("records")),
        sla=dict(breach_rate=round(float(t.breach.mean()), 4), credits_total=int(t.breach.sum() * BREACH_CREDIT), credits_per_quarter=round(t.breach.sum() * BREACH_CREDIT / q),
                 night_vs_day=[round(float(t[t.agent_shift == "Night"].breach.mean()), 3), round(float(t[t.agent_shift == "Day"].breach.mean()), 3)]),
        transfers=dict(count=int(t.transfers.sum()), cost_total=int(t.transfers.sum() * TRANSFER_COST), cost_per_quarter=round(t.transfers.sum() * TRANSFER_COST / q)),
        contact_cost_note="policy s4 blended Rs 290 (channel-specific 210/260/520/240); Finance's Rs 180 is not used. Payout leak does not depend on contact cost.",
    )
    return bc, L

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True); bc, L = compute()
    (OUT / "business_case.json").write_text(json.dumps(bc, indent=2, default=str)); L.to_csv(OUT / "second_payouts.csv")
    print(json.dumps(bc, indent=2, default=str))
