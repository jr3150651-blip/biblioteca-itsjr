
import os
import json
import urllib.request
import urllib.error
from dotenv import load_dotenv
from pathlib import Path

RUTA_ENV = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=RUTA_ENV)

account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
api_token = os.getenv("CLOUDFLARE_API_TOKEN")

if not account_id or not api_token:
    raise ValueError("Faltan las credenciales de Cloudflare en .env")

url = (
    f"https://api.cloudflare.com/client/v4/accounts/"
    f"{account_id}/ai/run/@cf/baai/bge-m3"
)

datos = {
    "text": [
        "Libros de programación, inteligencia artificial y redes informáticas"
    ]
}

solicitud = urllib.request.Request(
    url,
    data=json.dumps(datos).encode("utf-8"),
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
        print("Error de Cloudflare:", resultado.get("errors"))
    else:
        datos_vector = resultado.get("result", {}).get("data", [])

        print("¡CONEXIÓN EXITOSA CON CLOUDFLARE!")

        if datos_vector:
            print("Dimensiones del vector:", len(datos_vector[0]))
        else:
            print("Respuesta recibida:", resultado.get("result", {}).keys())

except urllib.error.HTTPError as error:
    print("Error HTTP:", error.code)
    print(error.read().decode("utf-8"))

except Exception as error:
    print("Error:", str(error))
