# Evaluation report (synthetic data)

Engine run with default tolerances: `{'qty_review_pct': 1.5, 'qty_hold_pct': 5.0, 'rate_hold_pct': 0.5, 'pct_review_pts': 1.0, 'pct_hold_pts': 5.0, 'tm_review_pct': 0.0, 'tm_hold_pct': 10.0, 'money_tol': 1.0}`

## Detection by rule

| rule                  |   planted |   flagged |   true_pos |   false_pos |   missed |   precision_pct |   recall_pct |
|:----------------------|----------:|----------:|-----------:|------------:|---------:|----------------:|-------------:|
| DUPLICATE_INVOICE     |         3 |         3 |          3 |           0 |        0 |           100   |          100 |
| EXTENSION_ERROR       |         9 |         9 |          9 |           0 |        0 |           100   |          100 |
| PCT_COMPLETE_OVERBILL |        11 |        12 |         11 |           1 |        0 |            91.7 |          100 |
| PER_DIEM_OVER_POLICY  |         5 |         5 |          5 |           0 |        0 |           100   |          100 |
| QTY_OVER_RECEIPT      |        14 |        14 |         14 |           0 |        0 |           100   |          100 |
| RATE_OVER_CONTRACT    |         3 |         3 |          3 |           0 |        0 |           100   |          100 |
| RETAINAGE_ERROR       |         3 |         3 |          3 |           0 |        0 |           100   |          100 |
| TM_OVER_APPROVED      |        15 |        15 |         15 |           0 |        0 |           100   |          100 |
| UNAPPROVED_CO         |         4 |         4 |          4 |           0 |        0 |           100   |          100 |
| ALL RULES             |        67 |        68 |         67 |           1 |        0 |            98.5 |          100 |

## Invoice-level gate outcome

| has_error         |   PASS |   REVIEW |   HOLD |
|:------------------|-------:|---------:|-------:|
| Clean             |     66 |        1 |      0 |
| Has planted error |      0 |        2 |     48 |

**Planted overbilling caught:** $17,516,006 of $17,516,006 (100.0%)

## Missed errors

None.

## False alarms

| invoice_id   |   line_no | rule                  | severity   |   variance |   amount_at_risk | detail                       |
|:-------------|----------:|:----------------------|:-----------|-----------:|-----------------:|:-----------------------------|
| INV-1031     |         8 | PCT_COMPLETE_OVERBILL | REVIEW     |        1.1 |          10866.3 | Billed 4.1% vs verified 3.0% |

## Quantity tolerance trade-off

|   tolerance_pct |   precision_pct |   recall_pct |   false_pos |   missed |
|----------------:|----------------:|-------------:|------------:|---------:|
|            0    |             7.9 |        100   |         163 |        0 |
|            0.25 |            13.7 |        100   |          88 |        0 |
|            0.5  |            29.8 |        100   |          33 |        0 |
|            0.75 |            53.8 |        100   |          12 |        0 |
|            1    |            73.7 |        100   |           5 |        0 |
|            1.25 |           100   |        100   |           0 |        0 |
|            1.5  |           100   |        100   |           0 |        0 |
|            1.75 |           100   |        100   |           0 |        0 |
|            2    |           100   |        100   |           0 |        0 |
|            2.25 |           100   |        100   |           0 |        0 |
|            2.5  |           100   |        100   |           0 |        0 |
|            2.75 |           100   |        100   |           0 |        0 |
|            3    |           100   |        100   |           0 |        0 |
|            3.25 |           100   |        100   |           0 |        0 |
|            3.5  |           100   |         92.9 |           0 |        1 |
|            3.75 |           100   |         92.9 |           0 |        1 |
|            4    |           100   |         92.9 |           0 |        1 |
|            4.25 |           100   |         92.9 |           0 |        1 |
|            4.5  |           100   |         92.9 |           0 |        1 |
|            4.75 |           100   |         92.9 |           0 |        1 |
|            5    |           100   |         92.9 |           0 |        1 |
|            5.25 |           100   |         92.9 |           0 |        1 |
|            5.5  |           100   |         92.9 |           0 |        1 |
|            5.75 |           100   |         92.9 |           0 |        1 |
|            6    |           100   |         78.6 |           0 |        3 |

![tolerance trade-off](tolerance_tradeoff.png)