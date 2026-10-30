# JARVIS Core — modelo neuronal propio desde cero

Este directorio define el primer motor entrenable cuyo código, tokenización, arquitectura y pesos iniciales nacen dentro de este proyecto. No descarga Qwen, Llama, Gemma, GPT ni pesos preentrenados. La arquitectura actual es un decoder Transformer causal pequeño y experimental, entrenado con inicialización aleatoria.

## Qué significa desde cero
- Pesos inicializados aleatoriamente por PyTorch.
- Tokenizador UTF-8 byte-level implementado aquí (256 bytes + tokens especiales).
- Bloques Transformer causales implementados en model.py.
- Entrenamiento next-token en train.py, checkpoints propios y generación en generate.py.
- No hay conocimiento previo: el modelo aprende únicamente del corpus que se le proporcione.

El código no equivale a un cerebro ya entrenado. Un modelo inicial aleatorio no sabe conversar. La calidad depende del tamaño, limpieza, diversidad y derechos de uso del corpus, además de GPU y tiempo de entrenamiento. No se declara que exista un checkpoint entrenado hasta que un entrenamiento real lo produzca y pase evaluación.

## Arranque local
Python 3.11+, PyTorch 2.4+ y una GPU NVIDIA recomendada:
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r brain/requirements.txt
python brain/prepare_corpus.py --input data/raw --output data/processed/corpus.txt
python brain/train.py --config brain/config.json
python brain/generate.py --checkpoint checkpoints/jarvis.pt --prompt "Hola, ¿quién eres?"
```

Pon textos propios o con licencia compatible en data/raw (.txt, .md, .jsonl con campo text). El preparador normaliza, elimina duplicados exactos y registra un manifiesto; no descarga ni copia a ciegas corpus con copyright.

## Corpus amplio
Construye un corpus multilingüe y multidominio con material creado por ti, documentación con licencia compatible, datos públicos cuya licencia permita entrenamiento y ejemplos de diálogo redactados y curados. Conserva por fuente URL, autor, licencia y fecha en data/sources.jsonl. No uses datos privados, credenciales, conversaciones de otras personas ni contenido cuya licencia no permita este uso.

## Escala
El config inicial es deliberadamente pequeño para verificar el pipeline. Después de medir memoria, tokens/segundo y pérdida de validación, aumenta capas, ancho, contexto y corpus por etapas. No escales a cientos de miles de millones de parámetros sin infraestructura, datos y evaluación adecuados.

## Voz británica
La voz de salida es TTS, no del modelo lingüístico. La interfaz web solicita en-GB y una voz grave/lenta disponible. Android debe configurar su motor TextToSpeech con Locale.UK y elegir una voz masculina instalada si el motor ofrece una; Android no garantiza que todos los dispositivos tengan la misma voz. No se usa clonación de voces.
