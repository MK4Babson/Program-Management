# Data dictionary

One CSV per table. Blank templates are in `templates/`. Run `python src/validate_input.py --data <folder>` after filling them in.

**Formats:** periods `YYYY-MM`, dates `YYYY-MM-DD`, numbers without `$` or commas, retainage as a fraction (`0.10`).

## purchase_orders.csv

| Column | Type | Required | Meaning |
|---|---|---|---|
| `po_id` | str | yes | Unique contract / PO id |
| `project_id` | str | yes | Building or project the PO belongs to |
| `prime_id` | str | yes | Prime contractor id |
| `retainage_rate` | float | yes | Retainage as a fraction, e.g. 0.10 for 10% |
| `contract_type` | str | no | e.g. Unit price, Lump sum, GMP |

## po_lines.csv

| Column | Type | Required | Meaning |
|---|---|---|---|
| `po_id` | str | yes | PO this line belongs to |
| `item_code` | str | yes | Pay item / SOV code (for approved change orders, the CO id) |
| `line_source` | str | yes | CONTRACT or CHANGE_ORDER |
| `description` | str | yes | Item description |
| `unit` | str | yes | LF, CY, EA, TON, LS, ... |
| `contract_qty` | float | yes | Contract quantity (1 for lump sum) |
| `contract_unit_rate` | float | yes | Contract unit price (scheduled value for lump sum) |
| `scheduled_value` | float | yes | contract_qty x contract_unit_rate |
| `co_id` | str | no | Change order id when line_source = CHANGE_ORDER |

## change_orders.csv

| Column | Type | Required | Meaning |
|---|---|---|---|
| `co_id` | str | yes | Change order id |
| `po_id` | str | yes | PO it modifies |
| `status` | str | yes | APPROVED, PENDING or REJECTED |
| `approval_period` | str | yes | YYYY-MM it was approved (blank if not approved) |
| `co_qty` | float | no | Quantity |
| `co_unit_rate` | float | no | Unit rate |
| `co_amount` | float | no | Total value |
| `description` | str | no | What the change is |

## tm_preapprovals.csv

| Column | Type | Required | Meaning |
|---|---|---|---|
| `approval_id` | str | yes | Pre-approval id referenced by T&M invoice lines |
| `po_id` | str | yes | PO |
| `period` | str | yes | YYYY-MM |
| `craft` | str | no | Labor craft |
| `approved_hours` | float | yes | Hours approved |
| `approved_rate` | float | no | Approved hourly rate |

## goods_receipts.csv

| Column | Type | Required | Meaning |
|---|---|---|---|
| `grn_id` | str | yes | Receipt / field verification id referenced by invoice lines |
| `po_id` | str | yes | PO |
| `item_code` | str | yes | Pay item verified |
| `period` | str | yes | YYYY-MM |
| `verified_qty` | float | yes | Quantity verified this period (blank for lump sum) |
| `verified_pct_complete_cum` | float | yes | Verified cumulative % complete (lump sum only) |

## invoices.csv

| Column | Type | Required | Meaning |
|---|---|---|---|
| `invoice_id` | str | yes | Unique system id for the invoice |
| `invoice_number` | str | yes | Contractor's invoice / pay app number |
| `po_id` | str | yes | PO billed |
| `project_id` | str | yes | Project |
| `prime_id` | str | yes | Prime contractor |
| `period` | str | yes | Billing period YYYY-MM |
| `invoice_date` | str | yes | YYYY-MM-DD |
| `gross_amount` | float | yes | Sum of line amounts |
| `retainage_withheld` | float | yes | Retainage withheld on this invoice |
| `net_amount` | float | yes | gross - retainage |

## invoice_lines.csv

| Column | Type | Required | Meaning |
|---|---|---|---|
| `invoice_id` | str | yes | Invoice |
| `line_no` | int | yes | Line number within the invoice |
| `line_type` | str | yes | SOV, CO, TM or PER_DIEM |
| `ref_id` | str | yes | SOV: item_code | CO: co_id | TM: approval_id | PER_DIEM: any |
| `description` | str | yes | Line description |
| `unit` | str | yes | Unit (LS for lump sum) |
| `qty` | float | yes | Quantity billed this period (blank for lump sum) |
| `unit_rate` | float | yes | Unit rate billed (blank for lump sum) |
| `amount` | float | yes | Amount billed |
| `pct_complete_prev` | float | yes | Lump sum: % complete billed before this invoice |
| `pct_complete_cum` | float | yes | Lump sum: cumulative % complete billed |
| `grn_id` | str | yes | Receipt id this SOV line should be matched to |

## primes.csv (optional)

| Column | Type | Required | Meaning |
|---|---|---|---|
| `prime_id` | str | yes | Prime id |
| `prime_name` | str | yes | Prime name |

## projects.csv (optional)

| Column | Type | Required | Meaning |
|---|---|---|---|
| `project_id` | str | yes | Project id |
