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

## Actualizaciones desde el móvil

Jarvis consulta al abrirse si existe una versión posterior y vuelve a revisar como máximo cada 6 horas; también hay un botón **Buscar actualizaciones de Jarvis**. Si encuentra una versión publicada, puede descargar el APK y abrir el instalador de Android. **Android todavía te pedirá autorizar la instalación**; las apps normales no pueden sustituirse silenciosamente.

Cada compilación de `main` puede publicar un GitHub Release permanente, pero solo cuando se configura la firma estable. Para activarla, crea una clave una sola vez en tu PC y guárdala fuera del repositorio:

```powershell
keytool -genkeypair -v -keystore jarvis-release.jks -alias jarvis -keyalg RSA -keysize 2048 -validity 10000
[Convert]::ToBase64String([IO.File]::ReadAllBytes(".\jarvis-release.jks"))
```

En GitHub abre **Settings → Secrets and variables → Actions → New repository secret** y crea estos cuatro secretos: `JARVIS_KEYSTORE_BASE64` (pega la salida Base64 del segundo comando), `JARVIS_STORE_PASSWORD`, `JARVIS_KEY_ALIAS` (valor `jarvis`) y `JARVIS_KEY_PASSWORD`. No subas el archivo `.jks` ni las contraseñas al repositorio. Conserva ese mismo archivo de firma y su contraseña: si se pierden o cambian, Android rechazará las futuras actualizaciones sobre esa instalación.

Hasta configurar esos secretos, Actions seguirá generando el APK de depuración como artefacto temporal de 7 días y no publicará un APK de actualización. La primera actualización desde una instalación antigua de depuración también puede requerir una reinstalación si su firma no coincide con la clave estable; no desinstales hasta tener claro que conservas cualquier configuración local importante.

## Descargar el APK de prueba

1. Abre [las ejecuciones de “Construir APK de Jarvis”](https://github.com/franyelmartinez618-cloud/Jarvis_apk/actions/workflows/prepare-jarvis.yml).
2. En una ejecución completada, baja hasta **Artifacts**.
3. Descarga **jarvis-apk** y extrae `app-debug.apk`.
## Código y compilación

El proyecto Android base está en `jarvis-android.zip`. Durante la compilación, `scripts/prepare_jarvis.py` prepara la conversación, el reconocimiento local, la pantalla y el icono; `scripts/prepare_jarvis_updates.py` agrega el verificador de versiones y la configuración de firma. El flujo de `.github/workflows/prepare-jarvis.yml` descarga los modelos y compila el APK.

No guardes contraseñas, datos personales ni claves de API en el repositorio.
