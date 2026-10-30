# JARVIS Core — red neuronal propia desde cero

Este proyecto implementa su propia arquitectura, tokenizador, inicialización aleatoria, entrenamiento, exportador y runtime de inferencia Android. No importa ni reutiliza pesos de modelos lingüísticos preentrenados.

## Arquitectura

- `model.py`: decoder Transformer causal con atención multi-cabeza y MLP.
- `tokenizer.py`: tokenizador UTF-8 byte-level (256 bytes y tokens especiales).
- `train.py`: entrenamiento de predicción del siguiente token desde pesos aleatorios.
- `export_android.py`: serializa los tensores a `JARVIS01`.
- `android/JarvisNativeBrain.kt`: runtime Kotlin que lee ese formato y ejecuta el Transformer en CPU.

El perfil inicial es móvil y deliberadamente pequeño (2 capas, ancho 64, contexto 128). Sirve para validar el ciclo completo, no para competir con modelos grandes ni para afirmar AGI. Los 48 ejemplos de `data/seed/jarvis_core.jsonl` enseñan la identidad y el comportamiento previsto de JARVIS, pero no aportan conocimiento mundial.

## Entrenamiento

Python 3.11+, PyTorch 2.4+ y una GPU NVIDIA recomendada:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r brain/requirements.txt
python brain/prepare_corpus.py --input data/seed --output data/processed/corpus.txt
python brain/train.py --config brain/config.json --data data/processed/corpus.txt --out checkpoints/jarvis.pt
python brain/generate.py --checkpoint checkpoints/jarvis.pt --prompt "### Usuario:\nHola.\n### JARVIS:"
python brain/export_android.py --checkpoint checkpoints/jarvis.pt --output brain/artifacts/jarvis-brain.bin
```

No se ha ejecutado ni validado todavía un entrenamiento general. Amplía el corpus con material propio o fuentes cuya licencia permita explícitamente entrenamiento. Conserva procedencia y fecha. No uses datos privados, credenciales o contenido sin autorización.

## Integración en APK

El workflow copia `brain/artifacts/jarvis-brain.bin` a los assets Android cuando el archivo existe. Sin ese archivo, JARVIS inicia su núcleo local de capacidades y un índice pequeño de conocimiento, informa que el checkpoint está pendiente y mantiene el enrutador de comandos Android. No ejecuta pesos aleatorios como si fueran una IA entrenada.

Tras entrenar y evaluar un checkpoint, vuelve a compilar Android. El runtime verifica la cabecera, vocabulario, dimensiones y pesos antes de inferir. El formato no requiere LiteRT, un SDK de terceros ni un servidor conversacional.

## Voz

La transcripción de voz es un componente separado del razonamiento. El reconocedor del APK convierte audio en texto. La síntesis de voz también es independiente: Android usa el motor TTS disponible y debe seleccionar una voz en-GB adecuada si el dispositivo la ofrece.
