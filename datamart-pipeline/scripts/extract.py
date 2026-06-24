"""
extract.py
----------
Responsable únicamente de LEER los archivos crudos y devolver
DataFrames de pandas. No aplica ninguna regla de negocio aquí:
la idea es mantener "leer datos" separado de "limpiar datos"
para que cada parte se pueda probar y entender por separado.
"""

import pandas as pd

RAW_PATH = "/opt/airflow/data/raw"


def extract_source1() -> pd.DataFrame:
    """
    Fuente 1: data.csv (Online Retail UK - Kaggle carrie1)
    Representa el volcado diario de órdenes del sistema operacional.
    """
    df = pd.read_csv(
        f"{RAW_PATH}/data.csv",
        encoding="ISO-8859-1",  # este dataset trae caracteres especiales
        dtype={"CustomerID": "string", "StockCode": "string"},
    )
    df["source_dataset"] = "data_csv"
    return df


def extract_source2() -> pd.DataFrame:
    """
    Fuente 2: online_retail_II.csv (thedevastator - Kaggle)
    Representa el historial histórico de 2 años adicionales.
    NOTA: las columnas no se llaman igual que en la fuente 1
    (ej. "Customer ID" con espacio en vez de "CustomerID").
    La unificación de nombres de columnas se hace en transform.py,
    no aquí, para que extract.py solo se preocupe de leer el archivo
    tal cual viene.
    """
    df = pd.read_csv(
        f"{RAW_PATH}/online_retail_II.csv",
        encoding="ISO-8859-1",
        dtype={"Customer ID": "string", "StockCode": "string"},
    )
    df["source_dataset"] = "online_retail_ii"
    return df