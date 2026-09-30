"""Shared feature build: cleaned tickets + themes + repeat-contact flags."""
import pandas as pd, numpy as np
from .clean import load
from .classify import add_themes

def build(data_dir=None):
    t = add_themes(load() if data_dir is None else load(data_dir))
    t = t.sort_values(["customer_id", "theme", "created_at"]).reset_index(drop=True)
    t["res_or_cr"] = t.resolved_at.fillna(t.created_at)
    g = t.groupby(["customer_id", "theme"])
    gap = (t.created_at - g.res_or_cr.shift(1)).dt.total_seconds() / 86400
    t["is_repeat"] = gap.between(-2, 30) & (t.theme != "unclassified")          # this ticket is a repeat of an earlier one
    nxt = (g.created_at.shift(-1) - t.res_or_cr).dt.total_seconds() / 86400
    t["came_back"] = nxt.between(-2, 30) & (t.theme != "unclassified")          # a repeat followed this ticket
    return t.sort_values("created_at").reset_index(drop=True)
