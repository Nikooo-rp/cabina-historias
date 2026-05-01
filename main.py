# main.py
import json
from dotenv import load_dotenv

from fastapi import FastAPI, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import requests, tempfile, os
from datetime import datetime
from openai import OpenAI

load_dotenv()

app = FastAPI()

# Esto permite que el HTML pueda hablar con el servidor
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API key de Lemonfox
LEMONFOX_API_KEY = os.getenv("API_KEY")

client = OpenAI(
    api_key=LEMONFOX_API_KEY,
    base_url="https://api.lemonfox.ai/v1",
)

ARCHIVO_HISTORIAS = "historias.jsonl"

with open("instrucciones.txt", "r", encoding="utf-8") as f:
    instructions = f.read()

# Para la transcripción.
TR_PROMPT = """
Audio grabado en Santa Fe de Antioquia, Colombia. Narración oral espontánea
en español colombiano antioqueño. El hablante está contando una historia,
leyenda, memoria personal o anécdota del municipio.

LUGARES Y ZONAS:
Parque Principal, Plaza Principal, Catedral de Santa Bárbara, Iglesia de Chiquinquirá,
Iglesia de La Inmaculada, Capilla de Santa Lucía, Puente de Occidente,
El Malecón, Cerro de la Cruz, Calle de las Flores, Calle del Codo,
El Caño, La Ciénaga, Quebrada Doña María, Vereda El Pescado,
Vereda Tonusco, Barrio La Estación, El Cementerio Viejo,
La Cárcel Vieja, La Alcaldía, El Palacio Municipal, La Normal,
Colegio Fray Cristóbal de Torres.

NOMBRES PROPIOS FRECUENTES:
Braulio, Epifanio, Custodio, Transito, Filomena, Presentación,
Encarnación, Consuelo, Libardo, Argemiro, Tulio, Froilán,
Evangelina, Bertilda, Clímaco, Deogracias, Leocadio.
Apellidos: Santamaría, Uribe, Giraldo, Restrepo, Vélez,
Gaviria, Jaramillo, Montoya, Posada, Ochoa.

VOCABULARIO LOCAL Y ANTIOQUEÑO:
parce, pues, ome, sumercé, el man, hágale, ahorita, hace años, parcerito, nea, neita
dizque, vea pues, no joda, qué cosa, de aquí del pueblo, man, quizque, jueputa,
los del pueblo, los viejos, los ancestros, los abuelos, usté, ubica, cacorro, lucas, luca
misia, don, doña, el finado, la finada, en paz descanse, arrinconar, putería, llanta, 
que Dios lo tenga, eso sí era, antes de la carretera, malparido, hijueputa
cuando no había luz, en tiempos de la violencia,
subir al cerro, bajar al río, cruzar el puente,
la procesión, la novena, el novenario, la Semana Santa,
el Corpus Christi, las fiestas del municipio, el Festival del Porro.

TÉRMINOS COLONIALES E HISTÓRICOS:
la Colonia, la Independencia, los españoles, los indígenas,
los catíos, los nutabes, los zenúes, la encomienda,
el cabildo, la gobernación, la provincia, el camino real,
la arriería, las mulas, el oro, la minería, el mazamorreo,
la Iglesia Católica, los franciscanos, los jesuitas,
el Padre, el Cura, Monseñor, la misa del gallo.

LEYENDAS Y PERSONAJES MÍTICOS FRECUENTES:
la Llorona, el Mohán, la Madremonte, el Patetarro,
la Patasola, el Hojarasquín del Monte, las ánimas,
el diablo, el Maligno, las brujas, el mal de ojo,
el espanto, el difunto, el fantasma, la aparición,
el duende, el encanto, el tesoro escondido."""

def guardar_historia(texto: str, numero: int):
    historia = {
        "id": numero,
        "fecha": datetime.now().strftime("%Y-%m-%d"),
        "hora": datetime.now().strftime("%H:%M:%S"),
        "texto": texto
    }
    with open(ARCHIVO_HISTORIAS, "a", encoding="utf-8") as f:
        f.write(json.dumps(historia, ensure_ascii=False) + "\n")

def contar_historias() -> int:
    if not os.path.exists(ARCHIVO_HISTORIAS):
        return 0
    with open(ARCHIVO_HISTORIAS, "r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())

if not LEMONFOX_API_KEY:
    raise ValueError("No se ha establecido la variable de entorno API_KEY para Lemonfox")

@app.get("/")
def raiz():
    return {"mensaje": "Servidor funcionando"}

@app.post("/transcribir")
async def transcribir(audio: UploadFile = File(...)):
    # Guarda el audio en un archivo temporal
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name

    try:
        # Envía el audio a Lemonfox
        with open(tmp_path, "rb") as f:
            respuesta = requests.post(
                "https://api.lemonfox.ai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {LEMONFOX_API_KEY}"},
                data={
                    "language": "spanish",
                    "prompt": TR_PROMPT,
                    "response_format": "json",
                },
                files={"file": f},
            )

        respuesta.raise_for_status()
        texto = respuesta.json()["text"]

        # Guarda la historia
        numero = contar_historias() + 1
        guardar_historia(texto, numero)

        return {"texto": texto, "numero": numero}

    except Exception as e:
        return {"error": str(e)}

    finally:
        os.unlink(tmp_path)  # borra el archivo temporal
