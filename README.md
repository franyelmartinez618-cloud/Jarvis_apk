# Jarvis — asistente personal para Android

Este repositorio contiene el proyecto de Jarvis para uso personal en un Android (objetivo inicial: Redmi Note 13).

## Qué incluye la versión base

- Activación por voz con la frase **“Jarvis activate”** usando el modelo local Vosk.
- Respuesta hablada con el motor de voz de Android.
- Órdenes básicas para llamadas, SMS con confirmación, abrir aplicaciones, hora y fecha.
- WhatsApp se abre con el mensaje preparado; por seguridad, el usuario toca **Enviar**.
- Selección por voz si hay varios contactos coincidentes.

Esta versión base todavía no incluye conversación abierta con IA ni recordatorios inteligentes. Esa será la siguiente fase, después de validar una instalación que compile y se ejecute correctamente en el teléfono.

## Compilación automática

El flujo de GitHub Actions toma el archivo `jarvis-android.zip`, descarga el modelo de voz e intenta crear el APK. Cuando la ejecución termina correctamente:

1. Abre **Actions**.
2. Selecciona la ejecución verde **Construir APK de Jarvis**.
3. En **Artifacts**, descarga `jarvis-apk`.
4. Dentro del ZIP descargado está `app-debug.apk`.

No hace falta Android Studio para este flujo.

## Privacidad y límites

- No agregues claves API, contraseñas ni datos personales al repositorio.
- La detección de la frase de activación usa Vosk local; el reconocimiento de las órdenes usa el servicio de voz disponible en Android y podría necesitar internet.
- WhatsApp no se envía automáticamente: la app abre el chat y tú confirmas el envío.
- Las llamadas y los SMS requieren permisos de Android y una confirmación por voz.
- Un APK compilado no equivale a una prueba real; se debe probar en un teléfono antes de confiar en la escucha continua o las acciones.

## Estado

El código fuente original está guardado en `jarvis-android.zip`. La automatización se ha simplificado para compilar directamente desde el archivo, sin cambiar el repositorio ni crear commits automáticamente durante la compilación.
