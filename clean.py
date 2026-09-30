"""Load raw Vireo exports and return an analysis-ready ticket table.

Every fix here comes from a documented trap (support-policy.pdf s9, README, email thread):
 1. 653 ticket_ids exist twice (helpdesk re-import + legacy_fd). Keep the helpdesk copy:
    it has IST resolution times, blank-not-0 CSAT and (in 195 cases) an order_id the legacy copy lacks.
 2. Legacy-only tickets: resolved_at was rebuilt from a UTC log -> add 5h30. Verified: 2,263 legacy
    rows had resolved_at BEFORE created_at; after the shift there are 0.
 3. Legacy CSAT 0 means "no response" -> NaN.
 4. Order link: order_id, else fallback customer_id+sku = latest order before the ticket (flagged as inferred).
 5. Roster: agent_id joined on the assignment valid on the ticket's created date (agents change shift/site).
"""
import pandas as pd, numpy as np, pathlib
D = pathlib.Path(__file__).resolve().parents[1] / "data"
FR_TARGET_MIN = {"chat": 15, "voice": 120, "social": 240, "email": 480}          # policy s3
CONTACT_COST  = {"chat": 210, "email": 260, "voice": 520, "social": 240}        # policy s4
BREACH_CREDIT, TRANSFER_COST, AGENT_HOUR = 350, 305, 165

def load(data_dir=D):
    data_dir = pathlib.Path(data_dir)
    t = pd.read_csv(data_dir/"tickets.csv")
    raw_rows = len(t)
    t["_pri"] = (t.source_system == "helpdesk").astype(int)
    t = t.sort_values(["ticket_id", "_pri"], ascending=[True, False]).drop_duplicates("ticket_id").drop(columns="_pri")
    for c in ["created_at", "first_response_at", "resolved_at"]:
        t[c] = pd.to_datetime(t[c])
    # legacy-only rows: UTC -> IST, and CSAT 0 -> blank
    leg = t.source_system == "legacy_fd"
    t.loc[leg, "resolved_at"] += pd.Timedelta(hours=5, minutes=30)
    t.loc[t.csat_score == 0, "csat_score"] = np.nan
    t["fr_min"] = (t.first_response_at - t.created_at).dt.total_seconds() / 60
    t["res_hours"] = (t.resolved_at - t.created_at).dt.total_seconds() / 3600
    t["fr_target"] = t.channel.map(FR_TARGET_MIN)
    t["breach"] = t.fr_min > t.fr_target
    t["contact_cost"] = t.channel.map(CONTACT_COST)
    t["month"] = t.created_at.dt.to_period("M").astype(str)
    t["week"] = t.created_at.dt.to_period("W-SUN").dt.start_time
    t["hour"] = t.created_at.dt.hour
    t["is_refund"] = t.refund_amount_inr.notna()
    t["is_repl"] = t.replacement_issued.eq("Y")

    # order link
    o = pd.read_csv(data_dir/"orders.csv", parse_dates=["order_date"])
    t = t.merge(o[["order_id", "order_date", "order_value_inr", "lot_code", "qty", "channel"]].rename(columns={"channel": "order_channel"}),
                on="order_id", how="left")
    t["order_link"] = np.where(t.order_id.notna(), "exact", "none")
    t["order_id_used"] = t.order_id
    miss = t.order_id.isna()
    oo = o.sort_values("order_date").rename(columns={"sku": "product_sku"})
    cand = t.loc[miss, ["ticket_id", "customer_id", "product_sku", "created_at"]].sort_values("created_at")
    j = pd.merge_asof(cand, oo, left_on="created_at", right_on="order_date",
                      by=["customer_id", "product_sku"], direction="backward").dropna(subset=["order_id"]).set_index("ticket_id")
    for col in ["order_id", "lot_code", "order_date", "order_value_inr"]:
        fill = t.ticket_id.map(j[col])
        dst = "order_id_used" if col == "order_id" else col
        t[dst] = t[dst].where(t[dst].notna(), fill)
    t.loc[miss & t.ticket_id.isin(j.index), "order_link"] = "inferred"
    # roster (valid assignment on created date)
    a = pd.read_csv(data_dir/"agents.csv", parse_dates=["from_date", "to_date"])
    a["to_date"] = a.to_date.fillna(pd.Timestamp("2100-01-01"))
    t["cdate"] = t.created_at.dt.normalize()
    m = t[["ticket_id", "agent_id", "cdate"]].merge(a, on="agent_id", how="left")
    m = m[(m.cdate >= m.from_date) & (m.cdate <= m.to_date)].drop_duplicates("ticket_id")
    t = t.merge(m[["ticket_id", "name", "site", "team", "shift", "tier"]].rename(columns={"team": "agent_team", "name": "agent_name", "shift": "agent_shift", "site": "agent_site"}),
                on="ticket_id", how="left")
    t.attrs["raw_rows"] = raw_rows
    return t

if __name__ == "__main__":
    t = load()
    print(t.attrs["raw_rows"], "->", len(t), "unique tickets")
    print("negative resolution times after fix:", (t.res_hours < 0).sum())
    print("roster match:", t.agent_shift.notna().mean().round(4))
    print(t.order_link.value_counts().to_dict())
