-- =====================================================================
-- Consultas de validación — responden las preguntas de negocio
-- de la sección 7 del enunciado. Ejecutar contra postgres-dw
-- después de correr el pipeline al menos una vez.
-- =====================================================================

-- 1) Evolución mensual de ventas netas (descontando devoluciones)
SELECT
    DATE_TRUNC('month', invoice_date_utc) AS mes,
    SUM(net_revenue) AS ventas_netas
FROM sales
GROUP BY 1
ORDER BY 1;


-- 2) Revenue bruto por categoría y proporción de devoluciones
--    (requiere products.category poblada)
SELECT
    p.category,
    SUM(s.gross_revenue) AS revenue_bruto,
    COALESCE(SUM(r.return_value), 0) AS valor_devuelto,
    ROUND(
        COALESCE(SUM(r.return_value), 0) / NULLIF(SUM(s.gross_revenue), 0) * 100, 2
    ) AS pct_devolucion
FROM sales s
LEFT JOIN products p ON p.product_code = s.product_code
LEFT JOIN returns r ON r.product_code = s.product_code
GROUP BY p.category
ORDER BY revenue_bruto DESC;


-- 3a) Top 10 productos con mayor revenue neto
SELECT product_code, SUM(net_revenue) AS revenue_neto
FROM sales
GROUP BY product_code
ORDER BY revenue_neto DESC
LIMIT 10;

-- 3b) Top 10 productos con mayor tasa de devolución
--     (valor devuelto / valor bruto vendido)
SELECT
    s.product_code,
    SUM(s.gross_revenue) AS revenue_bruto,
    COALESCE(SUM(r.return_value), 0) AS valor_devuelto,
    ROUND(COALESCE(SUM(r.return_value), 0) / NULLIF(SUM(s.gross_revenue), 0), 4) AS tasa_devolucion
FROM sales s
LEFT JOIN returns r ON r.product_code = s.product_code
GROUP BY s.product_code
HAVING SUM(s.gross_revenue) > 0
ORDER BY tasa_devolucion DESC
LIMIT 10;


-- 4) Países con más transacciones y ticket promedio por país
SELECT
    country,
    COUNT(*) AS num_transacciones,
    ROUND(AVG(gross_revenue), 2) AS ticket_promedio
FROM sales
GROUP BY country
ORDER BY num_transacciones DESC;


-- 5) Comportamiento de compra: clientes identificados vs UNKNOWN
SELECT
    CASE WHEN customer_id = 'UNKNOWN' THEN 'sin_identificar' ELSE 'identificado' END AS segmento,
    COUNT(*) AS num_transacciones,
    ROUND(AVG(gross_revenue), 2) AS ticket_promedio,
    SUM(gross_revenue) AS revenue_total
FROM sales
GROUP BY 1;


-- 6) Productos sin descripción consistente y total de códigos únicos
--    ("sin descripción consistente" = aparecen con más de una
--     descripción distinta en los datos crudos antes de canonizar)
SELECT COUNT(DISTINCT product_code) AS total_codigos_unicos
FROM sales;

-- (Para detectar inconsistencias de descripción habría que comparar
--  contra la tabla intermedia previa a canonical_description; ver
--  build_canonical_descriptions() en transform.py — se puede exportar
--  a una tabla auxiliar `product_description_variants` si se requiere
--  evidencia explícita en el repositorio.)


-- 7) Recomendación a producto: ejemplo de query de apoyo
--    (categoría con peor relación revenue/devolución)
SELECT
    p.category,
    SUM(s.gross_revenue) AS revenue_bruto,
    COALESCE(SUM(r.return_value), 0) AS valor_devuelto,
    ROUND(COALESCE(SUM(r.return_value), 0) / NULLIF(SUM(s.gross_revenue), 0) * 100, 2) AS pct_devolucion
FROM sales s
LEFT JOIN products p ON p.product_code = s.product_code
LEFT JOIN returns r ON r.product_code = s.product_code
GROUP BY p.category
ORDER BY pct_devolucion DESC;