# J.A.R.V.I.S. — asistente personal para Android

Proyecto Android existente, conservando identidad, paquete y firma de actualización. La versión instalada actualmente usa un motor conversacional local de terceros; el objetivo aprobado ahora es sustituirlo por un modelo entrenado desde inicialización aleatoria dentro del proyecto.

## Próxima arquitectura
- web/: interfaz PWA que se publica automáticamente con GitHub Pages; la app Android deberá integrar este runtime mediante WebView y puente nativo para que la interfaz web se actualice sin APK.
- brain/: primer decoder Transformer, tokenizador byte-level y entrenamiento desde cero. No contiene ni descarga pesos preentrenados.
- Android: conserva permisos y herramientas nativas. Las acciones sensibles requieren confirmación del usuario.
- Voz: salida objetivo en inglés británico (en-GB), tono calmado y grave. La disponibilidad de una voz masculina depende de las voces instaladas en el motor TTS del dispositivo.

## Estado honesto
El código de arquitectura y entrenamiento es el primer prototipo, no un cerebro ya entrenado. Un checkpoint aleatorio no sabe conversar: requiere un corpus grande, legal y diverso y entrenamiento real con GPU. No se afirma que JARVIS tenga conocimientos ilimitados ni AGI. La interfaz web se publica por workflow al integrarse en main; hasta integrar el WebView en Android, la APK no cambia visualmente.

Consulta brain/README.md para preparar el corpus y entrenar. Consulta data/README.md para las reglas de datos.
