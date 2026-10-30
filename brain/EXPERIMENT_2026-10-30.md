# Experimento de entrenamiento JARVIS · 2026-10-30

## Ejecución

- Run de GitHub Actions: [41011639767](https://github.com/franyelmartinez618-cloud/Jarvis_apk/actions/runs/41011639767)
- Inicialización: pesos aleatorios, semilla reproducible `20261030`.
- Arquitectura: Transformer causal propio, 2 capas, ancho 64, 4 cabezas, contexto 128, vocabulario de 260 IDs byte-level.
- Corpus: 48 ejemplos originales redactados para identidad, capacidades Android, permisos, privacidad y comportamiento.
- Entrenamiento: 2.500 pasos; PyTorch CPU.
- Mejor pérdida de validación registrada: `1.7612346212069194`.
- Exportación: correcta a `JARVIS01`; SHA-256 `2f76bae29af0c5efddde4ae81cb1f38b5a348af1a40c19a33e6503c7b7294e6d`.
- Artefacto de entrenamiento: `jarvis-brain-training-experiment` (checkpoint PyTorch, binario Android y metadatos).

## Evaluación cualitativa

Se probaron preguntas sobre identidad, funciones del teléfono y cómo actuar cuando no sabe. La generación produjo fragmentos incoherentes, repetición y palabras mal formadas. Una pérdida de validación reducida sobre un corpus tan pequeño no demuestra competencia conversacional ni conocimiento general.

## Decisión

**No integrar este checkpoint en la APK.** La APK mantiene el runtime Kotlin propio y el índice de conocimiento de los 48 ejemplos, y no carga pesos conversacionales de terceros. El checkpoint queda como artefacto experimental, fuera de la instalación.

## Próxima iteración necesaria

1. Ampliar el corpus con materiales originales o expresamente licenciados, con procedencia registrada; incluir varios dominios, estilos de pregunta y respuestas extensas.
2. Mejorar la tokenización para reducir la cantidad de bytes por contexto y ampliar contexto/capacidad del modelo.
3. Entrenar con aceleración GPU y medir pérdida por dominio, generación real, repetición, factualidad y rechazo a instrucciones inseguras.
4. Exportar y volver a probar en el runtime Android. Solo integrar los pesos cuando las respuestas pasen una batería automática y una revisión cualitativa.

## Componentes separados

Vosk sigue incluido solo para transcribir audio español a texto. Es un modelo acústico preentrenado de terceros, no el cerebro conversacional. Si el requisito final también prohíbe modelos externos de reconocimiento de voz, esa pieza deberá sustituirse en otro proyecto de entrenamiento independiente.
