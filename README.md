# Jarvis — asistente personal para Android

Proyecto personal para Android (objetivo inicial: Redmi Note 13). El APK se compila con GitHub Actions.

## Funciones de esta versión compilada

- Activación por voz: **“Jarvis, activa”**.
- Reconocimiento de activación y de órdenes en español con Vosk local; las órdenes básicas no necesitan una API de voz en la nube.
- Tras activarlo, mantiene una conversación por varios turnos sin pedir la frase de activación cada vez. La sesión vuelve a espera tras silencio o al alcanzar el límite de turnos.
- Abre aplicaciones por el nombre que aparece en el teléfono.
- Control opcional de pantalla mediante Accesibilidad: pulsar controles visibles por texto, escribir en el campo enfocado, desplazarse, volver atrás, ir al inicio, abrir notificaciones/ajustes rápidos y leer el texto visible.
- Las acciones de pantalla que puedan enviar, publicar, pagar o borrar requieren una segunda confirmación por voz; Accesibilidad debe activarse manualmente desde Ajustes de Android.
- Busca contactos para llamadas y mensajes.
- Pide confirmación antes de realizar llamadas o enviar SMS. Los SMS pueden generar cargos según el operador.
- WhatsApp se abre con el texto preparado: la persona usuaria todavía toca **Enviar**.
- Respuestas básicas sin internet; conversación natural local después de instalar una vez el modelo de lenguaje (~329 MB). Gemini online queda como opción separada.
- Pantalla oscura renovada, icono vectorial, lista de permisos y estado para ver qué falta habilitar.

## Conversación online opcional

En la app, introduce la clave de Gemini en **Conversación online opcional** y pulsa **Guardar clave**. Puedes obtener una clave desde [Google AI Studio](https://aistudio.google.com/apikey). No añadas claves al repositorio.

La cuota gratuita tiene límites y no significa uso ilimitado. Jarvis no activa facturación por su cuenta; para evitar cargos, no habilites un plan de pago en la cuenta de Google. Sin clave o sin conexión, Jarvis sigue reconociendo las órdenes y usa respuestas locales básicas, pero no dispone de un modelo conversacional completo sin conexión.

La IA solo genera texto: no puede ejecutar directamente llamadas, SMS ni abrir aplicaciones. Las acciones del dispositivo siguen pasando por el intérprete de órdenes de Jarvis.

## Permisos y límites de Android

Concede solo los permisos que vayas a utilizar. El micrófono es necesario para escuchar; los contactos, para buscar nombres; llamadas y SMS, para esas acciones; notificaciones, para informar del estado.

Android restringe el lanzamiento de otras aplicaciones desde servicios en segundo plano. Para abrir apps por voz mientras Jarvis escucha en segundo plano, activa **Mostrar sobre otras apps** desde el botón de permisos de Jarvis. Para interactuar con controles visibles dentro de otras apps, pulsa **Activar control de pantalla (Accesibilidad)** y habilita Jarvis manualmente en Ajustes de Accesibilidad. El servicio procesa la pantalla por orden y no guarda ni transmite eventos. En Xiaomi/Redmi, las restricciones de batería y el inicio automático también pueden afectar la escucha continua.

La detección y el reconocimiento de voz están diseñados para funcionar localmente; Gemini requiere internet y una clave opcional. En el primer uso Jarvis ofrece preparar el cerebro local: el modelo (~329 MB) se descarga una sola vez y se guarda en los datos privados de la app; no se vuelve a descargar en cada actualización. Se recomienda Wi-Fi. El botón de batería ayuda a abrir el ajuste de exclusión del ahorro de energía, pero Android/MIUI todavía pueden detener servicios y el usuario debe habilitar Inicio automático en Xiaomi si existe esa opción.

## Actualizaciones desde el móvil

Cuando un cambio se integra en `main`, GitHub Actions compila la aplicación y, si sigue configurada la firma estable, publica la nueva versión. No tienes que reconstruir ni subir el APK a mano. Jarvis comprueba al abrirse si existe una versión más nueva y vuelve a consultar como máximo cada 6 horas; también incluye **Buscar actualizaciones de Jarvis**. Si hay una versión publicada, descarga el APK y abre el instalador. **Android siempre exige que confirmes la instalación**: una app normal no puede reemplazarse silenciosamente.

Para publicar actualizaciones permanentes hace falta una clave de firma estable. Se configura una sola vez en tu PC (no dentro de la carpeta del repositorio). En PowerShell ejecuta estos dos comandos desde una carpeta segura donde guardar el archivo:

```powershell
keytool -genkeypair -v -keystore "$PWD\jarvis-release.jks" -alias jarvis -keyalg RSA -keysize 2048 -validity 10000 -storepass "JarvisKeystorePassword_2026" -keypass "JarvisKeystorePassword_2026" -dname "CN=Jarvis, O=Personal App, C=CO"
[Convert]::ToBase64String([IO.File]::ReadAllBytes("$PWD\jarvis-release.jks")) | Set-Clipboard
```

Después abre [los secretos del repositorio en GitHub](https://github.com/franyelmartinez618-cloud/Jarvis_apk/settings/secrets/actions), pulsa **New repository secret**, pon como nombre `JARVIS_KEYSTORE_BASE64` y pega con Ctrl+V el valor que quedó en el portapapeles. No publiques ni subas el archivo `.jks`; conserva una copia de respaldo en un lugar seguro. El alias y la contraseña están fijados en el flujo de compilación, por lo que **solo hace falta crear ese único secreto**.

Hasta que exista ese secreto, GitHub seguirá compilando un APK de prueba que caduca a los 7 días y no publicará actualizaciones permanentes. La primera instalación firmada estable puede requerir reinstalar el APK de prueba que tengas ahora, porque las compilaciones de prueba anteriores no compartían una firma persistente. Las instalaciones futuras podrán actualizarse sobre la misma app, con la confirmación de Android.

## Descargar el APK de prueba

1. Abre [las ejecuciones de “Construir APK de Jarvis”](https://github.com/franyelmartinez618-cloud/Jarvis_apk/actions/workflows/prepare-jarvis.yml).
2. En una ejecución completada, baja hasta **Artifacts**.
3. Descarga **jarvis-apk** y extrae `app-debug.apk`.
## Código y compilación

El proyecto Android base está en `jarvis-android.zip`. Durante la compilación, `scripts/prepare_jarvis.py` prepara la conversación, el reconocimiento local, la pantalla y el icono; `scripts/prepare_jarvis_updates.py` agrega el verificador de versiones y la configuración de firma. El flujo de `.github/workflows/prepare-jarvis.yml` descarga los modelos y compila el APK.

No guardes contraseñas, datos personales ni claves de API en el repositorio.
