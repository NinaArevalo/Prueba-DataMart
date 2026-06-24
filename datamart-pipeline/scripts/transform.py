"""
transform.py
------------
Aquí viven TODAS las reglas de negocio (sección 5 del enunciado) y las
decisiones tomadas para los casos ambiguos. Cada decisión está
comentada explicando el "por qué", tal como pide la sección 8
(documento de decisiones técnicas) -- este archivo es, en buena
parte, esa documentación hecha código.
"""

from datetime import datetime
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------
# PASO 1: Unificar nombres de columnas entre las dos fuentes
# ---------------------------------------------------------------------
# DECISIÓN: las dos fuentes Kaggle traen columnas equivalentes pero con
# nombres distintos (CustomerID vs "Customer ID", InvoiceNo vs Invoice,
# etc). Se unifican a un esquema común ANTES de aplicar cualquier regla,
# así el resto del pipeline no necesita saber de qué fuente vino el dato.
COLUMN_MAP_SOURCE1 = {
    "InvoiceNo": "invoice_no",
    "StockCode": "product_code",
    "Description": "description",
    "Quantity": "quantity",
    "InvoiceDate": "invoice_date",
    "UnitPrice": "unit_price",
    "CustomerID": "customer_id",
    "Country": "country",
}

COLUMN_MAP_SOURCE2 = {
    "Invoice": "invoice_no",
    "StockCode": "product_code",
    "Description": "description",
    "Quantity": "quantity",
    "InvoiceDate": "invoice_date",
    "Price": "unit_price",
    "Customer ID": "customer_id",
    "Country": "country",
}


def standardize_columns(df: pd.DataFrame, source: str) -> pd.DataFrame:
    mapping = (
        COLUMN_MAP_SOURCE1 if source == "data_csv" else COLUMN_MAP_SOURCE2
    )
    df = df.rename(columns=mapping)
    keep = list(mapping.values()) + ["source_dataset"]
    return df[[c for c in keep if c in df.columns]]


# ---------------------------------------------------------------------
# PASO 2: Normalizar tipos y formatos
# ---------------------------------------------------------------------
def normalize_types(df: pd.DataFrame) -> pd.DataFrame:
    # Regla de negocio (sección 5): fechas estandarizadas a UTC.
    # Ambos datasets son de Reino Unido (hora local UK); se asume
    # Europe/London y se convierte a UTC. DECISIÓN: si la conversión
    # de timezone falla por algún valor corrupto, se deja NaT y el
    # registro será rechazado más adelante (no se inventa una fecha).
    df["invoice_date"] = pd.to_datetime(
        df["invoice_date"].astype(str).str.strip(),
        errors="coerce",
        dayfirst=True,
    )
    df["invoice_date_utc"] = (
        df["invoice_date"]
        .dt.tz_localize("Europe/London", ambiguous="NaT", nonexistent="NaT")
        .dt.tz_convert("UTC")
        .dt.tz_localize(None)  # Quitamos el offset para compatibilidad con Parquet/DB
    )

    # Regla de negocio: códigos de producto en mayúsculas, sin espacios.
    df["product_code"] = (
        df["product_code"].astype("string").str.strip().str.upper()
    )

    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")

    return df


# ---------------------------------------------------------------------
# PASO 3: Decisión ambigua -> Customer ID faltante
# ---------------------------------------------------------------------
# DECISIÓN: en vez de excluir las transacciones sin customer_id (lo
# que perdería revenue real del análisis), se marcan con el valor
# 'UNKNOWN'. Así quedan identificables para responder la pregunta de
# negocio "¿hay diferencia de comportamiento entre clientes
# identificados y no identificados?" sin perder ninguna venta del
# cálculo de revenue total.
def handle_missing_customer(df: pd.DataFrame) -> pd.DataFrame:
    df["customer_id"] = df["customer_id"].fillna("UNKNOWN").astype("string")
    df.loc[df["customer_id"].str.strip() == "", "customer_id"] = "UNKNOWN"
    return df


# ---------------------------------------------------------------------
# PASO 4: Decisión ambigua -> nombre canónico del producto
# ---------------------------------------------------------------------
# DECISIÓN: por cada product_code, el "nombre canónico" es la
# descripción que aparece con más frecuencia (la moda) entre todas
# las variantes de mayúsculas/minúsculas. Es un criterio simple,
# reproducible y defendible: "lo que más se repite es lo más confiable".
def build_canonical_descriptions(df: pd.DataFrame) -> pd.DataFrame:
    desc = df.dropna(subset=["description", "product_code"]).copy()
    desc["description"] = desc["description"].str.strip().str.upper()

    # Optimizamos agrupando primero para reducir la carga computacional de la moda
    canonical = (
        desc.groupby("product_code")["description"]
        .agg(lambda x: x.mode().iloc[0] if not x.mode().empty else x.iloc[0])
        .reset_index()
        .rename(columns={"description": "canonical_description"})
    )
    return canonical


