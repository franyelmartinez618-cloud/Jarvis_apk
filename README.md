# Jarvis — asistente personal Android

Jarvis conserva el mismo paquete Android y repositorio. La aplicación pasa a una arquitectura híbrida: un contenedor Android pequeño y una interfaz web que puede actualizarse sin reemplazar el APK.

## Qué cambia en esta versión

- Se elimina el uso del micrófono, el reconocimiento de voz, el registro biométrico de voz y los servicios de escucha en segundo plano.
- Android ya no solicita permiso de micrófono. El flujo de compilación comprueba que RECORD_AUDIO no aparezca en el manifiesto final.
- La pantalla principal es un chat de texto, no un menú con varios pasos.
- La conversación, historial y recuerdos se procesan y guardan localmente en el dispositivo.
- No se envían mensajes a Gemini, ChatGPT, Qwen, OpenAI ni a otra API conversacional.
- El control de pantalla es opcional. Solo se activa manualmente en Ajustes > Accesibilidad; no es necesario para conversar.
- Las acciones de pantalla que pueden enviar, publicar, pagar, comprar o borrar solicitan confirmación.

## Actualizaciones sin APK para el chat y la interfaz

La interfaz vive en la carpeta web y se publica en GitHub Pages mediante el workflow deploy-jarvis-web.yml.

URL web prevista:

https://franyelmartinez618-cloud.github.io/Jarvis_apk/

Después de instalar por primera vez el nuevo contenedor web:

1. Cada cambio en web/** se publica como página estática desde GitHub Actions.
2. Jarvis consulta el identificador de versión mientras está abierto y recarga la interfaz cuando detecta un cambio.
3. El service worker guarda los archivos para que la conversación local siga abriendo cuando no hay conexión.
4. No se descarga ni instala un APK para cambios de HTML, CSS, JavaScript, respuestas, reglas o habilidades que ya estén disponibles en el puente nativo.

Configuración única de GitHub Pages: en el repositorio abre Settings > Pages y elige GitHub Actions como Source. GitHub Pages solo se puede desplegar cuando esa fuente está habilitada. Después, el workflow publica automáticamente cada cambio web.

La copia web que viene dentro del APK sirve como respaldo inicial/sin conexión. Cuando hay conexión, la app carga la versión publicada.

## Qué todavía requiere APK

La web puede actualizar la interfaz, memoria local, reglas conversacionales y uso de funciones nativas que ya estén expuestas por el puente Android. No puede añadir por sí sola permisos nuevos, servicios del sistema, código Kotlin, cambios del manifiesto ni capacidades nativas que aún no existen.

Esos cambios siguen necesitando una nueva versión nativa. La aplicación actual se instala desde APK de GitHub, no desde Google Play, por lo que no puede utilizar el mecanismo de actualizaciones de Play hasta que se publique e instale desde Play Store. Google Play ofrece actualizaciones flexibles e inmediatas para aplicaciones distribuidas por esa tienda; el usuario debe tener una instalación elegible de Play. Consulta la documentación oficial de actualizaciones integradas:
https://developer.android.com/guide/playcore/in-app-updates

No se intenta instalar código ejecutable Android desde una web: solo se actualiza la interfaz y lógica JavaScript interpretada en WebView.

## Conversación local: alcance real

El núcleo inicial de conversación está escrito específicamente para este proyecto, sin pesos ni API de un modelo generativo externo. Incluye interpretación de comandos, respuestas propias, operaciones aritméticas sencillas, contexto de conversación y recuerdos locales. Todavía NO es un modelo generativo general entrenado desde cero y no puede responder con la amplitud de una IA grande. No se debe presentar como AGI ni como un LLM autónomo.

Una IA generativa real entrenada desde cero requiere un corpus de entrenamiento, infraestructura de cómputo, un proceso de evaluación y ciclos de entrenamiento. No se obtiene únicamente cambiando la pantalla ni puede prometerse una calidad equivalente a los modelos grandes con este motor de reglas.

## Acciones disponibles en esta base

- Abrir aplicaciones instaladas por nombre.
- Leer el texto visible de la pantalla, si se activa Accesibilidad.
- Pulsar controles visibles y escribir en el campo enfocado, si se activa Accesibilidad.
- Volver atrás, ir al inicio y desplazarse por una pantalla, si se activa Accesibilidad.
- Abrir búsquedas web o de YouTube solicitadas por la persona.
- Abrir el marcador telefónico, sin iniciar una llamada automáticamente.
- Recordar el nombre y notas que la persona decida guardar. Los recuerdos se quedan en almacenamiento local del dispositivo.

La lectura y control de pantalla pueden exponer contenido privado a la función de Accesibilidad. Actívala solo si realmente necesitas esas acciones y revisa sus permisos en Android.

## Compilación

El proyecto Android base se mantiene en jarvis-android.zip. El flujo de APK:

1. Extrae el proyecto base.
2. Ejecuta los preparadores de accesibilidad, firma y contenedor web.
3. Elimina el código fuente de voz legado, los modelos de voz, las bibliotecas nativas de voz y todos los permisos Android que ya no se necesitan.
4. Compila un APK de depuración y, si está configurada la firma estable, el APK de lanzamiento.

Los cambios solo en web/** no disparan una nueva compilación APK: únicamente publican la interfaz web.

## Privacidad

La conversación y memoria no se envían a un servidor de IA. La conexión de red se utiliza para cargar y actualizar los archivos estáticos de la interfaz; las búsquedas externas solo se abren cuando la persona las solicita. Si se utiliza el control de pantalla, la lectura se procesa localmente en Android y depende de la autorización de Accesibilidad.

No guardes contraseñas, claves privadas ni secretos en el repositorio.
