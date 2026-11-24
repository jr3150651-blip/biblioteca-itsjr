
from sentence_transformers import SentenceTransformer
from database import obtener_conexion

# Cargar el modelo multilingüe
print("Cargando modelo de IA...")
modelo = SentenceTransformer(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

# Conectar con PostgreSQL
conexion = obtener_conexion()

try:
    with conexion.cursor() as cursor:

        # Obtener los datos de los libros
        cursor.execute("""
            SELECT id_libro, titulo, autor, tema_general,
                   subtema, palabras_clave, editorial,
                   anio_publicacion
            FROM libros
            ORDER BY id_libro;
        """)

        libros = cursor.fetchall()

    print(f"Libros encontrados: {len(libros)}")

    # Construir una descripción de cada libro
    ids = []
    contenidos = []

    for libro in libros:
        id_libro, titulo, autor, tema, subtema, palabras, editorial, anio = libro

        contenido = (
            f"Titulo: {titulo or ''}. "
            f"Autor: {autor or ''}. "
            f"Tema: {tema or ''}. "
            f"Subtema: {subtema or ''}. "
            f"Palabras clave: {palabras or ''}. "
            f"Editorial: {editorial or ''}. "
            f"Año: {anio or ''}."
        )

        ids.append(id_libro)
        contenidos.append(contenido)

    # Generar los vectores
    print("Generando embeddings...")
    vectores = modelo.encode(
        contenidos,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True
    )

    # Guardar los vectores en PostgreSQL
    print("Guardando embeddings en PostgreSQL...")

    with conexion.cursor() as cursor:
        for id_libro, contenido, vector in zip(ids, contenidos, vectores):

            vector_texto = "[" + ",".join(
                str(float(valor)) for valor in vector
            ) + "]"

            cursor.execute("""
                INSERT INTO libros_embeddings
                    (id_libro, contenido, embedding)
                VALUES (%s, %s, %s::vector)
                ON CONFLICT (id_libro)
                DO UPDATE SET
                    contenido = EXCLUDED.contenido,
                    embedding = EXCLUDED.embedding;
            """, (id_libro, contenido, vector_texto))

    conexion.commit()

    print("¡Proceso terminado correctamente!")
    print(f"Embeddings generados: {len(vectores)}")

finally:
    conexion.close()
