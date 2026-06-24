# DataMart S.A.S. — Pipeline ETL con Apache Airflow

Pipeline que extrae datos de ventas (Kaggle), los limpia/transforma aplicando
reglas de negocio, y los carga en un Data Warehouse en PostgreSQL, todo
orquestado por Apache Airflow corriendo en Docker.

## 1. Requisitos previos

- Docker Desktop instalado y corriendo (incluye Docker Compose).
- Git.
- (Opcional, para inspeccionar el DW) DBeaver o pgAdmin.

## 2. Descargar los datos (paso manual, una sola vez)

Como las fuentes son privadas de Kaggle, descárgalas manualmente y ponlas
en `data/raw/`:

1. https://www.kaggle.com/datasets/carrie1/ecommerce-data → descarga `data.csv`
2. https://www.kaggle.com/datasets/thedevastator/online-retail-transaction-dataset → descarga `online_retail_II.csv`

Resultado esperado:
```
data/raw/data.csv
data/raw/online_retail_II.csv
```

## 3. Configurar variables de entorno

```powershell
copy .env.example .env
```
Abre `.env` y cambia `DW_PASSWORD` por una contraseña propia (no es necesario
para que funcione en local, pero es buena práctica).

## 4. Levantar el entorno

```powershell
docker-compose up -d
```

Esto descarga las imágenes (la primera vez tarda unos minutos), y deja
corriendo automáticamente:
- Airflow webserver en http://localhost:8080 (usuario: `admin`, contraseña: `admin`)
- Airflow scheduler
- Postgres de metadatos de Airflow (uso interno, no lo necesitas tocar)
- Postgres del Data Warehouse en el puerto `5433`, con las tablas ya creadas

Espera ~2 minutos la primera vez (el contenedor `airflow-init` necesita
terminar de instalar dependencias y configurar todo antes de que el
webserver quede disponible).

## 5. Verificar que todo quedó bien configurado

1. Entra a http://localhost:8080 con `admin` / `admin`.
2. Ve a **Admin → Connections** y confirma que existe `dw_postgres`
   apuntando a `postgres-dw`.
3. Ve a **Admin → Variables** y confirma que existen `REJECT_LOG_TABLE`
   y `DUPLICATE_PRIORITY_SOURCE`.
4. Ve a **DAGs**, activa (toggle) el DAG `pipeline_datamart`, y dispáralo
   manualmente con el botón ▶ (Trigger DAG) para no esperar al schedule diario.

## 6. Verificar que los datos llegaron al Data Warehouse

Conéctate con DBeaver/pgAdmin a:
- Host: `localhost`
- Puerto: `5433`
- Usuario/Contraseña/DB: los que pusiste en `.env`

O desde la terminal:
```powershell
docker exec -it postgres-dw psql -U datamart_user -d datamart_dw -c "SELECT COUNT(*) FROM sales;"
```

## 7. Apagar el entorno

```powershell
docker-compose down
```
Para borrar también los datos (reinicio completo desde cero):
```powershell
docker-compose down -v
```

## 8. Estructura del repositorio

```
docker-compose.yml     -> define todos los servicios
.env.example            -> variables de entorno necesarias (sin secretos reales)
dags/                   -> DAG de Airflow (orquestación)
scripts/                -> lógica de extracción, transformación y carga
sql/init_dw.sql         -> creación de tablas del Data Warehouse
data/raw/                -> CSV de entrada (no se sube a Git, ver .gitignore)
DECISIONES.md            -> documento de decisiones técnicas y casos ambiguos
```

Ver `DECISIONES.md` para el detalle de cómo se modeló el repositorio
analítico y cómo se resolvió cada caso ambiguo del enunciado.