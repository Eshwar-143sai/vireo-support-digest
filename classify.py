"""Rules-first issue classifier for customer_message + agent_notes.

Why rules and not a per-ticket LLM call: (a) Finance (Arjun) asked for no per-ticket model bill,
(b) the text is template-driven with typo/Hinglish noise, which normalisation + fuzzy token repair handles,
(c) it is deterministic and auditable. `llm_fallback()` is a stub showing where a batch model call
would go for the unmatched residue; it is OFF by default (cost Rs 0).
"""
import re, difflib, pandas as pd

# theme -> (family, regex). Order matters: first match wins, most specific first.
THEMES = [
 # specific / high-precision rules first
 ("login_otp",         "Account & Login",    r"login code|code never arriv|code and my phon|sent me a code|otp|locked out|cannot log ?in|cant log ?in|unable to log|log ?in issue|password"),
 ("damaged_in_transit","Delivery & Shipping",r"crushed|dent on the case|kicked|damaged product|received damaged|arrived damaged|damaged in transit|transit damage|damage in transit|parcel looked|unit rcvd damaged|dented"),
 ("payment_issue",    "Billing & Payments", r"\bcharged (twice|two times|2 times)|two entries|entries of rs|went to you|no orders|card charged|double (charge|payment)|duplicate payment|same amount twice"),
 ("cancellation",      "Returns & Refunds",  r"stop the shipment|don.?t ship|do not ship|change of mind|ordered by mistake|ordered the wrong|without asking|please cancel|want to cancel|cancel my order|cancel order|cancellation request"),
 ("refund_not_received","Returns & Refunds",  r"refund (not|hasn|pending|delay|was promised)|not (rec\w*|credited).{0,15}refund|picked up the item|you picked up|money hasn.?t|amount is nowhere|return (was )?accepted|still waiting for my (refund|money)|where is the money"),
 ("hardware_defect",   "Build & Hardware",   r"display (just )?ignores|unrespon|not responding|ignores my finger|touch|lights up but|strap|\bband (snapped|broke)|snapped|peeling|screen (crack|flicker)|display (dead|flicker|crack)|tearing|hinge|metal pin|pin fell"),
 ("charging_case",     "Charging & Battery", r"case (wont|will not|not|no|is|does not|doesnt)? ?(charg|led|dead)|case no led|case led|nothing on the case|plugging in does nothing|replacement case.*charg"),
 ("bud_not_charging",  "Charging & Battery", r"(left|right) one (just )?does|\b(left|right|l|r) (ear)?bud\b.*(charg|paperweight|dead)|charg.*(left|right) bud|bud .*no charge|paperweight|(left|right) side (not|wont|won.?t) charg|(left|right) (one|earbud) .*(not charg|dead every)|0 percent|green light|one of them .*(left|right)"),
 ("battery_drain",     "Charging & Battery", r"battery|drain|backup|charge it twice|dies fast|full to empty|lunchtime|dies by|dise by|barely lasts|lasts \d+ hours"),
 ("device_dead",       "Charging & Battery", r"unit dead|dead unit|will not turn on|wont turn on|not turning on|button does|does nothing|no power|bricked|not charging at all"),
 ("pairing_failure",   "Connectivity",       r"wifi setup|new one it just blinks|\bpair(?!s? of\b)|discover|not (see|show)\w* .*list|device list|vanish|doesnt see|does not see|list anymore|not detect|connecting screen"),
 ("connection_drops",  "Connectivity",       r"stutter|disconnect|dropout|drop out|connection drop|drops constantly|losing my phone|goes silent|silent for a second|bt drop|cutting out|cuts out|intermittent|walk to the other room"),
 ("audio_noise",       "Audio Quality",      r"crackl|distort|hiss|static|frying|tuned radio|noise|buzz"),
 ("audio_one_side",    "Audio Quality",      r"one direction|one side|single side|side silent|only one|no sound from the|no audio|left side|right side|silent (left|right)|(left|right) (earbud|bud) (completely )?silent|(left|right) earbud complet"),
 ("mic_issue",         "Audio Quality",      r"microphone|\bmic\b|cannot hear me|cant hear me|people cannot hear|underwater|pickup low"),
 ("app_crash",         "App & Firmware",     r"\bapp\b.*(crash|open|white screen|load|freez|stuck|closes)|crash|loading screen|white screen|spinning circle"),
 ("firmware_update",   "App & Firmware",     r"progress bar|firmware|\bfw\b|update (hang|stuck|fail)|stuck at \d+|update hang"),
 ("order_not_received","Delivery & Shipping",r"not (been )?(deliver|receiv|rcvd)|nt deliver|tracking|out for delivery|marked delivered|haven.?t received|never arrived|shipment|waiting for your courier|sitting at home|nobody in my house|stuck on shipped|status stuck|still waiting for something to show up|nothing in hand"),
 ("delivery_delayed",  "Delivery & Shipping",r"delay|dlvry|\blate\b"),
 ("wrong_item_address","Delivery & Shipping",r"wrong (pincode|address|item|product|variant|colou?r)|different colou?r|got white|incorrect product|moved house|old flat|address (update|change)|update my ship|change (my )?(delivery )?address|pincode|flat number"),
 ("return_pickup",     "Returns & Refunds",  r"pickup|pick up|reverse pick|nobody came|rescheduled|packed the box"),
 ("refund_not_received","Returns & Refunds", r"refund|money for the return|amount is nowhere|return (was )?accepted|money hasn.?t come|hasn.?t come back|still waiting for my money"),
 ("cancellation",      "Returns & Refunds",  r"cancel|without asking|please reverse|ordered by mistake|ordered the wrong"),
 ("payment_issue",     "Billing & Payments", r"same amount twice|bank says|paid once|statement disagrees|deduct|debited|double (charge|payment)|charged twice|payment (went|failed)|failed order|no order (id|confirmation)|page failed|upi|money debited|amount deducted"),
 ("coupon_discount",   "Billing & Payments", r"coupon|promo|discount|offer price|20% off|promised|festive offer|offer (has )?vanish|clicked pay"),
 ("invoice_gst",       "Billing & Payments", r"invoice|\bgst|gstin|bill copy|need the bill|tax bill|accounts team"),
 ("login_otp_broad",   "Account & Login",    r"login|log in|sign in|\baccount\b"),
 ("repair_warranty",   "Warranty & Repair",  r"sent the unit in|repair|warranty|\brma\b|service cent|claim"),
 ("presales_compat",   "Product Enquiry",    r"compatib|before i buy|pre.?sales|will this|will the|work with|survive|talk to|enquiry|inquiry|spec|connect two"),
]
_C = [(n if n != "login_otp_broad" else "login_otp", f, re.compile(p, re.I)) for n, f, p in THEMES]

