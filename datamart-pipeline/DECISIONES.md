# Architecture Decision Records (ADR) — DataMart S.A.S.

This document records the technical decisions and tradeoffs applied during the implementation of the ETL platform.

---

# ADR 001 — Layered ETL Architecture

## Status

Approved

## Context

Data ingestion, business transformations, and persistence have different responsibilities and should evolve independently.

## Decision

The platform was separated into:

* extract.py
* transform.py
* load.py

Orchestrated through:

```text
pipeline_datamart.py
```

Extraction only reads files.

Transformation contains business logic.

Load handles persistence.

## Consequences

Pros:

* Better maintainability
* Easier testing
* Clear ownership boundaries

---

# ADR 002 — Idempotent Loading Strategy

## Status

Approved

## Context

Airflow retries and DAG reruns can create duplicated records.

## Decision

Implemented two complementary mechanisms:

1. Delete records by process_date.
2. Execute PostgreSQL UPSERT.

Implementation:

```text
DELETE + ON CONFLICT DO UPDATE
```

## Consequences

Pros:

* Safe reruns
* Retry resilience
* No duplicated analytical records

Tradeoff:

* Additional write operations during execution.

---

# ADR 003 — Business Ambiguity Resolution

## Status

Approved

### Missing Customer IDs

Decision:

```text
UNKNOWN
```

Reason:

Preserve anonymous purchases.

---

### Canonical Product Names

Decision:

Use the most frequent normalized description.

Reason:

Remove text inconsistencies.

---

### Duplicate Transactions

Decision:

Use:

```text
invoice_no
product_code
invoice_date_utc
```

Priority source configured through:

```text
DUPLICATE_PRIORITY_SOURCE
```

Reason:

Avoid hardcoded business priorities.

---

# ADR 004 — Data Quality and Error Isolation

## Status

Approved

## Context

Operational datasets contain incomplete or inconsistent values.

## Decision

Invalid records are separated from valid datasets.

Rejected rows are persisted into:

```text
rejected_records
```

Additional patch:

Missing return dates are replaced using Airflow execution date.

## Consequences

Pros:

* Prevents pipeline interruption
* Maintains auditability
* Preserves analytical completeness

Tradeoff:

Patched dates should be interpreted carefully in edge-case analysis.

---

# ADR 005 — Analytical Warehouse Design

## Status

Approved

## Context

Business reporting required operational separation between sales and returns.

## Decision

Implemented analytical relational modeling.

Entities:

* products
* sales
* returns
* rejected_records

Design principles:

* Separate sales and returns
* Independent catalog
* Soft constraints
* Analytical indexes

Indexes:

```text
idx_sales_date
idx_sales_product
idx_sales_country
idx_returns_product
idx_returns_date
```

## Consequences

Pros:

* Faster analytical queries
* Easier revenue calculations
* Flexible ingestion
* Lower operational failures

---

# Final Notes

This implementation prioritizes:

* reproducibility
* idempotency
* traceability
* operational resilience
* analytical usability
