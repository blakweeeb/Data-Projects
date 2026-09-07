-- Base de metadata de Airflow (compartida con el Hive Metastore en este demo).
-- En un entorno productivo irian en instancias/servicios separados.
CREATE DATABASE airflow;

-- Rol que usa Airflow (AIRFLOW__DATABASE__SQL_ALCHEMY_CONN = airflow:airflow).
-- Sin esto, `airflow db migrate` falla con "password authentication failed".
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'airflow') THEN
    CREATE ROLE airflow LOGIN PASSWORD 'airflow';
  END IF;
END $$;
GRANT ALL PRIVILEGES ON DATABASE airflow TO airflow;
-- La DB la crea el superusuario hive: hay que ceder propiedad y uso del schema.
ALTER DATABASE airflow OWNER TO airflow;
GRANT ALL ON SCHEMA public TO airflow;
