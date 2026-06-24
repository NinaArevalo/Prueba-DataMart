import sys
from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.models import Variable
from airflow.providers.postgres.hooks.postgres import PostgresHook

sys.path.append("/opt/airflow/scripts")

import extract
import load
import pandas as pd
import transform

default_args = {
    "owner": "datamart",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
}


@dag(
    dag_id="pipeline_datamart",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["datamart", "etl"],
)
def pipeline_datamart():

    @task
    def extract_source1_task():
        df = extract.extract_source1()
        path = "/opt/airflow/data/processed/source1.parquet"
        df.to_parquet(path, index=False)
        return path

    @task
    def extract_source2_task():
        df = extract.extract_source2()
        path = "/opt/airflow/data/processed/source2.parquet"
        df.to_parquet(path, index=False)
        return path

    @task
    def transform_task(path1, path2):
        # 1. Leer los archivos temporales de extracción
        df1 = pd.read_parquet(path1)
        df2 = pd.read_parquet(path2)

        # 2. Pipeline de transformación estándar
        df1 = transform.standardize_columns(df1, "data_csv")
        df2 = transform.standardize_columns(df2, "online_retail_ii")

        combined = pd.concat([df1, df2], ignore_index=True)
        combined = transform.normalize_types(combined)
        combined = transform.handle_missing_customer(combined)
        canonical = transform.build_canonical_descriptions(combined)

        priority_source = Variable.get(
            "DUPLICATE_PRIORITY_SOURCE", default_var="online_retail_ii"
        )

        combined = transform.deduplicate_across_sources(
            combined, priority_source
        )

        sales, returns = transform.split_sales_and_returns(combined)
        sales, rejected = transform.validate_sales(sales)
        sales = transform.calculate_revenue(sales, returns)

        # 3. Definir rutas de almacenamiento para la carga
        paths = {
            "sales": "/opt/airflow/data/processed/sales.parquet",
            "returns": "/opt/airflow/data/processed/returns.parquet",
            "rejected": "/opt/airflow/data/processed/rejected.parquet",
            "products": "/opt/airflow/data/processed/products.parquet",
        }

        # 4. Persistir a disco de forma eficiente
        sales.to_parquet(paths["sales"], index=False)
        returns.to_parquet(paths["returns"], index=False)
        rejected.to_parquet(paths["rejected"], index=False)
        canonical.to_parquet(paths["products"], index=False)

        return paths

    @task
    def load_task(paths_dict, ds=None):  
        # Usa la conexión local configurada en la UI web de Airflow
        hook = PostgresHook(postgres_conn_id="dw_postgres")
        engine = hook.get_sqlalchemy_engine()

        sales = pd.read_parquet(paths_dict["sales"])
        returns = pd.read_parquet(paths_dict["returns"])
        products = pd.read_parquet(paths_dict["products"])

        # -----------------------------------------------------------------
        # ### PARCHE DE SEGURIDAD EXCLUSIVO PARA EVITAR NOT NULL VIOLATION
        # Convertimos a datetime para asegurar el formateo correcto de Pandas
        returns['invoice_date_utc'] = pd.to_datetime(returns['invoice_date_utc'], errors='coerce')
        
        # Rellenamos los NaT (nulos) con la fecha de ejecución (ds)
        returns['invoice_date_utc'] = returns['invoice_date_utc'].fillna(pd.to_datetime(ds))
        # -----------------------------------------------------------------

        # Ejecutar cargas locales pasando 'ds'
        load.load_products(products, engine)
        load.load_table(sales, "sales", engine, process_date=ds)
        load.load_table(returns, "returns", engine, process_date=ds)

    # --- Flujo de Dependencias Único del Pipeline ---
    s1 = extract_source1_task()
    s2 = extract_source2_task()

    transformed_paths = transform_task(path1=s1, path2=s2)

    load_task(paths_dict=transformed_paths)


pipeline_datamart()