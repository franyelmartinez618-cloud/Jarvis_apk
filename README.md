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
- Motor local propio de intenciones y habilidades deterministas: comandos, fecha/hora, navegación y acciones de pantalla. No usa Gemini, Qwen ni una IA conversacional remota; no descarga modelos de lenguaje de terceros.
- Pantalla oscura renovada, icono vectorial, lista de permisos y estado para ver qué falta habilitar.

## Funcionamiento offline

JARVIS no envía mensajes de voz o texto a Gemini ni a otra IA remota, y no descarga modelos de lenguaje como Qwen. La respuesta de conversación general se basa en un motor local de intenciones y respuestas mantenido en este proyecto; cuando no tiene una habilidad para contestar, lo reconoce en lugar de inventar respuestas.

La detección y el reconocimiento de voz usan motores/modelos de voz empaquetados que funcionan localmente en el teléfono. No son un modelo conversacional creado desde cero. Entrenar un modelo neuronal completo propio requeriría un proyecto separado de datos y entrenamiento; esta compilación no se presenta como una IA general.

La conexión a Internet que conserva la app se utiliza para revisar y descargar actualizaciones oficiales desde GitHub. No se usa para inferencia de IA.

## Permisos y límites de Android

Concede solo los permisos que vayas a utilizar. El micrófono es necesario para escuchar; los contactos, para buscar nombres; llamadas y SMS, para esas acciones; notificaciones, para informar del estado.

Android restringe el lanzamiento de otras aplicaciones desde servicios en segundo plano. Para abrir apps por voz mientras Jarvis escucha en segundo plano, activa **Mostrar sobre otras apps** desde el botón de permisos de Jarvis. Para interactuar con controles visibles dentro de otras apps, pulsa **Activar control de pantalla (Accesibilidad)** y habilita Jarvis manualmente en Ajustes de Accesibilidad. El servicio procesa la pantalla por orden y no guarda ni transmite eventos. En Xiaomi/Redmi, las restricciones de batería y el inicio automático también pueden afectar la escucha continua.

En la primera apertura aparece una ventana de configuración y, después, Android solicita los permisos individualmente. La voz se registra con dos muestras de unos tres segundos. El verificador se precarga en segundo plano y mantiene una sesión local de confianza durante 90 segundos para evitar calcular la huella completa de voz en cada orden. La escucha limita cada turno a ocho segundos para no quedarse esperando indefinidamente; las órdenes largas conviene decirlas en frases separadas. Esto reduce la espera; la precisión real debe comprobarse en el teléfono. Android/MIUI todavía pueden detener servicios y el usuario debe habilitar Inicio automático en Xiaomi si esa opción existe.

## Actualizaciones desde el móvil

Cuando un cambio se integra en `main`, GitHub Actions compila y publica el APK firmado automáticamente. JARVIS comprueba si hay una versión nueva al abrirse. Cuando se instala una versión nueva, la próxima apertura muestra una cuenta regresiva de tres segundos y reinicia el servicio local si estaba activo antes de la actualización. **Android siempre exige que confirmes la instalación**: una app normal no puede reemplazarse silenciosamente.

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
