# J.A.R.V.I.S. — asistente personal para Android

Proyecto Android existente. Se conserva el paquete de la aplicación, el flujo de firma y la ruta de actualización.

## Trabajo de sustitución del cerebro

La versión estable que estaba publicada desde `main` (v112) todavía fue construida con el motor anterior. Esta rama de trabajo elimina de la APK el motor conversacional de terceros y conecta un runtime Android propio, escrito en Kotlin, que carga exclusivamente checkpoints creados por el entrenamiento de este repositorio.

- `brain/model.py`: Transformer causal propio, con pesos inicializados aleatoriamente.
- `brain/tokenizer.py`: tokenizador propio byte-level UTF-8.
- `brain/train.py`: entrenamiento next-token desde cero.
- `brain/export_android.py`: exportación de pesos al formato binario versionado `JARVIS01`.
- `brain/android/JarvisNativeBrain.kt`: inferencia Kotlin propia, sin LiteRT ni SDK de modelos externos.
- `data/seed/jarvis_core.jsonl`: 48 ejemplos originales sobre identidad, funciones Android, permisos y reglas de seguridad del proyecto.

El reconocedor Vosk se mantiene únicamente como componente separado de transcripción de voz a texto; no genera respuestas ni decide acciones. El razonamiento conversacional no depende de él.

## Estado real del cerebro

El runtime propio y el pipeline de entrenamiento/exportación están creados. **Todavía no existe un checkpoint neuronal entrenado**. Sin checkpoint, Android utiliza el índice local de conocimiento del proyecto y el enrutador de órdenes del teléfono; no presenta la red aleatoria como si supiera conversar. Los 48 ejemplos semilla sirven para enseñar identidad y capacidades, pero no constituyen conocimiento general.

Para el primer entrenamiento:
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r brain/requirements.txt
python brain/prepare_corpus.py --input data/seed --output data/processed/corpus.txt
python brain/train.py --config brain/config.json --data data/processed/corpus.txt --out checkpoints/jarvis.pt
python brain/export_android.py --checkpoint checkpoints/jarvis.pt --output brain/artifacts/jarvis-brain.bin
```

Después de revisar métricas y respuestas, el archivo `brain/artifacts/jarvis-brain.bin` se incluye en la siguiente compilación Android. Para conocimiento amplio se deben añadir fuentes legales, multilingües y multidominio, registrar su procedencia y ampliar la evaluación.

## Android y permisos

Las acciones del teléfono siguen separadas del texto generado. Android determina qué permisos están concedidos. Llamadas y mensajes requieren permisos y confirmación; Accesibilidad, mostrar sobre otras aplicaciones y modificar ajustes necesitan activación en Ajustes del sistema. No se afirma que JARVIS pueda concederse esos permisos a sí mismo.

## Voz e interfaz

La voz objetivo es masculina británica, calmada y grave (en-GB), si el sintetizador instalado ofrece una voz adecuada. Voz a texto, razonamiento neuronal y texto a voz son componentes separados. La PWA de `web/` es una interfaz adicional; falta integrar su WebView nativo para actualizarla sin reinstalar la APK.

No se declara AGI, conocimiento ilimitado ni control total del dispositivo. La publicación de esta rama y su APK firmada requieren que la compilación Android pase y que se publique desde `main` usando la firma estable.


## Primer entrenamiento propio (2026-10-30)
Se completó un experimento desde pesos aleatorios: 2.500 pasos sobre 48 ejemplos originales, pérdida de validación 1.7612 y exportación `JARVIS01` correcta. La prueba cualitativa produjo respuestas incoherentes, por lo que ese checkpoint NO se incluye en la APK. El detalle y las decisiones están en [brain/EXPERIMENT_2026-10-30.md](brain/EXPERIMENT_2026-10-30.md). La APK de la rama usa el runtime propio y el índice semilla, sin modelo conversacional externo.



## Escalado del cerebro propio (30-10-2026)
- Se amplió el corpus original con 69 ejemplos curriculares adicionales de ciencia, matemáticas, informática, seguridad y planificación.
- El entrenamiento ahora separa documentos completos para validación, aprende tokens BOS/EOS, acumula gradientes, usa calentamiento y decaimiento coseno, registra perplejidad y guarda checkpoints reanudables.
- Se añadieron perfiles de investigación móvil (6 capas/256) y grande (12 capas/512/contexto 1024), además de un workflow GPU específico.
- El perfil grande requiere al menos 1,1 GB de corpus autorizado y un runner Linux con GPU NVIDIA. Los runners CPU de GitHub no pueden entrenarlo a escala grande.
- Los archivos externos requieren registro individual de licencia, autorización de entrenamiento y uso comercial. No se incorporan fuentes NC o SA automáticamente.
- El entrenamiento de prueba del corpus semilla se ejecuta automáticamente en Actions. Su checkpoint no se integra en la APK sin evaluación cualitativa satisfactoria.

Consulta [brain/README.md](brain/README.md) y [data/raw/README.md](data/raw/README.md) para los requisitos y el procedimiento.