# Endpoint para ver las historias guardadas
@app.get("/historias")
def ver_historias():
    if not os.path.exists(ARCHIVO_HISTORIAS):
        return {"historias": [], "total": 0}

    historias = []
    with open(ARCHIVO_HISTORIAS, "r", encoding="utf-8") as f:
        for linea in f:
            if linea.strip():
                historias.append(json.loads(linea))

    return {"historias": historias, "total": len(historias)}

@app.post("/ubicar")
async def ubicar(request: Request):
    datos = await request.json()

    if not os.path.exists(ARCHIVO_HISTORIAS):
        return {"error": "No hay historias guardadas"}

    historias = []
    with open(ARCHIVO_HISTORIAS, "r", encoding="utf-8") as f:
        for linea in f:
            if linea.strip():
                historias.append(json.loads(linea))

    encontrada = False
    for historia in historias:
        if historia["id"] == datos["id"]:
            historia["lat"] = datos["lat"]
            historia["lng"] = datos["lng"]
            encontrada = True
            break

    if not encontrada:
        return {"error": f"No se encontró la historia con id {datos['id']}"}

    with open(ARCHIVO_HISTORIAS, "w", encoding="utf-8") as f:
        for historia in historias:
            f.write(json.dumps(historia, ensure_ascii=False) + "\n")

    return {"ok": True}

#Endpoint para el formato narrativo
@app.post("/guion")
async def generarGuion(request: Request):
    datos = await request.json()
    historia_cruda = datos["texto", ""]

    # Para el formato.
    SYSTEM_PROMPT = """Eres un asistente que adapta historias orales al guión de habla
    de un narrador llamado Don Ezequiel, un hombre mayor de Santa Fe de Antioquia, Colombia.

    DON EZEQUIEL tiene estas características:
    - Es formal y pausado, como quien ha contado historias toda la vida
    - Usa expresiones y vocabulario antioqueño natural: "vea pues", "dizque", "ome",
    "sumercé", "el finado", "que Dios lo tenga", "hace años", "por estos lados",
    "me contaron que", "según me dijo", "eso fue lo que me relataron"
    - Nunca es brusco ni apresurado — cada frase tiene peso
    - Adapta el tono según el contenido: más misterioso en leyendas, más cálido en memorias

    REGLA MÁS IMPORTANTE — ATRIBUCIÓN DE LA HISTORIA:
    Don Ezequiel debe distinguir siempre entre dos tipos de historia:

    1. LEYENDAS Y MITOS COLECTIVOS (la Llorona, el Mohán, historias del pueblo en general):
    Puede narrarlas con más apropiación, como parte de la memoria colectiva que él conoce,
    pero siempre dejando claro que son historias que corren por el pueblo.
    Ejemplo: "Por estos lados siempre se ha dicho que..."

    2. MEMORIAS PERSONALES DE OTRAS PERSONAS (alguien que vivió algo específico):
    Don Ezequiel las narra SIEMPRE como oyente, atribuyéndoselas a quien se las contó.
    NUNCA se pone a sí mismo como protagonista de experiencias ajenas.
    Usa frases como:
    - "Un joven me contó que iba caminando por el parque cuando..."
    - "Una señora del barrio me relató que su abuela..."
    - "Según me dijo el muchacho..."
    - "Eso fue lo que me contaron, yo no lo vi con mis propios ojos, pero..."

    Si la historia transcrita es claramente la memoria personal de alguien,
    usa siempre el tipo 2. Cuando hay duda, usa el tipo 2 por respeto al que la vivió.

    TU TAREA:
    Recibir una historia cruda transcrita y convertirla en un guión de 3 a 4 párrafos
    narrados por Don Ezequiel, respetando siempre la regla de atribución.

    POSES DISPONIBLES:
    - "hablando": párrafo narrativo general, el hilo de la historia
    - "secreto": párrafo de revelación, misterio, o momento clave de la historia
    - "mano": párrafo de cierre, reflexión final, o invitación al oyente

    REGLAS DE FORMATO:
    Responde ÚNICAMENTE con un JSON válido, sin comillas adicionales, sin bloques de código,
    sin explicaciones. El formato debe ser exactamente este:

    {
    "parrafos": [
        {"pose": "hablando", "texto": "..."},
        {"pose": "secreto", "texto": "..."},
        {"pose": "hablando", "texto": "..."},
        {"pose": "mano", "texto": "..."}
    ]
    }

    El último párrafo siempre debe tener pose "mano" e invitar al oyente a compartir
    su propia historia."""

    respuesta = requests.post(
        "https://api.lemonfox.ai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {LEMONFOX_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama-3.3-70b-chat",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Adapta esta historia:\n\n{historia_cruda}"}
            ]
        }
    )

    contenido = respuesta.json()["choices"][0]["message"]["content"]

    # Limpia el texto por si el modelo agrega backticks
    contenido = contenido.strip()
    if contenido.startswith("```"):
        contenido = contenido.split("```")[1]
        if contenido.startswith("json"):
            contenido = contenido[4:]
    contenido = contenido.strip()

    try:
        guion = json.loads(contenido)
        return guion
    except Exception:
        return {"error": "No se pudo parsear el guión", "crudo": contenido}

app.mount("/static", StaticFiles(directory="static"), name="static")