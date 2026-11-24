import os
import psycopg
from pathlib import Path
from dotenv import load_dotenv

# Cargar el .env ubicado en la carpeta raíz del proyecto
RUTA_ENV = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=RUTA_ENV)


def obtener_conexion():
    return psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        sslmode=os.getenv("DB_SSLMODE", "require")
    )