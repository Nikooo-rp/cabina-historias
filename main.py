# main.py
import json
import re
import hashlib
from dotenv import load_dotenv

from fastapi import FastAPI, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
import requests, tempfile, os
from datetime import datetime
from openai import OpenAI

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# APIs
LEMONFOX_API_KEY    = os.getenv("API_KEY")
ELEVENLABS_API_KEY  = os.getenv("11LAB_KEY")
ELEVENLABS_VOICE_ID = "gUMwNXyuudv6WujOBL4s"

# Archivos y carpetas
ARCHIVO_HISTORIAS = "historias.jsonl"
ARCHIVO_GUIONES   = "guiones.jsonl"
CARPETA_AUDIOS    = "audios"
os.makedirs(CARPETA_AUDIOS, exist_ok=True)

client = OpenAI(
    api_key=LEMONFOX_API_KEY,
    base_url="https://api.lemonfox.ai/v1",
)

with open("instrucciones.txt", "r", encoding="utf-8") as f:
    instructions = f.read()

if not LEMONFOX_API_KEY:
    raise ValueError("No se ha establecido la variable de entorno API_KEY para Lemonfox")

# ─── Prompts ──────────────────────────────────────────────────────────────────

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

EXPRESIONES CONVERSACIONALES FRECUENTES:
¿usté ubica?, ¿usted sabe?, ¿me entiende?, ¿cierto?,
¿sí o no?, ¿verdad?, ¿ve?, vea que, resulta que,
es que, o sea, digamos, por decir algo, como le dijera.

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

SYSTEM_PROMPT_GUION = """Eres un asistente que adapta historias orales al guión de habla
de un narrador llamado Don Ezequiel, un hombre mayor de Santa Fe de Antioquia, Colombia.

DON EZEQUIEL tiene estas características:
Es formal y pausado, como quien ha contado historias toda la vida
Habla con economía de palabras — dice lo justo, nunca rellena ni explica de más
Usa expresiones antioqueñas naturales pero con moderación, no en cada frase: "vea pues", "dizque", "ome", "sumercé", "el finado", "hace años", "por estos lados"
Deja que la historia respire — no moraliza ni explica lo que ya es evidente
Nunca repite una idea que ya dijo antes

ANTES DE ADAPTAR LA HISTORIA:
1. Corrige errores obvios de transcripción automática, especialmente:
   - Topónimos inventados que en realidad son expresiones conversacionales (ejemplo: "ustubica" → "¿usté ubica?", "playa principal" → "plaza principal")
   - Palabras cortadas o unidas por error del transcriptor
   - Nombres de lugares de Santa Fe de Antioquia mal escritos
   No corrijas el estilo oral ni las muletillas — esas son intencionales.

2. REGLA FUNDAMENTAL DE TRANSFORMACIÓN DE PERSONA:
   Si la historia original está contada en primera persona ("yo vi", "me pasó", "yo fui"), debes transformarla a tercera persona atribuida a un narrador anónimo o a un tercero identificado como "alguien", "un señor", "una persona", "el finado fulano", etc.
   NUNCA preserves el "yo" del hablante original.
   NUNCA pongas a Don Ezequiel como protagonista de esas experiencias.
   Ejemplo: Original "yo me apareció el ánima" → Transformado "a un señor se le apareció el ánima"

REGLA MÁS IMPORTANTE — ATRIBUCIÓN DE LA HISTORIA:
Don Ezequiel distingue siempre entre dos tipos de historia:

1. LEYENDAS Y MITOS COLECTIVOS:
   Las narra como parte de la memoria del pueblo, sin apropiárselas.
   Ejemplo: "Por estos lados siempre se ha dicho que..."

2. MEMORIAS PERSONALES DE OTRAS PERSONAS:
   Las narra SIEMPRE como oyente, atribuyéndoselas a quien se las contó.
   NUNCA se pone a sí mismo como protagonista de experiencias ajenas.
   Ejemplo: "Un muchacho me contó que iba por el parque cuando..."
   Si hay duda, usa siempre el tipo 2.

POSES DISPONIBLES:
- "saludo": bienvenida breve y cálida — MÁXIMO 2 frases.
  Don Ezequiel saluda al visitante y anuncia que va a contar una historia.
  Ejemplo: "Buenas tardes tenga usted. Siéntese pues, que hoy le tengo una historia."
- "hablando": párrafo narrativo, el hilo de la historia
- "secreto": el momento clave, la revelación, el detalle misterioso
- "mano": cierre e invitación — MÁXIMO 1 frase, directa y cálida, sin explicar por qué invita.
  Ejemplos: "¿Y usted, no tendrá alguna historia guardada de por estos lados?"
            "Cuénteme pues, ¿qué sabe usted de esto?"

TU TAREA:
Convertir la historia cruda en un guión de 4 o 5 párrafos cortos.
El primero siempre es "saludo", el último siempre es "mano".
Cada párrafo máximo 4 frases. Sin relleno, sin moralejas, sin repeticiones.

FORMATO — responde ÚNICAMENTE con este JSON válido, sin explicaciones ni backticks:

{
  "parrafos": [
    {"pose": "saludo",   "texto": "..."},
    {"pose": "hablando", "texto": "..."},
    {"pose": "secreto",  "texto": "..."},
    {"pose": "mano",     "texto": "..."}
  ]
}"""

