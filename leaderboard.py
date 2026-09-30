"""Agent leaderboard, built to be fair rather than literal.

Priya asked for tickets closed per week. Raw volume mostly measures which TEAM an agent sits in
(Billing/Logistics/Returns ~5.3-5.5 tickets/agent/week vs Chat ~2.9, Voice ~2.6), and Tier 2 is explicitly excluded from
volume comparison (policy s6, Neha's email). So:
  * Tier 1 agents are ranked only against teammates on the same team.
  * Volume is shown next to quality (CSAT, repeat rate), and the score is a within-team z-score of volume, CSAT and no-repeat rate.
  * Tier 2 is shown separately on median days to resolve, never ranked against Tier 1.
  * SLA breaches are shown as context only: they are caused by queue timing, not by the resolving agent (policy s3).
"""
import pandas as pd, numpy as np, pathlib
from .features import build
from . import payout_guard
OUT = pathlib.Path(__file__).resolve().parents[1] / "out"

def table(t: pd.DataFrame, products: pd.DataFrame):
    done = t[t.status.isin(["resolved", "closed"])].copy()
    weeks = ((t.created_at.max() - t.created_at.min()).days + 1) / 7
    leaks = payout_guard.find(t, products)
    later = set()
    for tks in leaks.tickets:
        ids = tks.split(","); later.update(ids[1:])
    done["second_payout"] = done.ticket_id.isin(later) & (done.is_refund | done.is_repl)
    a = done.groupby(["agent_id", "agent_name", "agent_team", "agent_site", "agent_shift", "tier"]).agg(
        closed=("ticket_id", "size"), resolved_by_agent=("status", lambda x: (x == "resolved").sum()),
        auto_closed_share=("status", lambda x: (x == "closed").mean()), median_handle_h=("res_hours", "median"),
        csat=("csat_score", "mean"), csat_n=("csat_score", "count"), came_back=("came_back", "mean"),
        breach=("breach", "mean"), second_payouts=("second_payout", "sum")).reset_index()
    a["per_week"] = a.closed / weeks
    a["handle_days"] = a.median_handle_h / 24
    t1 = a[a.tier == 1].copy()
    z = lambda s: (s - s.mean()) / (s.std(ddof=0) or 1)
    g = t1.groupby("agent_team")
    t1["z_volume"] = g.per_week.transform(z); t1["z_csat"] = g.csat.transform(z); t1["z_noreturn"] = -g.came_back.transform(z)
    t1["score"] = (0.4 * t1.z_volume + 0.3 * t1.z_csat + 0.3 * t1.z_noreturn).round(2)
    t1["team_rank"] = g.score.rank(ascending=False, method="min").astype(int)
    t1["team_size"] = g.agent_id.transform("size")
    t1["note"] = np.where(t1.csat_n < 40, "few CSAT responses", "")
    t2 = a[a.tier == 2].sort_values("handle_days")
    raw = a.sort_values("per_week", ascending=False)
    return t1.sort_values(["agent_team", "team_rank"]), t2, raw, weeks

def render(t1, t2, raw, weeks):
    f = lambda d: d.round(2).to_markdown(index=False)
    L = ["# Agent leaderboard", "",
         f"Data window: {weeks:.0f} weeks. 'Closed' = status resolved or closed (auto-closed after 72h counts; share shown).", "",
         "## Tier 1: ranked within team only", "",
         "Score = 40% volume, 30% CSAT, 30% not-coming-back, each as a z-score against teammates on the same team. Scores are only comparable within a team.", ""]
    cols = ["agent_team", "team_rank", "agent_name", "agent_shift", "agent_site", "per_week", "csat", "csat_n", "came_back", "median_handle_h", "auto_closed_share", "second_payouts", "score", "note"]
    for team, d in t1.groupby("agent_team"):
        L += [f"### {team}", "", f(d[cols[1:]]), ""]
    L += ["## Tier 2 (Escalations & Warranty): resolution time, not volume", "", f(t2[["agent_name", "agent_shift", "agent_site", "closed", "handle_days", "csat", "csat_n", "came_back"]]), "",
          "## For reference: the ranking as literally requested (tickets closed per week)", "",
          "Do not act on this table. It ranks teams and queue mix, not effort: the top 3 are in Billing, Returns and Logistics and Tier 2 is at the bottom by design.", "",
          f(raw.head(12)[["agent_name", "agent_team", "tier", "per_week", "csat"]]), ""]
    return "\n".join(L)

if __name__ == "__main__":
    t = build(); p = pd.read_csv("data/products.csv")
    t1, t2, raw, w = table(t, p); OUT.mkdir(exist_ok=True)
    (OUT / "leaderboard.md").write_text(render(t1, t2, raw, w), encoding="utf-8")
    t1.to_csv(OUT / "leaderboard_tier1.csv", index=False); t2.to_csv(OUT / "leaderboard_tier2.csv", index=False)
    print(t1.groupby("agent_team").apply(lambda d: d[["agent_name","per_week","csat","came_back","score"]].round(2).head(3)).to_string())