# ---------------------------------------------------------------------
# PASO 5: Separar ventas de devoluciones/ajustes
# ---------------------------------------------------------------------
# Regla de negocio explícita (sección 5): quantity <= 0 es devolución
# o ajuste, NUNCA una venta.
def split_sales_and_returns(df: pd.DataFrame):
    sales = df[df["quantity"] > 0].copy()
    returns = df[df["quantity"] <= 0].copy()
    returns["quantity_returned"] = returns["quantity"].abs()
    return sales, returns


# ---------------------------------------------------------------------
# PASO 6: Validaciones -> registros rechazados con motivo
# ---------------------------------------------------------------------
# OPTIMIZACIÓN DE RENDIMIENTO: Se elimina el bucle iterrows(). En su lugar,
# se utiliza procesamiento vectorial con np.select para clasificar los rechazos,
# bajando el tiempo de cómputo drásticamente en pruebas de estrés.
def validate_sales(df: pd.DataFrame):
    # Forzamos a que las series sean estrictamente arreglos booleanos de NumPy
    cond_bad_price = (df["unit_price"] <= 0).fillna(False).astype(bool)
    cond_bad_date = df["invoice_date_utc"].isna().astype(bool)
    cond_bad_code = (
        (df["product_code"].isna() | (df["product_code"].str.len() == 0))
        .fillna(False)
        .astype(bool)
    )

    # Identificar filas inválidas usando máscaras booleanas puras
    invalid_mask = cond_bad_price | cond_bad_date | cond_bad_code

    # Separar válidos de inválidos
    valid = df[~invalid_mask].copy()
    rejected = df[invalid_mask].copy()

    if not rejected.empty:
        # Ahora condlist contiene solo estructuras booleanas nativas
        conditions = [
            cond_bad_price[invalid_mask],
            cond_bad_date[invalid_mask],
            cond_bad_code[invalid_mask],
        ]
        choices = [
            "unit_price <= 0 en venta",
            "fecha invalida o no convertible a UTC",
            "product_code vacio",
        ]
        rejected["reason"] = np.select(
            conditions, choices, default="error desconocido"
        )
    else:
        # Estructura vacía consistente con la salida esperada si todo está perfecto
        rejected["reason"] = pd.Series(dtype="string")

    return valid, rejected


# ---------------------------------------------------------------------
# PASO 7: Cálculo de revenue bruto y neto
# ---------------------------------------------------------------------
def calculate_revenue(
    sales: pd.DataFrame, returns: pd.DataFrame
) -> pd.DataFrame:
    sales["gross_revenue"] = sales["quantity"] * sales["unit_price"]

    # Usamos .dt.floor("D") en lugar de .dt.date para conservar el tipo datetime
    # y evitar problemas de rendimiento y tipos en el motor de persistencia.
    sales["process_day"] = sales["invoice_date_utc"].dt.floor("D")

    returns = returns.copy()
    returns["return_value"] = returns["quantity_returned"] * returns[
        "unit_price"
    ].fillna(0)
    returns["process_day"] = returns["invoice_date_utc"].dt.floor("D")

    returns_by_day_product = (
        returns.groupby(["product_code", "process_day"])["return_value"]
        .sum()
        .reset_index()
        .rename(columns={"return_value": "daily_return_value"})
    )

    sales = sales.merge(
        returns_by_day_product, on=["product_code", "process_day"], how="left"
    )
    sales["daily_return_value"] = sales["daily_return_value"].fillna(0)
    sales["net_revenue"] = sales["gross_revenue"] - sales["daily_return_value"]
    sales = sales.drop(columns=["daily_return_value"])
    return sales


# ---------------------------------------------------------------------
# PASO 8: Decisión ambigua -> duplicados entre las dos fuentes Kaggle
# ---------------------------------------------------------------------
# DECISIÓN: se usa una clave compuesta (invoice_no + product_code +
# invoice_date_utc) para detectar el duplicado real entre fuentes
# (no basta con InvoiceNo porque se numeran independientemente en cada
# dataset). Cuando hay choque, se prioriza 'online_retail_ii' porque
# es la versión más reciente/curada publicada por el mismo proveedor
# de datos, asumida como la de mejor calidad. Esta prioridad se
# controla por una Airflow Variable (DUPLICATE_PRIORITY_SOURCE) para
# poder cambiarla sin tocar código.
def deduplicate_across_sources(
    df: pd.DataFrame, priority_source: str
) -> pd.DataFrame:
    # Aseguramos que la columna no tenga nulos que rompan el key lambda
    df["source_dataset"] = df["source_dataset"].fillna("UNKNOWN").astype(str)

    df = df.sort_values(
        by="source_dataset", key=lambda s: (s != priority_source)
    )  # prioridad primero
    return df.drop_duplicates(
        subset=["invoice_no", "product_code", "invoice_date_utc"], keep="first"
    )