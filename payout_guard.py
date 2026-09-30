"""Second-payout detector: finds orders Vireo paid out on more than once.

Two leak types, conservative on purpose (only orders linked by a quoted order_id; inferred joins excluded):
 A. Over-refund   : 2+ refunds on one order (excluding DUP-PAYMENT, which legitimately returns a duplicate charge
                    and PRICE-ADJ, a partial adjustment) whose total exceeds order_value. Leak = total - order_value.
 B. Refund+replace: order has a replacement AND a refund (excl. DUP-PAYMENT / PRICE-ADJ). Policy s5: never both.
                    Leak = replacement cost (unit cost + Rs 340, policy s5).
Per order we take the larger of A and B (no double counting).
"""
import pandas as pd, numpy as np
from .clean import load
EXCL = {"DUP-PAYMENT", "PRICE-ADJ"}

def find(t: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    p = products.set_index("sku")
    t = t[t.order_link == "exact"].copy()
    t["repl_cost"] = np.where(t.is_repl, t.product_sku.map(p.unit_cost_inr) + 340, 0.0)
    ref = t[t.is_refund & ~t.refund_reason_code.isin(EXCL)]
    a = ref.groupby("order_id").agg(n_ref=("ticket_id", "nunique"), refunded=("refund_amount_inr", "sum"),
                                    order_value=("order_value_inr", "first"))
    a = a[a.n_ref > 1]; a["leak_overrefund"] = (a.refunded - a.order_value).clip(lower=0)
    b = t.groupby("order_id").agg(has_repl=("is_repl", "any"), repl_cost=("repl_cost", "sum"))
    b2 = ref.groupby("order_id").size().rename("n_refund_nonexcl")
    b = b.join(b2, how="inner"); b = b[b.has_repl]
    out = pd.concat([a.leak_overrefund, b.repl_cost.rename("leak_refund_and_replace")], axis=1).fillna(0)
    out["leak_inr"] = out.max(axis=1)
    out = out[out.leak_inr > 0]
    meta = t.sort_values("created_at").groupby("order_id").agg(first_payout=("created_at", "min"), last_ticket=("created_at", "max"),
                                                               tickets=("ticket_id", lambda x: ",".join(x)))
    return out.join(meta).sort_values("leak_inr", ascending=False)

def summary(t, leaks):
    e = t[t.order_link == "exact"]
    paid_orders = e[e.is_refund | e.is_repl].order_id.nunique()
    months = (t.created_at.max() - t.created_at.min()).days / 30.44
    return dict(paid_orders=paid_orders, leak_orders=len(leaks), leak_rate=len(leaks) / paid_orders,
                leak_inr=float(leaks.leak_inr.sum()), months=months, leak_per_quarter=float(leaks.leak_inr.sum()) / (months / 3))

if __name__ == "__main__":
    t = load(); pr = pd.read_csv("data/products.csv")
    L = find(t, pr); print(summary(t, L)); print(L.head())
