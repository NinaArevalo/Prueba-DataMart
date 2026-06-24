# DataMart S.A.S. — ETL Data Pipeline

This repository contains an end-to-end ETL pipeline developed for **DataMart S.A.S.** to consolidate operational e-commerce data into a structured PostgreSQL analytical repository.

The solution is containerized using Docker and orchestrated with Apache Airflow.

---

# Project Overview

The objective of this project is to:

* Extract transactional information from multiple CSV sources.
* Standardize and clean heterogeneous schemas.
* Apply business validation rules and quality controls.
* Build analytical entities for reporting.
* Persist curated datasets into PostgreSQL.

The pipeline follows a layered architecture:

```text
Raw CSV
   ↓
Extract
   ↓
Parquet Staging
   ↓
Transform
   ↓
Validated Parquet
   ↓
Load
   ↓
PostgreSQL Data Warehouse
```

---

# Repository Structure

```text
datamart-pipeline/

├── dags/
│   └── pipeline_datamart.py

├── scripts/
│   ├── extract.py
│   ├── transform.py
│   └── load.py

├── data/
│   ├── raw/
│   │   ├── data.csv
│   │   └── online_retail_II.csv
│   │
│   └── processed/
│       ├── source1.parquet
│       ├── source2.parquet
│       ├── sales.parquet
│       ├── returns.parquet
│       ├── products.parquet
│       └── rejected.parquet

├── sql/
│   ├── init_dw.sql
│   └── validation_queries.sql

├── docker-compose.yml
├── README.md
├── DECISIONES.md
├── .env
└── .env.example
```

---

# Infrastructure

The platform runs using Docker Compose.

Services deployed:

| Service           | Purpose                                              |
| ----------------- | ---------------------------------------------------- |
| postgres-airflow  | Airflow metadata database                            |
| postgres-dw       | Analytical PostgreSQL repository                     |
| airflow-init      | Initializes Airflow users, variables and connections |
| airflow-webserver | Airflow UI                                           |
| airflow-scheduler | DAG orchestration                                    |

---

# Running the Project

## 1. Configure Environment Variables

Create the environment file:

```bash
cp .env.example .env
```

Populate:

```env
DW_USER=postgres
DW_PASSWORD=password
DW_DB=datamart
```

---

## 2. Start Infrastructure

```bash
docker-compose up -d
```

This command initializes:

* PostgreSQL (metadata)
* PostgreSQL (Data Warehouse)
* Airflow Scheduler
* Airflow Webserver
* Airflow Variables
* Airflow Connections

---

## 3. Access Airflow

```text
http://localhost:8080
```

Credentials:

```text
username: admin
password: admin
```

Verify:

Admin → Connections

Expected:

```text
dw_postgres
```

Verify:

Admin → Variables

Expected:

```text
DUPLICATE_PRIORITY_SOURCE
REJECT_LOG_TABLE
```

---

# Pipeline Flow

## Extract

Reads raw CSV datasets.

Sources:

* data.csv
* online_retail_II.csv

Output:

```text
source1.parquet
source2.parquet
```

---

## Transform

Applies:

* Schema standardization
* UTC conversion
* Customer normalization
* Product canonicalization
* Cross-source deduplication
* Sales/returns separation
* Revenue calculations
* Data quality validation

Output:

```text
sales.parquet
returns.parquet
products.parquet
rejected.parquet
```

---

## Load

Loads curated datasets into PostgreSQL.

Target tables:

* products
* sales
* returns
* rejected_records

Loading strategy:

* Delete by process_date
* UPSERT on conflicts

This guarantees idempotent execution.

---

# Data Quality Rules

Implemented validations:

* unit_price > 0
* invoice_date must be valid
* product_code cannot be empty
* missing customer IDs → UNKNOWN
* duplicate resolution between sources

Rejected records are stored in:

```text
rejected_records
```

---

# Analytical Validation

Business validation queries are available in:

```text
sql/validation_queries.sql
```

Examples:

* Monthly net revenue
* Product performance
* Return ratios
* Geographic analysis
* Customer segmentation
* Catalog verification

---

# Technologies

* Python
* Pandas
* Apache Airflow 2.9
* PostgreSQL 16
* Docker Compose
* SQLAlchemy
* Parquet

---

# Author

Technical Assessment — DataMart S.A.S.