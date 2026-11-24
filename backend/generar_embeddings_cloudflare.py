

import os
import json
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

# Cargar el .env de la carpeta principal
RUTA_ENV = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(RUTA_ENV)

from database import obtener_conexion

ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")

URL = (
    f"https://api.cloudflare.com/client/v4/accounts/"
    f"{ACCOUNT_ID}/ai/run/@cf/baai/bge-m3"
)

def crear_contenido(fila):
    titulo, autor, tema, subtema, palabras, editorial, anio = fila

    return (
        f"Título: {titulo or ''}. "
        f"Autor: {autor or ''}. "
        f"Tema: {tema or ''}. "
        f"Subtema: {subtema or ''}. "
        f"Palabras clave: {palabras or ''}. "
        f"Editorial: {editorial or ''}. "
        f"Año: {anio or ''}."
    )

def obtener_embeddings(textos):
    datos = {"text": textos}

    solicitud = urllib.request.Request(
        URL,
        data=json.dumps(datos).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {API_TOKEN}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    with urllib.request.urlopen(solicitud, timeout=180) as respuesta:
        resultado = json.loads(respuesta.read().decode("utf-8"))

    if not resultado.get("success"):
        raise RuntimeError(str(resultado.get("errors")))

    vectores = resultado["result"]["data"]

    if len(vectores) != len(textos):
        raise RuntimeError("La cantidad de vectores no coincide.")

    for vector in vectores:
        if len(vector) != 1024:
            raise RuntimeError("El vector no tiene 1024 dimensiones.")

    return vectores


def main():
    if not ACCOUNT_ID or not API_TOKEN:
        raise ValueError("No se encontraron las credenciales de Cloudflare.")

    conexion = obtener_conexion()
    total_generados = 0
    tamano_lote = 10

    try:
        while True:
            with conexion.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        l.id_libro,
                        l.titulo,
                        l.autor,
                        l.tema_general,
                        l.subtema,
                        l.palabras_clave,
                        l.editorial,
                        l.anio_publicacion
                    FROM libros l
                    LEFT JOIN libros_embeddings_bge e
                        ON l.id_libro = e.id_libro
                    WHERE e.id_libro IS NULL
                    ORDER BY l.id_libro
                    LIMIT %s;
                """, (tamano_lote,))

                libros = cursor.fetchall()

            if not libros:
                break

            print(f"Procesando lote de {len(libros)} libros...")

            textos = [crear_contenido(fila[1:]) for fila in libros]
            vectores = obtener_embeddings(textos)

            with conexion.cursor() as cursor:
                for libro, contenido, vector in zip(libros, textos, vectores):
                    vector_texto = "[" + ",".join(
                        str(float(valor)) for valor in vector
                    ) + "]"

                    cursor.execute("""
                        INSERT INTO libros_embeddings_bge
                            (id_libro, contenido, embedding)
                        VALUES (%s, %s, %s::vector)
                        ON CONFLICT (id_libro)
                        DO UPDATE SET
                            contenido = EXCLUDED.contenido,
                            embedding = EXCLUDED.embedding;
                    """, (libro[0], contenido, vector_texto))

            conexion.commit()
            total_generados += len(vectores)

            print(f"Lote guardado. Nuevos registros: {total_generados}")

        print("\n¡PROCESO TERMINADO!")
        print("Embeddings nuevos generados:", total_generados)

    except Exception:
        conexion.rollback()
        raise

    finally:
        conexion.close()

if __name__ == "__main__":
    main()
