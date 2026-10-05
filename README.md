# Práctica diaria de chino mandarín (HSK) por Telegram

Aplicación personal que te envía cada día, por Telegram, una frase en chino
simplificado adaptada a tu nivel de HSK, con pinyin, traducción al español y
un desglose de las palabras clave. Incluye repetición espaciada (repasa
frases anteriores a los +1, +3, +7 y +30 días).

> **Estado actual: las 3 etapas están completas** — base de datos, mensajes
> de texto diarios por Telegram, audio (frase completa + cada palabra clave)
> e imagen ilustrativa para cada frase.

## 1. Qué necesitas antes de empezar

- Un computador con **Python 3.11 o superior** instalado.
- Una cuenta de Telegram (la app en tu teléfono o en telegram.org).
- Conexión a internet (solo hace falta para la primera descarga de datos y
  para que el bot funcione).

Todo lo demás es gratis: no se necesita ninguna tarjeta de crédito ni clave
de pago para nada de esto (ver la sección 10 para el detalle de cada fuente).

## 2. Crear tu bot de Telegram (una sola vez)

1. Abre Telegram y busca el usuario **@BotFather** (tiene una marca de
   verificación azul).
2. Envíale el comando `/newbot`.
3. Te pedirá un **nombre** para el bot (el que verás tú, ej. "Mi Profe de
   Chino") y luego un **usuario** que debe terminar en `bot` (ej.
   `mi_profe_chino_bot`).
4. BotFather te responderá con un mensaje que incluye un **token**, algo
   como:
   ```
   123456789:AAExampleTokenNoEsReal1234567
   ```
   Copia ese token completo, lo necesitarás en el paso 4.
5. Abre una conversación con tu bot nuevo (aparecerá un enlace `t.me/...`
   en la respuesta de BotFather) y presiona **Start** — así queda
   "activado" para poder hablarte primero.

## 3. Descargar e instalar el proyecto

Abre una terminal dentro de la carpeta del proyecto y ejecuta:

```bash
# 1. Crear un entorno virtual (aísla las dependencias del proyecto)
python3 -m venv .venv
source .venv/bin/activate        # en Windows: .venv\Scripts\activate

# 2. Instalar las dependencias
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Configurar tus datos

1. Copia el archivo de ejemplo de variables de entorno:
   ```bash
   cp .env.example .env
   ```
2. Abre `.env` con un editor de texto y pega tu token de Telegram:
   ```
   TELEGRAM_BOT_TOKEN=123456789:AAExampleTokenNoEsReal1234567
   ```
3. (Opcional) Revisa `config/config.yaml` para ajustar tu nivel inicial de
   HSK, el modo de estudio y la hora de envío diario. La zona horaria ya
   viene configurada en `America/Costa_Rica`. Todo esto también se puede
   cambiar después con comandos del bot (`/level`, `/time`).

## 5. Primera ejecución: descargar la biblioteca de estudio

La primera vez que ejecutes el programa, va a descargar automáticamente:

- El vocabulario oficial de HSK 1-6 (clásico) y de la banda HSK 3.0 "7-9"
  (fuente: [complete-hsk-vocabulary](https://github.com/drkameleon/complete-hsk-vocabulary)
  en GitHub, que ya incluye significados en inglés tomados de CC-CEDICT).
- Miles de frases de ejemplo en chino con su traducción real al español,
  desde [Tatoeba](https://tatoeba.org) (un proyecto colaborativo y
  gratuito de frases traducidas).
- Además, el bot traduce al español las palabras clave cuando aparecen en
   una lección y guarda el resultado. Si el servicio gratuito está saturado
   o no responde, muestra «traducción al español pendiente» en vez del
   significado inglés. El programa **nunca se detiene** por esto. Para
   reintentar la traducción masiva de la biblioteca, ejecuta:
  ```bash
  python -m data.build_library --retry-translations
  ```
  para completar las traducciones que faltaron.

Este primer proceso puede tardar **varios minutos**. La descarga de datos es
el paso principal; las traducciones de las palabras clave se hacen a medida
que aparezcan en tus lecciones. Es un proceso único: las próximas veces
que ejecutes el bot, ya no se repite.

Puedes ejecutarlo por separado antes de arrancar el bot (recomendado la
primera vez, para ver el progreso):

```bash
python -m data.build_library
```

## 6. Ejecutar el bot

```bash
python main.py
```

Si es la primera vez y no ejecutaste el paso anterior, `main.py` construirá
la biblioteca automáticamente antes de arrancar el bot.

Con el bot corriendo, ve a Telegram, abre el chat con tu bot y envía:

```
/start
```

Esto registra tu chat para que el bot te empiece a escribir todos los días a
la hora configurada.

## 7. Comandos disponibles en el bot

| Comando | Qué hace |
|---|---|
| `/start` | Registra tu chat y muestra tu configuración actual |
| `/level N [only\|below]` | Cambia tu nivel de HSK (1-7). `only` = solo ese nivel, `below` = ese nivel y los anteriores |
| `/time HH:MM` | Cambia la hora de envío diario (formato 24 horas) |
| `/another` | Te envía una frase nueva ahora mismo |
| `/review` | Te envía ahora los repasos pendientes (en vez de esperar al horario diario) |
| `/progress` | Muestra cuántas frases has estudiado, dominado y cuántos repasos tienes pendientes |
| `/reset` | Abre una confirmación para borrar el historial y las prácticas activas |
| `/stop` | Termina la práctica de pronunciación activa |

Cada frase (diaria, `/another` o `/review`) llega acompañada de:

- Una **imagen**: primero se intenta encontrar una foto real y con licencia
  libre (banco de imágenes [Openverse](https://openverse.org)) para la
  palabra clave más "fotografiable" de la frase (un sustantivo concreto).
  Si no hay un sustantivo claro o no se encuentra una foto adecuada, se
  genera automáticamente una tarjeta con el hanzi en grande y su pinyin
  debajo. Las fotos reales siempre incluyen su atribución (autor y
  licencia) como descripción del mensaje, tal como exigen sus licencias
  Creative Commons.
- Un **audio** con la pronunciación completa y, después, un audio corto por
   cada segmento del desglose (usando voces naturales de Microsoft Edge TTS; si ese
  servicio no responde, se usa Google TTS como respaldo automático).

El **desglose de la frase** incluye todas sus palabras en orden, no solo las
palabras HSK reconocidas. Para términos fuera de las listas HSK, el bot calcula
el pinyin y busca una traducción al español; esos resultados también se guardan
para reutilizarlos.

Tanto los audios como las imágenes se guardan en caché (`storage/audio/`,
`storage/images/`), así que la misma frase o palabra nunca se vuelve a
buscar/generar dos veces.

Debajo de cada frase hay un botón **Practicar pronunciación**. Púlsalo y envía
una nota de voz con esa frase; el bot te devuelve una puntuación aproximada de
coincidencia entre la transcripción y el texto. Puedes enviar varios intentos:
todos se comparan con la misma frase hasta pulsar **Terminar práctica** o usar
`/stop`. La puntuación mide similitud del texto reconocido, no evalúa con
precisión tonos ni calidad fonética.

El reconocimiento se ejecuta localmente con Whisper `base` y CPU, sin API de
pago. La primera nota de voz descarga el modelo (aproximadamente 145 MB) y
puede tardar más; después queda almacenado en la caché de modelos.

El botón **Reiniciar progreso** pide confirmación antes de borrar el historial
de estudio y las prácticas activas. No modifica el nivel ni el horario, y el
envío diario nunca reinicia el progreso automáticamente.

## 8. Mantenerlo corriendo todos los días

Mientras `python main.py` siga corriendo, el bot funcionará y respetará tu
horario configurado.

### Opción A: tu propio computador (Linux), con systemd

Esto deja el bot corriendo aunque cierres la terminal, y lo reinicia solo si
el computador se reinicia. Crea el archivo
`~/.config/systemd/user/chino-bot.service`:

```ini
[Unit]
Description=Bot de práctica de chino
After=network-online.target

