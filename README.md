# Vireo support digest

Weekly "what are customers complaining about" digest, a fair agent leaderboard, and a duplicate-payout detector, built from Vireo's 18-month ticket export. Plain Python, no API keys, no paid model calls, ~12 s per run.

## Run it (clean machine)

```bash
python3 -m venv .venv && source .venv/bin/activate      # Python 3.10+
pip install -r requirements.txt
# copy the Vireo export into ./data/  : tickets.csv agents.csv orders.csv customers.csv products.csv
python run.py                                            # writes ./out (private) and ./sample_output (no customer text)
python -m unittest discover -s tests                     # 9 tests, ~10 s
python -m src.digest --week 2026-06-15                   # digest for any Monday
```

The client CSVs are deliberately **not** in this repo (customer data). `run.py` tells you if any are missing.

## What you get

| Output | File | What it is |
|---|---|---|
| Weekly digest | `out/digests/digest_<monday>.md` | Top complaint themes vs the last 4 weeks, rising issues, mis-tagged "Other" tickets, issues customers come back about, orders paid out twice this week, lot watch, SLA. Public sample: `sample_output/` |
| Leaderboard | `out/leaderboard.md` | Tier 1 ranked **within team**; Tier 2 on days-to-resolve; the raw tickets-per-week table for reference with a warning |
| Business case | `out/business_case.json`, `out/second_payouts.csv` | Every rupee figure in the memo, and the list of 130 orders paid out twice |
| Accuracy | `out/eval_report.md` | Hand-audit results (see below) |

## How it works

`src/clean.py` fixes the data traps documented in the policy/README: 653 duplicate ticket IDs (keep the helpdesk copy), legacy `resolved_at` in UTC (+5h30; 2,263 rows were "resolved before created", now 0), legacy CSAT `0` = no response, order link (quoted `order_id`, else latest earlier order for the same customer+SKU, flagged "inferred"), roster join by date. `src/classify.py` reads **what the customer wrote** (falls back to the agent's note) with typo repair and boilerplate stripping and assigns one of 25 issue themes; the bot's own tag is wrong or "Other" often enough to be useless for this. `src/payout_guard.py` finds orders paid out twice. `src/digest.py`, `src/leaderboard.py`, `src/business_case.py`, `src/evaluate.py` build the outputs.

**Why rules and not an LLM per ticket:** Finance asked for no per-ticket model bill; the text is template-like with typos, which normalisation handles; rules are deterministic and auditable. `classify.llm_fallback()` marks where a batched cheap-model call would go for the ~1% unclassified. It is not implemented.

## How accurate is it

Three random samples (126, 100, 79 tickets), each drawn after the previous round of fixes. Labels are a **single-rater audit by an AI (Claude), not a gold standard**. Accuracy as audited: 82.5% (v1) → 89.0% (v2, unseen) → 89.9% (v3, unseen). Pooled unseen: **89.4% (160/179)** theme, 91% at family level. Labels: `data/labels/audit_labels.csv`. Full write-up: `sample_output/eval_report.md`.

## Decisions and assumptions (read before trusting a number)

- **Contact cost** is the policy's channel figures (Rs 210/260/520/240), not Finance's Rs 180. The payout number does not depend on it.
- **Second payout** = an order with a refund *and* a replacement, or refunds totalling more than the order value. `DUP-PAYMENT` and `PRICE-ADJ` refunds are excluded (they are legitimate top-ups). Only orders where the customer quoted an order ID (no guessed joins) are counted, so it is a **lower bound**. Replacement cost = unit cost + Rs 340 (policy s5).
- **"70% preventable"** is an assumption, not a measurement; sensitivity shown in `business_case.json`.
- **Repeat contact** = same customer, same *theme*, within 30 days of the last resolution (policy s10).
- **Legacy timestamps:** +5h30 applied to legacy-only tickets. Refund units: no legacy/current discrepancy visible (refund/order value ratios match), so none applied.
- **Volume:** the export averages ~153 tickets/week, not the ~650 quoted. Figures here are for the export as given.
- **Lot defects:** one Pulse 2 lot stands out but does not survive correction for testing 1,270 lots; reported as "watch", not a finding.

## Not built (on purpose)

Dashboard/UI, LLM classification, a CSAT model, staffing model, transfer-routing analysis, live helpdesk integration (the real fix for payouts needs a check at refund time), inferred-order payout matching, anything about individual agents' notes.
