# Jarvis — asistente personal para Android

Proyecto personal para Android (objetivo inicial: Redmi Note 13). El APK se compila con GitHub Actions.

## Funciones de esta versión compilada

- Activación por voz: **“Jarvis, activa”**.
- Reconocimiento de activación y de órdenes en español con Vosk local; las órdenes básicas no necesitan una API de voz en la nube.
- Tras activarlo, mantiene una conversación por varios turnos sin pedir la frase de activación cada vez. La sesión vuelve a espera tras silencio o al alcanzar el límite de turnos.
- Abre aplicaciones por el nombre que aparece en el teléfono.
- Busca contactos para llamadas y mensajes.
- Pide confirmación antes de realizar llamadas o enviar SMS. Los SMS pueden generar cargos según el operador.
- WhatsApp se abre con el texto preparado: la persona usuaria todavía toca **Enviar**.
- Respuestas básicas sin internet y conversación abierta opcional con Gemini API.
- Pantalla oscura renovada, icono vectorial, lista de permisos y estado para ver qué falta habilitar.

## Conversación online opcional

En la app, introduce la clave de Gemini en **Conversación online opcional** y pulsa **Guardar clave**. Puedes obtener una clave desde [Google AI Studio](https://aistudio.google.com/apikey). No añadas claves al repositorio.

La cuota gratuita tiene límites y no significa uso ilimitado. Jarvis no activa facturación por su cuenta; para evitar cargos, no habilites un plan de pago en la cuenta de Google. Sin clave o sin conexión, Jarvis sigue reconociendo las órdenes y usa respuestas locales básicas, pero no dispone de un modelo conversacional completo sin conexión.

La IA solo genera texto: no puede ejecutar directamente llamadas, SMS ni abrir aplicaciones. Las acciones del dispositivo siguen pasando por el intérprete de órdenes de Jarvis.

## Permisos y límites de Android

Concede solo los permisos que vayas a utilizar. El micrófono es necesario para escuchar; los contactos, para buscar nombres; llamadas y SMS, para esas acciones; notificaciones, para informar del estado.

Android restringe el lanzamiento de otras aplicaciones desde servicios en segundo plano. Para abrir apps por voz mientras Jarvis escucha en segundo plano, activa **Mostrar sobre otras apps** desde el botón de permisos de Jarvis. En Xiaomi/Redmi, las restricciones de batería y el inicio automático también pueden afectar la escucha continua.

La detección y el reconocimiento de voz están diseñados para funcionar localmente; Gemini requiere internet y una clave opcional. No se garantiza escucha continua cuando Android o MIUI detienen el servicio.

## Descargar el APK

1. Abre [la ejecución más reciente de “Construir APK de Jarvis”](https://github.com/franyelmartinez618-cloud/Jarvis_apk/actions/workflows/prepare-jarvis.yml).
2. En la ejecución completada, baja hasta **Artifacts**.
3. Descarga **jarvis-apk** y extrae `app-debug.apk`.

Los artefactos de Actions caducan después de 7 días. El APK actual es de depuración y todavía no se ha probado físicamente en un teléfono. Android exigirá que confirmes la instalación de un APK nuevo; una actualización instalada sobre la anterior requiere una firma de publicación persistente, que aún no está configurada.

## Código y compilación

El proyecto Android base está en `jarvis-android.zip`. Durante la compilación, `scripts/prepare_jarvis.py` prepara la conversación, el reconocimiento local, la pantalla y el icono. El flujo de `.github/workflows/prepare-jarvis.yml` descarga el modelo español y compila el APK.

No guardes contraseñas, datos personales ni claves de API en el repositorio.
