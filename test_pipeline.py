import unittest, sys, pathlib
import pandas as pd
ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from src.classify import classify, normalise
from src import payout_guard

class TestClassify(unittest.TestCase):
    def test_typo_and_boilerplate(self):
        self.assertEqual(classify("need GST invoice for my order, i want my money back", "")[0], "invoice_gst")   # boilerplate must not trigger refund
        self.assertEqual(classify("crackling sound in the right side", "")[0], "audio_noise")                    # 'crackling' must not be repaired to 'tracking'
        self.assertEqual(classify("hello ji i haven't received my order", "")[0], "order_not_received")
        self.assertEqual(classify("two entries of Rs 2499 for one pair of earbuds", "")[0], "payment_issue")   # 'pair of' is not pairing
        self.assertEqual(classify("I fully charged and discharged twice, battery life dropped", "")[0], "battery_drain")
    def test_family_of_unclassified(self):
        self.assertEqual(classify("hello", "ok")[0], "unclassified")

class TestPayout(unittest.TestCase):
    def _t(self, rows):
        base = dict(order_link="exact", is_refund=False, is_repl=False, refund_amount_inr=float("nan"), refund_reason_code=None, order_value_inr=1000.0,
                    created_at=pd.Timestamp("2026-01-01"), product_sku="S", ticket_id="x", order_id="O1")
        return pd.DataFrame([{**base, **r} for r in rows])
    P = pd.DataFrame({"sku": ["S"], "unit_cost_inr": [1000]})
    def test_dup_payment_refund_is_legit(self):
        t = self._t([dict(ticket_id="a", is_refund=True, refund_amount_inr=1000.0, refund_reason_code="RETURN-QC-OK"),
                     dict(ticket_id="b", is_refund=True, refund_amount_inr=1000.0, refund_reason_code="DUP-PAYMENT")])
        self.assertEqual(len(payout_guard.find(t, self.P)), 0)
    def test_two_refunds_over_value(self):
        t = self._t([dict(ticket_id="a", is_refund=True, refund_amount_inr=1000.0, refund_reason_code="RETURN-QC-OK"),
                     dict(ticket_id="b", is_refund=True, refund_amount_inr=600.0, refund_reason_code="CANCEL")])
        self.assertEqual(payout_guard.find(t, self.P).leak_inr.iloc[0], 600)
    def test_refund_plus_replacement(self):
        t = self._t([dict(ticket_id="a", is_refund=True, refund_amount_inr=1000.0, refund_reason_code="DOA-REPL"), dict(ticket_id="b", is_repl=True)])
        self.assertEqual(payout_guard.find(t, self.P).leak_inr.iloc[0], 1340)   # unit cost + Rs 340 (policy s5)

@unittest.skipUnless((ROOT / "data/tickets.csv").exists(), "needs data/")
class TestData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.features import build; cls.t = build()
    def test_dedupe(self):  self.assertEqual(self.t.ticket_id.is_unique, True)
    def test_no_negative_resolution(self):  self.assertEqual(int((self.t.res_hours < 0).sum()), 0)
    def test_csat_zero_is_blank(self):  self.assertEqual(int((self.t.csat_score == 0).sum()), 0)
    def test_regression_vs_hand_audit(self):
        from src.evaluate import run
        g, _ = run(write=False); self.assertGreater(g.current_rules_on_same_rows.min(), 0.97)

if __name__ == "__main__": unittest.main()
