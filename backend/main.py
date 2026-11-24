
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from database import obtener_conexion
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from sentence_transformers import SentenceTransformer

modelo_semantico = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global modelo_semantico

    modelo_semantico = SentenceTransformer(
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )

    yield

    modelo_semantico = None


app = FastAPI(
    title="Biblioteca ITSJR",
    description="Sistema de búsqueda de recursos bibliográficos",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
def inicio():
    return {
        "mensaje": "¡Bienvenido al sistema de búsqueda de la Biblioteca ITSJR!"
    }


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

            return {"total": len(libros), "libros": libros}

    finally:
        conexion.close()


@app.get("/buscar")
def buscar_libros(q: str):
    consulta = q.strip()

    if not consulta:
        return {"consulta": q, "total": 0, "libros": []}

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
                busqueda, busqueda, busqueda,
                busqueda, busqueda, busqueda
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


@app.get("/buscar-semantico")
def buscar_semantico(q: str, limite: int = 10):

    consulta = q.strip()

    if not consulta:
        return {"consulta": q, "total": 0, "libros": []}

    if limite < 1 or limite > 50:
        raise HTTPException(
            status_code=400,
            detail="El límite debe estar entre 1 y 50."
        )

    if modelo_semantico is None:
        raise HTTPException(
            status_code=503,
            detail="El modelo semántico todavía no está disponible."
        )

    vector_consulta = modelo_semantico.encode(
        consulta,
        normalize_embeddings=True
    )

    vector_texto = "[" + ",".join(
        str(float(valor)) for valor in vector_consulta
    ) + "]"

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
                FROM libros_embeddings e
                INNER JOIN libros l
                    ON l.id_libro = e.id_libro
                ORDER BY e.embedding <=> %s::vector
                LIMIT %s;
            """, (vector_texto, vector_texto, limite))

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


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app.mount(
    "/interfaz",
    StaticFiles(directory=str(FRONTEND_DIR), html=True),
    name="frontend"
)