SYSTEM_PROMPT_GRACIAS = """Eres Don Ezequiel, un narrador mayor de Santa Fe de Antioquia.
Alguien acaba de contarte una historia. Responde con UN solo párrafo muy breve (máximo 2 frases)
agradeciéndole de forma cálida y diciéndole que vas a guardar esa historia para contársela a otros.
Usa vocabulario antioqueño natural. Solo el texto, sin JSON, sin explicaciones."""

# ─── Correcciones de transcripción ───────────────────────────────────────────

CORRECCIONES = {
    "la playa principal de ustubica": "la plaza principal, ¿usté ubica?",
    "ustubica": "¿usté ubica?",
    "playa principal": "plaza principal",
}

def corregir_transcripcion(texto: str) -> str:
    for error, correcto in CORRECCIONES.items():
        texto = re.sub(re.escape(error), correcto, texto, flags=re.IGNORECASE)
    return texto

# ─── Helpers de archivo ───────────────────────────────────────────────────────

def leer_archivo(path: str) -> list:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

def escribir_archivo(path: str, registros: list):
    with open(path, "w", encoding="utf-8") as f:
        for r in registros:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def agregar_linea(path: str, registro: dict):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")

# ─── Caché de audios ─────────────────────────────────────────────────────────

def ruta_audio(texto: str) -> str:
    """Genera una ruta única basada en el contenido del texto."""
    hash_texto = hashlib.md5(texto.encode()).hexdigest()
    return os.path.join(CARPETA_AUDIOS, f"{hash_texto}.mp3")

# ─── Lógica de LLM ───────────────────────────────────────────────────────────

def llamar_llm(texto: str) -> str:
    respuesta = requests.post(
        "https://api.lemonfox.ai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {LEMONFOX_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama-3.3-70b-chat",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_GUION},
                {"role": "user",   "content": f"Adapta esta historia:\n\n{texto}"}
            ],
            "temperature":       0.4,
            "frequency_penalty": 0.8,
            "presence_penalty":  0.6,
            "max_tokens":        700
        }
    )
    return respuesta.json()["choices"][0]["message"]["content"]

def llamar_llm_simple(texto: str) -> str:
    r = requests.post(
        "https://api.lemonfox.ai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {LEMONFOX_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama-3.3-70b-chat",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_GRACIAS},
                {"role": "user", "content": f"La historia que me contaron fue:\n\n{texto}"}
            ],
            "temperature": 0.6,
            "max_tokens": 120
        }
    )
    return r.json()["choices"][0]["message"]["content"].strip()

def parsear_guion(contenido: str) -> dict:
    contenido = contenido.strip()
    if contenido.startswith("```"):
        contenido = contenido.split("```")[1]
        if contenido.startswith("json"):
            contenido = contenido[4:]
    return json.loads(contenido.strip())

def generar_y_guardar_guion(historia: dict) -> dict:
    texto_corregido = corregir_transcripcion(historia["texto"])
    contenido = llamar_llm(texto_corregido)
    guion = parsear_guion(contenido)
    guion["id"] = historia["id"]

    if historia["id"] != 0:
        guiones = leer_archivo(ARCHIVO_GUIONES)
        guiones = [g for g in guiones if g["id"] != historia["id"]]
        guiones.append(guion)
        escribir_archivo(ARCHIVO_GUIONES, guiones)

    return guion

# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/")
def raiz():
    return {"mensaje": "Servidor funcionando"}