# vocabulary used for typo repair: whole words only, so ordinary words are never "corrected" into keywords
_VOCAB = ["pairing","bluetooth","discoverable","disconnecting","disconnects","dropouts","charging","battery","draining","firmware","update","crashing",
 "delivered","delivery","received","tracking","courier","refund","payment","deducted","debited","invoice","coupon","discount","warranty","repair",
 "cancel","cancellation","pickup","damaged","transit","crackling","distortion","static","silent","microphone","earbud","earbuds","replacement",
 "address","account","password","login","arrives","arrived","screen","display","strap","empty","commute","shipment","ordered","compatible",
 "amount","twice","waiting","charge","hardware","stuck","loading","crushed","cracked","order","phone","completely","decoration","paperweight"]
_repair_cache = {}
def _repair(tok):
    if len(tok) < 5 or not tok.isalpha() or tok in _VOCAB: return tok
    if tok in _repair_cache: return _repair_cache[tok]
    cand = [v for v in _VOCAB if v[0] == tok[0] and abs(len(v) - len(tok)) <= 2]
    m = difflib.get_close_matches(tok, cand, n=1, cutoff=0.85)
    _repair_cache[tok] = m[0] if m else tok
    return _repair_cache[tok]

# customers append demand/closing boilerplate to ANY complaint ("i want my money back"); it says nothing about the issue.
_BOILER = re.compile(r"i want (my money back|a replacement or refund,? nothing else|a replacement|a refund)|i request you to (kindly arrange a replacement|\w+ a refund to my original payment method|provide a resolution within \d+ working days|look into this matter at the earliest)|expected: ?\w+|request you to .{0,30}refund.{0,30}|escalate this to someone senior|please call me on my registered number|fix this or i am posting on twitter|refund\. now|replacement\. escalate|refund\.? ?$", re.I)

def normalise(s: str) -> str:
    s = _BOILER.sub(" ", str(s))
    s = s.lower()
    s = re.sub(r"(.)\1{2,}", r"\1\1", s)              # sooo -> soo
    s = re.sub(r"\[ivr transcript\]", " ", s)
    return " ".join(_repair(w) for w in re.findall(r"[a-z0-9%']+|[^\sa-z0-9]", s)).replace(" ' ", "'")

def _first_match(text):
    for name, fam, rx in _C:
        if rx.search(text): return name, fam
    return None, None

def classify(msg, note):
    """Return (theme, family, source). Customer words win; agent note is the fallback."""
    m = normalise(msg); n = normalise(note)
    th, fam = _first_match(m)
    if th: return th, fam, "message"
    th, fam = _first_match(n)
    if th: return th, fam, "note"
    return "unclassified", "Unclassified", "none"

REPEAT_RX = re.compile(r"(second|third|fourth|fifth|2nd|3rd|4th|5th) time|writing again|same (problem|thing|issue) again|issue is back|already told|told your colleague|nth time", re.I)
def repeat_signal(msg): return bool(REPEAT_RX.search(str(msg)))

def llm_fallback(rows):
    """Placeholder for a batched cheap-model call on 'unclassified' rows (disabled: cost Rs 0)."""
    raise NotImplementedError

def add_themes(t: pd.DataFrame) -> pd.DataFrame:
    out = [classify(m, n) for m, n in zip(t.customer_message, t.agent_notes)]
    t = t.copy()
    t["theme"], t["family"], t["theme_src"] = zip(*out)
    t["cust_repeat_signal"] = t.customer_message.map(repeat_signal)
    return t
