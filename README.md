# JARVIS — asistente de voz local para Android

Jarvis es una aplicación Android de interacción por voz. Se abre, se inicia el servicio y se habla con él; no es un chat de texto. El proyecto conserva el paquete Android, la identidad de firma estable y la posibilidad de actualizar la instalación existente.

## Arquitectura de voz y cerebro local

- **Voz de entrada (ASR):** Vosk con el modelo pequeño de español incluido en la APK. Convierte el habla a texto dentro del teléfono.
- **Cerebro conversacional:** Qwen3-1.7B en formato LiteRT-LM, ejecutado en el dispositivo. Sustituye las respuestas fijas como motor de conversación.
- **Voz de salida (TTS):** TextToSpeech de Android. La voz disponible depende del motor e idioma instalados en el teléfono.
- **Acciones:** herramientas Kotlin que invocan APIs de Android, un analizador local de órdenes frecuentes y el servicio opcional de Accesibilidad.

El archivo del cerebro local pesa aproximadamente **932 MiB (977 MB)**. No se mete dentro de la APK para que las actualizaciones de la aplicación no tengan que volver a descargarlo. La primera vez que se inicia una instalación que no tiene el modelo, Jarvis pide permiso para descargarlo; se necesita conexión a internet y al menos 1.2 GB libres. Se guarda en el almacenamiento privado de la aplicación, se comprueba con SHA-256 y después el texto de la conversación se procesa localmente, sin enviarlo a Gemini, ChatGPT ni a una API conversacional remota. La descarga inicial sí usa internet.

El modelo está publicado con licencia Apache 2.0 por LiteRT Community. Es un modelo abierto preentrenado, no un modelo privado entrenado desde cero para Jarvis. **No es AGI ni tiene capacidades literalmente ilimitadas.** Su calidad, rapidez y memoria disponible dependen del teléfono; aún hay que probarlo en cada dispositivo objetivo.

## Acciones de Android conectadas

El puente de herramientas y el analizador directo cubren estas acciones:

- Abrir aplicaciones instaladas por nombre, con tolerancia a errores pequeños de pronunciación o transcripción; consultar la lista de aplicaciones visibles para el lanzador.
- Buscar contactos, incluidos algunos apodos familiares habituales; preparar llamadas y mensajes por WhatsApp o SMS.
- Leer el texto de la pantalla, desplazarse, escribir en un campo enfocado y pulsar controles visibles mediante Accesibilidad.
- Abrir una búsqueda web o una búsqueda de un lugar en mapas.
- Abrir la cámara, controlar la linterna, cambiar el volumen multimedia y ajustar el brillo si Android concede el acceso correspondiente.
- Preparar una alarma o un temporizador en la aplicación de reloj; abrir el editor de calendario con un evento.

Llamadas, SMS, mensajes y acciones sensibles de pantalla requieren confirmación hablada antes de continuar. WhatsApp abre el mensaje preparado y la persona debe tocar «Enviar». El calendario y el reloj muestran sus pantallas nativas para que se revise y guarde o inicie la acción.

El analizador directo ejecuta órdenes comunes sin depender de que el modelo genere una llamada a herramienta. Las peticiones que no coinciden con una acción instalada pasan al modelo conversacional; este puede ayudar a entender la intención y utilizar las herramientas registradas cuando el formato del modelo lo permita. No se afirma que cualquier petición arbitraria pueda ser ejecutada.

## Permisos y límites de Android

Al iniciar y después de actualizar, Jarvis revisa los permisos normales que falten y puede solicitarlos individualmente: micrófono, cámara para la linterna, contactos, llamadas, SMS y notificaciones. Solo se piden los permisos relacionados con funciones implementadas.

Android no permite que una aplicación se conceda a sí misma permisos especiales. La persona debe activar manualmente desde Ajustes los accesos que quiera usar, por ejemplo:

- **Accesibilidad:** leer pantallas, pulsar controles y escribir en otras aplicaciones.
- **Mostrar sobre otras aplicaciones:** puede ayudar con algunas aperturas y superposiciones.
- **Modificar ajustes del sistema:** necesario para controlar el brillo.
- **Exención de ahorro de batería:** ayuda a reducir la suspensión del servicio, especialmente en algunas capas de Android.

El sistema operativo y cada aplicación conservan el control de sus pantallas, datos y acciones protegidas. Android puede impedir que un servicio en segundo plano abra directamente otra aplicación; cuando eso ocurra, Jarvis puede dejar una notificación para que la persona toque y continúe. Algunas funciones solo abren Ajustes o una pantalla nativa, no cambian silenciosamente una configuración protegida. Wi-Fi y Bluetooth, por ejemplo, pueden requerir que la persona termine el cambio en Ajustes.

La escucha empieza después de abrir la aplicación, conceder el micrófono y pulsar «Iniciar Jarvis». Android y el fabricante pueden suspender servicios en segundo plano; no se promete escucha permanente en todos los teléfonos.

## Reconocimiento del habla frente a biometría

Jarvis sigue necesitando reconocimiento del habla para entender las palabras pronunciadas. Eso es ASR y se ejecuta localmente. Se eliminó la identificación biométrica del hablante: no se compara la voz con una huella ni se exige grabar muestras para inscribirse.

## Privacidad y almacenamiento

- El ASR y el cerebro conversacional trabajan localmente después de instalar y descargar el modelo.
- Las conversaciones no se envían a una API de IA remota.
- No se guardan muestras biométricas de voz.
- La descarga inicial del modelo y las búsquedas externas solicitadas sí usan internet.
- La Accesibilidad permite acceder al contenido visible de otras aplicaciones; solo debe activarse si la persona desea esas funciones.

## Compilación y actualizaciones

GitHub Actions extrae el proyecto Android base, descarga el modelo de ASR español, aplica los generadores de código y compila APK de depuración y de lanzamiento firmada. La firma estable permite actualizar la aplicación existente sin desinstalarla. Los cambios del motor, permisos o capacidades Android requieren una nueva APK.
