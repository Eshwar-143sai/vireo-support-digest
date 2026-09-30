"""One command: python run.py   (needs the 5 CSVs in ./data/, see README)"""
import sys, pathlib, shutil, json, time
import pandas as pd
ROOT = pathlib.Path(__file__).parent
NEED = ["tickets.csv", "agents.csv", "orders.csv", "customers.csv", "products.csv"]
missing = [f for f in NEED if not (ROOT / "data" / f).exists()]
if missing: sys.exit(f"Missing in ./data/: {', '.join(missing)}. Copy the Vireo export CSVs there and re-run.")
sys.path.insert(0, str(ROOT))
from src.features import build
from src import digest, leaderboard, business_case, evaluate

t0 = time.time(); out = ROOT / "out"; out.mkdir(exist_ok=True)
t = build(); prods = pd.read_csv(ROOT / "data/products.csv"); orders = pd.read_csv(ROOT / "data/orders.csv", parse_dates=["order_date"])
end = t.created_at.max().normalize(); last_week = end - pd.Timedelta(days=end.weekday()) - pd.Timedelta(weeks=1)
files = [digest.make(last_week - pd.Timedelta(weeks=i), t, orders, prods) for i in range(3, -1, -1)]
pub = ROOT / "sample_output"; pub.mkdir(exist_ok=True)
digest.make(last_week, t, orders, prods, out_dir=pub, quotes=False)
t1, t2, raw, w = leaderboard.table(t, prods); (out / "leaderboard.md").write_text(leaderboard.render(t1, t2, raw, w), encoding="utf-8")
bc, leaks = business_case.compute(t, prods); (out / "business_case.json").write_text(json.dumps(bc, indent=2, default=str)); leaks.to_csv(out / "second_payouts.csv")
g, txt = evaluate.run(); shutil.copy(out / "eval_report.md", pub / "eval_report.md"); shutil.copy(out / "business_case.json", pub / "business_case.json")
p = bc["payout"]
print(f"Done in {time.time()-t0:.0f}s. Outputs in ./out (private) and ./sample_output (no customer text).")
print(f"  {bc['tickets']:,} unique tickets | latest digest: {files[-1].name}")
print(f"  Second payouts: {p['leak_orders']} orders, Rs {p['leak_inr_total']:,} ({p['leak_rate']:.1%} of paid orders); Rs {p['leak_inr_per_quarter']:,}/quarter; target 2% = Rs {p['saving_per_quarter_at_target']:,}/quarter")
