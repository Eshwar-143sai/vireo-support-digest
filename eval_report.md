# Classifier evaluation

Accuracy **as audited** (rules as they were when each sample was drawn; samples 2 and 3 were unseen by the rules they scored):

|   sample | rules_version   |   n |   theme_acc |   family_acc |   current_rules_on_same_rows |
|---------:|:----------------|----:|------------:|-------------:|-----------------------------:|
|        1 | rules v1        | 126 |       0.825 |        0.889 |                        0.984 |
|        2 | rules v2        | 100 |       0.89  |        0.91  |                        0.99  |
|        3 | rules v3        |  79 |       0.899 |        0.911 |                        1     |

Pooled unseen samples 2+3: 89.4% theme-correct (160/179); family-level 91.1%.
`current_rules_on_same_rows` is NOT accuracy: those rows were used to fix the rules afterwards. It is a regression check.

## Where it still gets things wrong
- Heavy typos on rare phrasing (e.g. 'flul to epmty').
- Messages where the product name is the only keyword (e.g. 'charging case' in an order-status complaint) rely on ordering rules, so new phrasings can slip.
- Notes-only fallback (about 18% of tickets have no keyword in the customer message): agent notes describe what the agent *did*, which can differ from what the customer *asked*.
- Ambiguous delivery vs pickup ('waiting for your courier' can be a delivery or a return pickup).

## Bot tag vs what customers wrote
- Bot tag agrees with the reader-derived family on 86.6% of tickets it did not tag 'Other'.
- 14.2% of tickets are tagged 'Other'; 99.1% of those have an identifiable issue in the text.
- Tickets still unclassified after rules: 1.2%.