@app.post("/transcribir")
async def transcribir(audio: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name

    try:
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

        numero = len(leer_archivo(ARCHIVO_HISTORIAS)) + 1
        historia = {
            "id":    numero,
            "fecha": datetime.now().strftime("%Y-%m-%d"),
            "hora":  datetime.now().strftime("%H:%M:%S"),
            "texto": texto
        }
        agregar_linea(ARCHIVO_HISTORIAS, historia)
        guion = generar_y_guardar_guion(historia)

        return {"texto": texto, "numero": numero, "guion": guion}

    except Exception as e:
        return {"error": str(e)}
    finally:
        os.unlink(tmp_path)

@app.get("/historias")
def ver_historias():
    historias = leer_archivo(ARCHIVO_HISTORIAS)
    return {"historias": historias, "total": len(historias)}

@app.post("/ubicar")
async def ubicar(request: Request):
    datos = await request.json()
    historias = leer_archivo(ARCHIVO_HISTORIAS)

    encontrada = False
    for h in historias:
        if h["id"] == datos["id"]:
            h["lat"] = datos["lat"]
            h["lng"] = datos["lng"]
            encontrada = True
            break

    if not encontrada:
        return {"error": f"No se encontró la historia con id {datos['id']}"}

    escribir_archivo(ARCHIVO_HISTORIAS, historias)
    return {"ok": True}

@app.get("/guiones")
def ver_guiones():
    guiones = leer_archivo(ARCHIVO_GUIONES)
    return {"guiones": guiones, "total": len(guiones)}

@app.get("/guion/{id}")
def ver_guion(id: int):
    guiones = leer_archivo(ARCHIVO_GUIONES)
    for g in guiones:
        if g["id"] == id:
            return g
    return {"error": f"No hay guión para la historia {id}"}

@app.post("/guion")
async def generar_guion(request: Request):
    datos = await request.json()
    historia_id = datos.get("id")

    if historia_id:
        historias = leer_archivo(ARCHIVO_HISTORIAS)
        historia  = next((h for h in historias if h["id"] == historia_id), None)
        if not historia:
            return {"error": f"No se encontró la historia {historia_id}"}
    else:
        texto = datos.get("texto", "")
        historia = {"id": 0, "texto": texto}

    try:
        guion = generar_y_guardar_guion(historia)
        return guion
    except Exception as e:
        return {"error": str(e)}

@app.post("/corregir")
async def corregir(request: Request):
    datos       = await request.json()
    id          = datos.get("id")
    texto_nuevo = datos.get("texto")

    if not id or not texto_nuevo:
        return {"error": "Se necesita id y texto"}

    historias = leer_archivo(ARCHIVO_HISTORIAS)
    encontrada = False
    for h in historias:
        if h["id"] == id:
            h["texto"]            = texto_nuevo
            h["corregida_manual"] = True
            encontrada            = True
            break

    if not encontrada:
        return {"error": f"No se encontró la historia {id}"}

    escribir_archivo(ARCHIVO_HISTORIAS, historias)
    historia = next(h for h in historias if h["id"] == id)
    try:
        guion = generar_y_guardar_guion(historia)
        return {"ok": True, "guion": guion}
    except Exception as e:
        return {"error": str(e)}

@app.post("/tts")
async def tts(request: Request):
    datos = await request.json()
    texto = datos.get("texto", "")
    ruta  = ruta_audio(texto)

    # Si ya existe el audio, lo devuelve directamente sin llamar a ElevenLabs
    if os.path.exists(ruta):
        return FileResponse(ruta, media_type="audio/mpeg")

    # Si no existe, lo genera y guarda
    respuesta = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
        headers={
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        },
        json={
            "text": texto,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.75,
                "similarity_boost": 0.85,
                "style": 0.4,
                "use_speaker_boost": True
            }
        }
    )
    respuesta.raise_for_status()

    with open(ruta, "wb") as f:
        f.write(respuesta.content)

    return Response(content=respuesta.content, media_type="audio/mpeg")

@app.get("/historia-aleatoria")
def historia_aleatoria():
    guiones = leer_archivo(ARCHIVO_GUIONES)
    if not guiones:
        return {"error": "No hay historias aún"}
    import random
    return random.choice(guiones)

@app.post("/gracias")
async def generar_gracias(request: Request):
    datos = await request.json()
    texto = datos.get("texto", "")
    contenido = llamar_llm_simple(texto)
    return {"texto": contenido}

@app.get("/frases-transicion")
def frases_transicion():
    import random
    transicion = random.choice([
        "Y dígame, ¿en qué rincón del pueblo fue que ocurrió eso?",
        "¿Y dónde fue que pasó todo eso, usté sabe?",
        "Cuénteme, ¿en qué parte del pueblo ocurrió esa historia?",
        "¿Y en qué lugar de por aquí fue que sucedió eso?",
    ])
    despedida = random.choice([
        "Que le vaya bien, pues. Si quiere, puede ver dónde están todas las historias del pueblo en el mapa.",
        "Vaya con Dios. Y si tiene curiosidad, puede echarle un ojo al mapa con las historias de por aquí.",
        "Bueno pues, fue un gusto. Puede ver el mapa con todas las historias si le provoca.",
    ])
    return {"transicion": transicion, "despedida": despedida}

app.mount("/static", StaticFiles(directory="static"), name="static")