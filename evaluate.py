"""Score the classifier against the hand audit (data/labels/audit_labels.csv).

Protocol (see README): three random samples, each drawn AFTER the previous round of rule fixes, so each sample was
unseen by the rules it scored. Labels = my (Claude's) reading of customer_message + agent_notes; where the prediction looked right
I accepted it, where it looked wrong I wrote the correct theme. It is a single-rater audit, not a gold standard.
`delivery_delayed` and `order_not_received` are merged when scoring: customers and agents use them interchangeably.
"""
import pandas as pd, pathlib
from .features import build
from .classify import THEMES
ROOT = pathlib.Path(__file__).resolve().parents[1]
FAM = {n: f for n, f, _ in THEMES}; FAM["login_otp"] = "Account & Login"
merge = lambda x: "order_not_received" if x == "delivery_delayed" else x

def run(write=True):
    L = pd.read_csv(ROOT / "data/labels/audit_labels.csv"); L = L[L.judged]
    t = build().set_index("ticket_id")
    L["current"] = L.ticket_id.map(t.theme)
    L["ok_audit"] = L.predicted_at_audit.map(merge) == L.true_theme.map(merge)
    L["ok_now"] = L.current.map(merge) == L.true_theme.map(merge)
    L["fam_ok_audit"] = L.predicted_at_audit.map(FAM) == L.true_theme.map(FAM)
    g = L.groupby(["sample", "rules_version"]).agg(n=("ok_audit", "size"), theme_acc=("ok_audit", "mean"), family_acc=("fam_ok_audit", "mean"), current_rules_on_same_rows=("ok_now", "mean")).reset_index()
    tag = t.category.ne("Other") & t.theme.ne("unclassified")
    bot_family = {"Connectivity": "Connectivity", "Charging & Battery": "Charging & Battery", "Audio Quality": "Audio Quality", "App & Firmware": "App & Firmware",
                  "Delivery & Shipping": "Delivery & Shipping", "Billing & Payments": "Billing & Payments", "Returns & Refunds": "Returns & Refunds",
                  "Warranty & Repair": "Warranty & Repair", "Account & Login": "Account & Login", "Product Enquiry": "Product Enquiry"}
    fam = t.theme.map(FAM)
    agree = (t.category[tag].map(bot_family) == fam[tag]).mean()
    other = (t.category == "Other").mean(); other_ok = (t[t.category == "Other"].theme != "unclassified").mean()
    txt = ["# Classifier evaluation", "", "Accuracy **as audited** (rules as they were when each sample was drawn; samples 2 and 3 were unseen by the rules they scored):", "",
           g.round(3).to_markdown(index=False), "",
           f"Pooled unseen samples 2+3: {L[L['sample']>1].ok_audit.mean():.1%} theme-correct ({int(L[L['sample']>1].ok_audit.sum())}/{len(L[L['sample']>1])}); family-level {L[L['sample']>1].fam_ok_audit.mean():.1%}.",
           "`current_rules_on_same_rows` is NOT accuracy: those rows were used to fix the rules afterwards. It is a regression check.", "",
           "## Where it still gets things wrong", "- Heavy typos on rare phrasing (e.g. 'flul to epmty').", "- Messages where the product name is the only keyword (e.g. 'charging case' in an order-status complaint) rely on ordering rules, so new phrasings can slip.",
           "- Notes-only fallback (about 18% of tickets have no keyword in the customer message): agent notes describe what the agent *did*, which can differ from what the customer *asked*.",
           "- Ambiguous delivery vs pickup ('waiting for your courier' can be a delivery or a return pickup).", "", "## Bot tag vs what customers wrote",
           f"- Bot tag agrees with the reader-derived family on {agree:.1%} of tickets it did not tag 'Other'.", f"- {other:.1%} of tickets are tagged 'Other'; {other_ok:.1%} of those have an identifiable issue in the text.",
           f"- Tickets still unclassified after rules: {(t.theme=='unclassified').mean():.1%}."]
    if write: (ROOT / "out/eval_report.md").write_text("\n".join(txt) + "\n", encoding="utf-8")
    return g, txt

if __name__ == "__main__":
    g, txt = run(); print("\n".join(txt))
