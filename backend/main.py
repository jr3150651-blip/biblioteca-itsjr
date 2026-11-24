
import os
import json
import urllib.request
import urllib.error

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from database import obtener_conexion


# ==========================================
# GENERAR EMBEDDINGS CON CLOUDFLARE BGE-M3
# ==========================================

def obtener_embedding_cloudflare(texto):
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    api_token = os.getenv("CLOUDFLARE_API_TOKEN")

    if not account_id or not api_token:
        raise HTTPException(
            status_code=500,
            detail="No se encontraron las credenciales de Cloudflare."
        )

    url = (
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{account_id}/ai/run/@cf/baai/bge-m3"
    )

    datos = json.dumps({"text": [texto]}).encode("utf-8")

    solicitud = urllib.request.Request(
        url,
        data=datos,
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(solicitud, timeout=60) as respuesta:
            resultado = json.loads(respuesta.read().decode("utf-8"))

        if not resultado.get("success"):
            raise HTTPException(
                status_code=502,
                detail="Cloudflare no pudo generar el embedding."
            )

        embedding = resultado["result"]["data"][0]

        if len(embedding) != 1024:
            raise HTTPException(
                status_code=502,
                detail="El embedding generado no tiene 1024 dimensiones."
            )

        return embedding

    except urllib.error.HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail=f"Error de Cloudflare: HTTP {error.code}"
        )
    except urllib.error.URLError:
        raise HTTPException(
            status_code=502,
            detail="No fue posible conectar con Cloudflare."
        )


# ==========================================
# CONFIGURACIÓN DE FASTAPI
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Biblioteca ITSJR",
    description="Sistema de búsqueda de recursos bibliográficos",
    version="1.0.0",
    lifespan=lifespan
)


# ==========================================
# RUTA PRINCIPAL
# ==========================================

@app.get("/")
def inicio():
    return {
        "mensaje": "¡Bienvenido al sistema de búsqueda de la Biblioteca ITSJR!"
    }


# ==========================================
# LISTAR LIBROS
# ==========================================

@app.get("/libros")
def listar_libros():
    conexion = obtener_conexion()

    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT id_libro, titulo, autor,
                       tema_general, unidades_disponibles
                FROM libros
                ORDER BY id_libro
                LIMIT 20;
            """)

            resultados = cursor.fetchall()

            libros = [
                {
                    "id": fila[0],
                    "titulo": fila[1],
                    "autor": fila[2],
                    "tema": fila[3],
                    "disponibles": fila[4]
                }
                for fila in resultados
            ]

            return {
                "total": len(libros),
                "libros": libros
            }

    finally:
        conexion.close()


# ==========================================
# BÚSQUEDA TRADICIONAL
# ==========================================

@app.get("/buscar")
def buscar_libros(q: str):
    consulta = q.strip()

    if not consulta:
        return {
            "consulta": q,
            "total": 0,
            "libros": []
        }

    conexion = obtener_conexion()

    try:
        with conexion.cursor() as cursor:
            busqueda = f"%{consulta}%"

            cursor.execute("""
                SELECT id_libro, titulo, autor,
                       tema_general, subtema,
                       editorial, anio_publicacion,
                       unidades_disponibles,
                       pasillo, estanteria, estante
                FROM libros
                WHERE titulo ILIKE %s
                   OR autor ILIKE %s
                   OR tema_general ILIKE %s
                   OR subtema ILIKE %s
                   OR palabras_clave ILIKE %s
                   OR editorial ILIKE %s
                ORDER BY id_libro
                LIMIT 50;
            """, (
                busqueda,
                busqueda,
                busqueda,
                busqueda,
                busqueda,
                busqueda
            ))

            resultados = cursor.fetchall()

            libros = [
                {
                    "id": fila[0],
                    "titulo": fila[1],
                    "autor": fila[2],
                    "tema": fila[3],
                    "subtema": fila[4],
                    "editorial": fila[5],
                    "anio": fila[6],
                    "disponibles": fila[7],
                    "pasillo": fila[8],
                    "estanteria": fila[9],
                    "estante": fila[10]
                }
                for fila in resultados
            ]

            return {
                "consulta": consulta,
                "total": len(libros),
                "libros": libros
            }

    finally:
        conexion.close()


# ==========================================
# BÚSQUEDA SEMÁNTICA CON BGE-M3
# ==========================================

@app.get("/buscar-semantico")
def buscar_semantico(q: str, limite: int = 10):
    consulta = q.strip()

    if not consulta:
        return {
            "consulta": q,
            "total": 0,
            "libros": []
        }

    if limite < 1 or limite > 50:
        raise HTTPException(
            status_code=400,
            detail="El límite debe estar entre 1 y 50."
        )

    # Generar embedding de la consulta con Cloudflare
    vector_consulta = obtener_embedding_cloudflare(consulta)

    vector_texto = (
        "[" + ",".join(str(float(valor)) for valor in vector_consulta) + "]"
    )

    conexion = obtener_conexion()

    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT
                    l.id_libro,
                    l.titulo,
                    l.autor,
                    l.tema_general,
                    l.subtema,
                    l.editorial,
                    l.anio_publicacion,
                    l.unidades_disponibles,
                    l.pasillo,
                    l.estanteria,
                    l.estante,
                    e.embedding <=> %s::vector AS distancia
                FROM libros_embeddings_bge e
                INNER JOIN libros l
                    ON l.id_libro = e.id_libro
                ORDER BY e.embedding <=> %s::vector
                LIMIT %s;
            """, (
                vector_texto,
                vector_texto,
                limite
            ))

            resultados = cursor.fetchall()

            libros = [
                {
                    "id": fila[0],
                    "titulo": fila[1],
                    "autor": fila[2],
                    "tema": fila[3],
                    "subtema": fila[4],
                    "editorial": fila[5],
                    "anio": fila[6],
                    "disponibles": fila[7],
                    "pasillo": fila[8],
                    "estanteria": fila[9],
                    "estante": fila[10],
                    "similitud": round(1 - float(fila[11]), 4)
                }
                for fila in resultados
            ]

            return {
                "consulta": consulta,
                "total": len(libros),
                "libros": libros
            }

    finally:
        conexion.close()


# ==========================================
# SERVIR INTERFAZ WEB
# ==========================================

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app.mount(
    "/interfaz",
    StaticFiles(directory=str(FRONTEND_DIR), html=True),
    name="frontend"
)
