"""
load.py
-------
Carga los DataFrames ya limpios al Data Warehouse en Postgres.

IDEMPOTENCIA: antes de insertar los datos de una fecha de proceso
(process_date = fecha de ejecución del DAG), se borra cualquier
registro que ya exista para esa misma fecha y esa misma fuente.
Así, correr el DAG dos veces el mismo día con los mismos datos NO
duplica filas: la segunda corrida simplemente reemplaza a la primera.
Además, utiliza UPSERT a nivel de fila para garantizar la calidad de los
datos en caso de conflictos por restricciones de claves únicas.
"""

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert


def get_engine(conn_string: str):
    return create_engine(conn_string)


def _delete_existing(
    engine, table: str, process_date: str, source_dataset: str | None = None
):
    with engine.begin() as conn:
        if source_dataset:
            conn.execute(
                text(
                    f"DELETE FROM {table} WHERE process_date = :pd AND source_dataset = :sd"
                ),
                {"pd": process_date, "sd": source_dataset},
            )
        else:
            conn.execute(
                text(f"DELETE FROM {table} WHERE process_date = :pd"),
                {"pd": process_date},
            )


def insert_on_conflict_update_generic(table, conn, keys, data_iter):
    """
    Función de soporte para pandas.to_sql que ejecuta un UPSERT (ON CONFLICT DO UPDATE)
    en PostgreSQL dinámicamente según las restricciones de la tabla.
    """
    data = [dict(zip(keys, row)) for row in data_iter]
    if not data:
        return

    # Crear la sentencia INSERT base de PostgreSQL
    insert_stmt = insert(table.table).values(data)

    # Identificar la restricción de clave única compuesta de las tablas transaccionales
    conflict_keys = ['invoice_no', 'product_code', 'invoice_date_utc', 'source_dataset']

    # Definir las columnas a actualizar (todas las que no formen parte de la clave compuesta)
    update_dict = {
        c.name: insert_stmt.excluded[c.name]
        for c in table.table.columns
        if c.name not in conflict_keys
    }

    # Construir la estructura completa del UPSERT
    upsert_stmt = insert_stmt.on_conflict_do_update(
        index_elements=conflict_keys,
        set_=update_dict
    )

    result = conn.execute(upsert_stmt)
    return result.rowcount


def load_table(
    df: pd.DataFrame,
    table: str,
    engine,
    process_date: str,
    source_dataset: str | None = None,
):
    if df.empty:
        return

    df = df.copy()
    df["process_date"] = process_date

    # ---------------------------------------------------------------------
    # DEFENSA ANTE ERRORES DE ESQUEMA: Filtrar solo las columnas de la DB LOCAL
    # ---------------------------------------------------------------------
    db_columns_map = {
        "sales": [
            "invoice_no",
            "product_code",
            "quantity",
            "unit_price",
            "customer_id",
            "country",
            "source_dataset",
            "invoice_date_utc",
            "gross_revenue",
            "net_revenue",
            "process_date",
        ],
        "returns": [
            "invoice_no",
            "product_code",
            "unit_price",
            "customer_id",
            "country",
            "source_dataset",
            "invoice_date_utc",
            "quantity_returned",
            "return_value",
            "process_date",
        ],
    }

    if table in db_columns_map:
        valid_cols = [c for c in db_columns_map[table] if c in df.columns]
        df = df[valid_cols]

    # Remoción de duplicados internos dentro del mismo DataFrame antes de la inserción
    subset_cols = ["invoice_no", "product_code", "invoice_date_utc", "source_dataset"]
    df = df.drop_duplicates(subset=subset_cols, keep="last")

    # Ejecutar el borrado idempotente tradicional
    _delete_existing(engine, table, process_date, source_dataset)
    
    # Inserción con control de conflictos (UPSERT)
    df.to_sql(
        table,
        engine,
        if_exists="append",
        index=False,
        method=insert_on_conflict_update_generic,
        chunksize=1000,
    )


def load_products(df: pd.DataFrame, engine):
    """
    products usa UPSERT (no depende de process_date) porque el
    catálogo no es un dato "diario" sino el estado actual del producto.
    """
    if df.empty:
        return

    df = df.copy()
    staging_df = pd.DataFrame(
        {
            "product_code": df["product_code"],
            "canonical_name": df["canonical_description"],
            "category": df.get("category", "SIN_CATEGORIA"),
            "supplier_country": df.get("supplier_country", None),
            "is_active": df.get("is_active", True),
            "source": df.get("source", "derived_from_transactions"),
        }
    )

    staging_df = staging_df.drop_duplicates(subset=["product_code"])

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS tmp_products_staging;"))
        conn.execute(
            text(
                """
            CREATE TEMPORARY TABLE tmp_products_staging (
                product_code TEXT,
                canonical_name TEXT,
                category TEXT,
                supplier_country TEXT,
                is_active BOOLEAN,
                source TEXT
            );
        """
            )
        )

        staging_df.to_sql(
            "tmp_products_staging",
            conn,
            if_exists="append",
            index=False,
            chunksize=5000,
        )

        upsert_query = """
            INSERT INTO products (product_code, canonical_name, category, supplier_country, is_active, source)
            SELECT product_code, canonical_name, category, supplier_country, is_active, source 
            FROM tmp_products_staging
            ON CONFLICT (product_code) DO UPDATE SET
                canonical_name = EXCLUDED.canonical_name,
                category = EXCLUDED.category,
                supplier_country = EXCLUDED.supplier_country,
                is_active = EXCLUDED.is_active,
                source = EXCLUDED.source;
        """
        conn.execute(text(upsert_query))
        conn.execute(text("DROP TABLE IF EXISTS tmp_products_staging;"))