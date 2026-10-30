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


## Resultado del primer experimento
El entrenamiento del 30-10-2026 produjo un checkpoint propio (2.500 pasos, val_loss 1.7612) y lo exportó correctamente. En tres preguntas de prueba la generación fue incoherente y repetitiva. No se debe copiar ese binario a `brain/artifacts/` ni distribuirlo en la APK hasta mejorar corpus, tokenizer y capacidad y aprobar una evaluación. Consulta `EXPERIMENT_2026-10-30.md`.

## Perfiles de entrenamiento

- `config.json`: perfil de prueba pequeño para verificar el ciclo completo; no sirve como cerebro general.
- `config-mobile.json`: 6 capas, ancho 256, contexto 512. Perfil de investigación para una futura APK, sujeto a pruebas de latencia y memoria.
- `config-large.json`: 12 capas, ancho 512, contexto 1024, acumulación de gradiente y precisión BF16. Aproximadamente 38 millones de parámetros; necesita GPU CUDA con memoria suficiente y un corpus de al menos 1,1 GB antes de iniciar. No se ejecuta en el runner CPU normal.

El entrenamiento ahora separa documentos completos entre entrenamiento y validación, registra pérdida/perplejidad, aplica calentamiento y decaimiento coseno de la tasa de aprendizaje, acumula gradientes y guarda checkpoints reanudables. La validación nunca debe contener fragmentos de los mismos documentos que el entrenamiento.

## Corpus y procedencia

El corpus semilla contiene ejemplos originales de identidad, seguridad, Android, ciencia, matemáticas, programación y razonamiento. Se amplió con 69 pares curriculares originales, pero continúa siendo demasiado pequeño para un modelo general.

Los datos externos deben ir en `data/raw/` y declararse archivo por archivo en `data/raw/SOURCES.json`. El preparador rechaza licencias no autorizadas, uso comercial no permitido y fuentes sin evidencia de atribución o permiso. La lista permitida por defecto es CC0-1.0, dominio público justificado, CC-BY-4.0 con atribución, contenido original del propietario o permiso explícito.

No se incorporan automáticamente textos de OpenStax porque su licencia actual CC BY-NC-SA excluye usos comerciales y la propia organización solicita permiso para proyectos de IA. Tampoco se incluye Wikipedia por defecto: el texto exige atribución y ShareAlike CC BY-SA. Esas fuentes solo se considerarían tras revisar y aceptar sus obligaciones. El registro de fuentes está en `data/raw/README.md`.

## Entrenamiento grande

El workflow `.github/workflows/train-jarvis-brain-gpu.yml` está preparado para una máquina Linux con GPU NVIDIA registrada como runner propio de GitHub Actions con etiquetas `self-hosted, linux, x64, gpu`. El entorno de esta sesión y los runners estándar de GitHub disponibles aquí no proporcionan GPU CUDA. No se puede ejecutar honestamente el perfil de 12 capas en un runner CPU pequeño ni afirmar que ya se entrenó a escala grande.

El workflow GPU es manual y exige que el corpus autorizado alcance el tamaño mínimo. Los checkpoints se conservan como artefactos separados y no se integran automáticamente en la APK. Primero deben pasar evaluación cualitativa, validación de seguridad y pruebas de rendimiento en Android.



## Segunda etapa: ajuste a instrucciones

Después del preentrenamiento autoregresivo, `train_sft.py` realiza ajuste supervisado con pares `### Usuario:` / `### JARVIS:`. La pérdida se calcula sobre la respuesta del asistente y el token EOS; el texto de la pregunta queda enmascarado como objetivo. Esto enseña formato de conversación y seguimiento de instrucciones, pero la calidad sigue limitada por el tamaño y diversidad del conjunto de ejemplos. El workflow exporta el checkpoint SFT, no el checkpoint base.
