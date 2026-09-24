-- Analytical queries on data/pubmed.db  (sqlite3 data/pubmed.db < sql/analytics.sql)

-- 1. Papers per year with year-over-year change (CTE + window function LAG)
WITH yearly AS (
    SELECT year, COUNT(*) AS papers FROM papers WHERE year IS NOT NULL GROUP BY year
)
SELECT year, papers,
       papers - LAG(papers) OVER (ORDER BY year) AS yoy_change
FROM yearly ORDER BY year;

-- 2. Top journals with share of corpus (window SUM over all rows)
SELECT journal, COUNT(*) AS papers,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM papers GROUP BY journal ORDER BY papers DESC LIMIT 10;

-- 3. Most prolific authors (JOIN authors -> papers)
SELECT a.name, COUNT(DISTINCT a.pmid) AS papers, MIN(p.year) AS first_year, MAX(p.year) AS last_year
FROM authors a JOIN papers p ON p.pmid = a.pmid
GROUP BY a.name HAVING papers > 1 ORDER BY papers DESC LIMIT 10;

-- 4. Most cited-in-corpus study type per year: rank within each year (ROW_NUMBER)
SELECT year, study_type, n FROM (
    SELECT year, study_type, COUNT(*) AS n,
           ROW_NUMBER() OVER (PARTITION BY year ORDER BY COUNT(*) DESC) AS rn
    FROM papers WHERE year IS NOT NULL GROUP BY year, study_type
) WHERE rn = 1 ORDER BY year;

-- 5. Data-quality audit: rows missing key fields
SELECT SUM(doi IS NULL OR doi = '') AS no_doi,
       SUM(mesh_terms IS NULL OR mesh_terms = '') AS no_mesh,
       COUNT(*) AS total
FROM papers;
