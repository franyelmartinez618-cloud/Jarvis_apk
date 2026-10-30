# JARVIS — asistente de voz local para Android

Jarvis conserva el mismo proyecto Android, paquete, repositorio y firma de actualización. La experiencia objetivo vuelve a ser voz a voz: la persona habla, Jarvis entiende el contenido hablado localmente y responde con audio mediante la síntesis de voz de Android.

## La corrección de voz de esta versión

- Se conserva el micrófono y el reconocimiento local de español (ASR) porque son necesarios para que Jarvis entienda lo que la persona dice.
- Se conserva la respuesta hablada (TTS) de Android: Jarvis no responde como chat escrito.
- El modelo español de Vosk se empaqueta dentro de la APK en `app/src/main/assets/model-es`; el servicio busca exactamente esa carpeta y la copia a almacenamiento interno antes de crear el reconocedor.
- Si Android no puede leer el modelo al iniciar, la pantalla permanece abierta, muestra el estado de arranque y permite volver a intentarlo. No se necesita descargar un segundo modelo después de instalar.
- La pantalla de inicio usa un reactor y paneles dibujados de forma nativa, sin imágenes remotas ni una interfaz de chat.
- Se elimina la verificación biométrica del hablante: ya no se comparan huellas de voz ni se exige grabar dos muestras antes de usar la aplicación.
- Se amplía el turno de escucha para aceptar frases habladas más largas.
- Se amplía la gramática de activación con frases como «Hola Jarvis», «Oye Jarvis», «Jarvis, ¿estás ahí?», «Jarvis, ¿estás despierto?», «Jarvis, ¿estás activo?» y «Jarvis, ¿me escuchas?». La detección se activa cuando el reconocedor local encuentra el nombre «Jarvis» en la frase.
- La pantalla principal conserva un único botón para iniciar o detener el asistente. En la primera instalación, Android solicita los permisos necesarios.
- Se conservan las capacidades nativas de acciones del teléfono y el control opcional de pantalla por Accesibilidad.

## Diferencia importante: reconocer el habla no es reconocer la identidad

Jarvis necesita reconocimiento del habla para convertir lo que se dice en texto que sus órdenes puedan interpretar. Eso es ASR y se ejecuta localmente con Vosk y el modelo español incluido en la compilación.

Lo que se elimina es la biometría de voz: identificar si la persona que habla coincide con una huella grabada anteriormente. Esa verificación era adicional, lenta y no es necesaria para conversar con Jarvis.

La respuesta se produce por síntesis de voz (TextToSpeech) en el dispositivo. El motor de voz de Android puede depender de la voz instalada en el teléfono, pero no requiere una API conversacional ni enviar los mensajes a Gemini, ChatGPT u otro servicio de IA.

## Activación y conversación

La app se abre y se pulsa «INICIAR JARVIS». El servicio de primer plano queda escuchando la palabra de activación con el reconocedor local. Cuando detecta «Jarvis», pasa al ciclo de conversación, interpreta las órdenes, ejecuta las habilidades disponibles y responde por voz.

La gramática ampliada acepta varias expresiones que contienen Jarvis. No promete detectar cualquier frase sin la palabra de activación ni garantiza que un modelo acústico pequeño interprete perfectamente todos los acentos, nombres propios o ruidos.

## Qué puede hacer y qué no se debe prometer

El código incorpora comandos para abrir aplicaciones, consultar contactos, preparar mensajes o llamadas, controlar la pantalla con Accesibilidad y responder a algunas preguntas comunes. Los mensajes y llamadas deben estar sujetos a permisos, confirmaciones y restricciones de Android.

El motor conversacional actual está basado en intenciones y habilidades programadas para este proyecto. **No es todavía una IA general ni un modelo generativo entrenado desde cero.** Por eso, aunque ahora la interacción vuelve a ser por voz, todavía no puede mantener una conversación abierta con la amplitud de Tony Stark/Jarvis o de un modelo conversacional grande.

Una IA generativa verdaderamente propia requiere diseñar y entrenar un modelo con datos, recursos de cómputo, pruebas y ajustes. No se consigue quitando una API o cambiando el reconocimiento. No se añade aquí un modelo conversacional de terceros ni se finge que el motor actual tiene esa capacidad.

## Actualizaciones

Las versiones nativas siguen compilándose y firmándose automáticamente con la identidad de firma estable del repositorio. Los cambios de Kotlin, permisos, audio, accesibilidad o capacidades Android requieren una actualización nativa. Android siempre conserva el control del permiso del micrófono y de la instalación de actualizaciones.

## Privacidad

- El reconocimiento de voz se ejecuta localmente en el dispositivo.
- No se transmiten grabaciones a una API conversacional.
- No se guardan muestras biométricas de voz.
- Las búsquedas externas solo se abren cuando la persona las solicita.
- La lectura y el control de otras aplicaciones requieren habilitar voluntariamente el servicio de Accesibilidad. Esa función puede acceder al contenido visible de la pantalla.

## Compilación

El workflow extrae el proyecto base `jarvis-android.zip`, prepara reconocimiento local en español, aplica las habilidades de la app, elimina el verificador biométrico y la pantalla de inscripción de voz, y compila APK de depuración y de lanzamiento firmado.
