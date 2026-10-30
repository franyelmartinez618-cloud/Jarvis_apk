# Escala objetivo del cerebro JARVIS

## Qué tenemos ahora

- Arquitectura propia causal Transformer.
- Perfil grande intermedio: 12 capas, dimensión 512, contexto 1.024, aproximadamente 38,4 millones de parámetros.
- Tokenizador byte-level de 260 IDs.
- Entrenamiento desde pesos aleatorios, preentrenamiento y ajuste supervisado de instrucciones.
- Runtime Kotlin propio que entiende el formato JARVIS01.
- El currículo actual es un conjunto de arranque: 117 pares originales más 3.000 ejercicios algorítmicos reproducibles. No es una base de conocimiento general de escala mundial.

Este perfil de 38,4 M de parámetros sirve para validar la cadena de entrenamiento e inferencia. No equivale a un asistente general de alta capacidad.

## Tamaño de pesos y almacenamiento

El tamaño del APK no crea inteligencia por sí mismo. Como referencia aproximada:

| Parámetros | FP32 | FP16/BF16 | INT8 | INT4 |
|---:|---:|---:|---:|---:|
| 1.000 millones | 4 GB | 2 GB | 1 GB | 0,5 GB |
| 1.500 millones | 6 GB | 3 GB | 1,5 GB | 0,75 GB |
| 2.000 millones | 8 GB | 4 GB | 2 GB | 1 GB |

Son tamaños teóricos de pesos; el APK añade código y datos, y la inferencia requiere RAM adicional para contexto, cachés y activaciones. El runtime Android actual almacena pesos FP32 y no implementa cuantización INT8/INT4 ni kernels optimizados. Por eso no basta con entrenar 1–2B parámetros: también habría que crear y probar un runtime móvil eficiente.

## Escala de entrenamiento

Una regla de planificación habitual para modelos densos es del orden de 20 tokens de entrenamiento por parámetro, aunque la cifra óptima depende de arquitectura, calidad de datos y objetivo. Un modelo de 1.000 millones de parámetros puede necesitar decenas de miles de millones de tokens para un preentrenamiento competitivo. Los 3.000 ejercicios sintéticos actuales sirven para habilidades matemáticas concretas, no para sustituir ese corpus.

Un entrenamiento de ese tamaño requiere una colección masiva y diversa con derechos documentados, almacenamiento de varios GB o más, GPU(s) con decenas de GB de VRAM, muchas horas o días de cómputo y evaluación continua. Los runners CPU normales de GitHub no proporcionan esa capacidad. El workflow GPU ya está preparado, pero necesita un runner GPU real y el corpus autorizado que exige su control previo.

## Componentes necesarios para acercarse al JARVIS ficticio

1. Preentrenamiento lingüístico y de conocimiento a gran escala, con datos multilingües y dominio técnico.
2. SFT de instrucciones, planificación, uso de herramientas y diálogo de varios turnos.
3. Evaluación humana y automática de factualidad, razonamiento, seguridad, consistencia y resistencia a errores.
4. Memoria local persistente y recuperación documental con procedencia y fecha.
5. Planificador que divida objetivos, ejecute herramientas Android y compruebe cada resultado.
6. Percepción de audio/imagen y síntesis de voz. Si no se acepta ningún modelo externo, también habrá que entrenar desde cero reconocimiento de voz y voz sintética; Vosk sigue siendo hoy el transcriptor separado de la APK.
7. Runtime Android cuantizado y optimizado para el hardware real, con límites térmicos, memoria y batería.

## Política de independencia

El cerebro conversacional, los pesos y el runtime se crean en el proyecto. No se carga un LLM preentrenado ni se consulta una API de IA para responder. Las fuentes de conocimiento externas, cuando se incorporen, serán documentos con licencia registrada, no un cerebro remoto. El navegador puede abrir la web si el usuario lo solicita, pero eso no convierte una búsqueda en conocimiento aprendido por los pesos.

## Criterio para instalar un modelo

Ningún checkpoint se integra automáticamente. Debe superar el conjunto de evaluación, responder de forma coherente, no repetir ni inventar fuentes, respetar reglas de seguridad y funcionar con memoria/latencia aceptables en el teléfono. El tamaño de archivo no sustituye estas pruebas.
