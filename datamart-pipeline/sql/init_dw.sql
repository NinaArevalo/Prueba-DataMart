-- =====================================================================
-- Modelo del repositorio analítico (Data Warehouse) de DataMart
-- =====================================================================
-- DECISIÓN DE DISEÑO: se separan ventas y devoluciones en dos tablas
-- distintas (sales / returns) en lugar de una sola tabla con una
-- columna "tipo". Esto hace trivial calcular "venta neta" (sección 7)
-- con un simple JOIN/resta, evita errores de filtrado y refleja
-- directamente la regla de negocio de la sección 5: "deben separarse
-- de forma que sea posible calcular el neto".
--
-- DECISIÓN DE DISEÑO: products es una tabla de catálogo independiente
-- (viene de la API opcional o de un fallback estático/derivado de los
-- propios datos). sales y returns referencian product_code, no un FK
-- estricto, porque en datos reales de Kaggle aparecerán códigos sin
-- catálogo y no queremos que la carga falle por eso.
-- =====================================================================

CREATE TABLE IF NOT EXISTS products (
    product_code      VARCHAR(50) PRIMARY KEY,   -- normalizado: mayúsculas, sin espacios
    canonical_name     VARCHAR(255),
    category            VARCHAR(100),
    supplier_country    VARCHAR(100),
    is_active            BOOLEAN DEFAULT TRUE,
    source               VARCHAR(50)               -- 'api' | 'static_fallback' | 'derived_from_transactions'
);

CREATE TABLE IF NOT EXISTS sales (
    sale_id            BIGSERIAL PRIMARY KEY,
    invoice_no          VARCHAR(50)   NOT NULL,
    product_code        VARCHAR(50)   NOT NULL,
    quantity              INTEGER       NOT NULL CHECK (quantity > 0),
    unit_price            NUMERIC(12,2) NOT NULL CHECK (unit_price > 0),
    gross_revenue        NUMERIC(14,2) NOT NULL,     -- quantity * unit_price
    net_revenue           NUMERIC(14,2),               -- gross_revenue ajustado por devoluciones del mismo código/periodo
    invoice_date_utc     TIMESTAMP     NOT NULL,
    country               VARCHAR(100),
    customer_id           VARCHAR(50),                 -- 'UNKNOWN' si no venía en la fuente
    source_dataset        VARCHAR(50),                 -- 'data_csv' | 'online_retail_ii'
    process_date          DATE          NOT NULL,       -- fecha de ejecución del DAG (para idempotencia)
    UNIQUE (invoice_no, product_code, invoice_date_utc, source_dataset)
);

CREATE TABLE IF NOT EXISTS returns (
    return_id          BIGSERIAL PRIMARY KEY,
    invoice_no           VARCHAR(50)   NOT NULL,
    product_code         VARCHAR(50)   NOT NULL,
    quantity_returned     INTEGER       NOT NULL CHECK (quantity_returned > 0), -- valor absoluto
    unit_price             NUMERIC(12,2),
    return_value           NUMERIC(14,2),
    invoice_date_utc      TIMESTAMP     NOT NULL,
    country                VARCHAR(100),
    customer_id            VARCHAR(50),
    source_dataset         VARCHAR(50),
    process_date           DATE          NOT NULL,
    UNIQUE (invoice_no, product_code, invoice_date_utc, source_dataset)
);

-- Log de registros rechazados durante la transformación.
-- Guarda el payload crudo como JSON para poder auditar/depurar sin
-- tener que volver al CSV original.
CREATE TABLE IF NOT EXISTS rejected_records (
    rejected_id        BIGSERIAL PRIMARY KEY,
    source_dataset       VARCHAR(50),
    reason                 TEXT NOT NULL,
    raw_payload            JSONB,
    rejected_at             TIMESTAMP DEFAULT NOW(),
    process_date            DATE NOT NULL
);

-- Índices pensados directamente para las preguntas de negocio
-- (evolución mensual, top productos, comparación por país).
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales (invoice_date_utc);
CREATE INDEX IF NOT EXISTS idx_sales_product ON sales (product_code);
CREATE INDEX IF NOT EXISTS idx_sales_country ON sales (country);
CREATE INDEX IF NOT EXISTS idx_returns_product ON returns (product_code);
CREATE INDEX IF NOT EXISTS idx_returns_date ON returns (invoice_date_utc);