[Service]
WorkingDirectory=/ruta/completa/a/Chinese
ExecStart=/ruta/completa/a/Chinese/.venv/bin/python main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

Reemplaza `/ruta/completa/a/Chinese` por la ruta real del proyecto (por
ejemplo `/home/tu_usuario/Desktop/Chinese`). Luego actívalo:

```bash
systemctl --user daemon-reload
systemctl --user enable --now chino-bot.service

# Ver que esté corriendo y revisar el log en vivo:
systemctl --user status chino-bot.service
journalctl --user -u chino-bot.service -f

# Para que siga corriendo incluso si cierras sesión:
loginctl enable-linger $USER
```

Para actualizarlo tras un cambio de código: `systemctl --user restart chino-bot.service`.

### Opción B: un servidor gratuito en la nube

Si prefieres no depender de tu computador, puedes desplegarlo en un servicio
con capa gratuita que mantenga procesos corriendo 24/7, como
[Railway](https://railway.app) o [Fly.io](https://fly.io):

1. Sube el proyecto a un repositorio de GitHub (recuerda que `.env` y
   `storage/` están en `.gitignore` y no se suben, lo cual es correcto).
2. Crea un nuevo proyecto en el servicio elegido y conéctalo a tu
   repositorio.
3. Configura la variable de entorno `TELEGRAM_BOT_TOKEN` en el panel del
   servicio (nunca la subas al repositorio).
4. Define el comando de arranque como `python main.py` (o `python3`).
5. **Importante:** estos servicios normalmente usan almacenamiento
   temporal — si el contenedor se reinicia, `storage/library.db` podría
   perderse y volver a descargarse solo. Si el servicio ofrece un
   "volumen persistente" gratuito, súmalo apuntando a la carpeta
   `storage/` para no perder tu progreso ni tener que re-descargar la
   biblioteca cada vez.

## 9. Estructura del proyecto

```
config/          # config.yaml + carga/guardado de configuración
data/            # base de datos SQLite, descarga de HSK/Tatoeba, consultas
srs/             # lógica de repetición espaciada (+1, +3, +7, +30 días)
audio/           # generación de audio (edge-tts, con respaldo en gTTS) y caché
images/          # búsqueda de fotos (Openverse) + tarjeta de respaldo (Pillow)
bot/             # comandos, formato de mensajes y envío de audio/imagen
scheduler/       # tarea diaria programada (APScheduler)
storage/         # base de datos, audio/imágenes en caché, fuente y logs (no se sube a git)
main.py          # arranca todo
```

## 10. Notas sobre las fuentes de datos y licencias

- **Vocabulario HSK:** [complete-hsk-vocabulary](https://github.com/drkameleon/complete-hsk-vocabulary)
  (MIT), que a su vez combina listas de HSK 2.0/3.0 y definiciones de
  CC-CEDICT (CC BY-SA).
- **Frases de ejemplo:** [Tatoeba](https://tatoeba.org) (CC BY 2.0 FR /
  CC0), frases y traducciones aportadas por su comunidad.
- **Fotos:** [Openverse](https://openverse.org), que agrega contenido con
  licencias Creative Commons; cada foto usada muestra su atribución.
- **Fuente tipográfica:** [Noto Sans SC](https://github.com/google/fonts)
  (licencia SIL Open Font License), usada para las tarjetas de respaldo.

Todo funciona sin necesidad de tarjetas de crédito ni claves de pago.
