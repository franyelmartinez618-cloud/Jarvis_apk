"""Replace the legacy third-party LLM injection with the first-party JARVIS runtime."""
from pathlib import Path
import re
import shutil
import sys

repo = Path(__file__).resolve().parents[1]
root = Path(sys.argv[1])
service_path = root / "app/src/main/java/com/jarvis/personal/JarvisService.kt"
main_path = root / "app/src/main/java/com/jarvis/personal/MainActivity.kt"
service = service_path.read_text(encoding="utf-8")
main = main_path.read_text(encoding="utf-8")

# The generator that adds Android phone tools historically injected Qwen/LiteRT-LM.
# Strip every inference dependency and replace only the conversational entry points.
service = re.sub(r"(?m)^import com\.google\.ai\.edge\.litertlm\.\*\s*\n", "", service)
service = re.sub(r"(?m)^import kotlinx\.coroutines\.flow\.collect\s*\n", "", service)
service = re.sub(r"(?m)^import kotlinx\.coroutines\.sync\.(?:Mutex|withLock)\s*\n", "", service)
service = re.sub(r"(?m)^.*private const val BRAIN_URL.*\n", "", service)
service = re.sub(r"(?m)^.*private const val BRAIN_SHA256.*\n", "", service)
for pattern in [
    r"(?m)^\s*@Volatile private var brainLoading = false\s*\n",
    r"(?m)^\s*@Volatile private var brainEngine: Engine\? = null\s*\n",
    r"(?m)^\s*@Volatile private var brainConversation: Conversation\? = null\s*\n",
    r"(?m)^\s*private val brainMutex = Mutex\(\)\s*\n",
]:
    service = re.sub(pattern, "", service)
service = service.replace(
    "        try { brainConversation?.close() } catch (_: Exception) {}\n"
    "        try { brainEngine?.close() } catch (_: Exception) {}\n",
    ""
)

dialogue_marker = "    private val dialogueHistory = ArrayList<Pair<String, String>>()\n"
if dialogue_marker not in service:
    raise SystemExit("No se encontró el historial de diálogo para integrar el motor propio.")
if "private var nativeBrain: JarvisNativeBrain?" not in service:
    service = service.replace(
        dialogue_marker,
        dialogue_marker + "    @Volatile private var nativeBrain: JarvisNativeBrain? = null\n",
        1
    )

start = service.find("    private fun initializeLocalBrain() {")
end = service.find("    private fun spanishNumber(", start)
if start < 0 or end < 0:
    raise SystemExit("No se encontró el bloque de carga Qwen para sustituir.")
native_init = '''    private fun initializeLocalBrain() {
        scope.launch {
            try {
                updateNotification("Iniciando motor propio JARVIS")
                val instance = withContext(Dispatchers.IO) {
                    JarvisNativeBrain(this@JarvisService)
                }
                nativeBrain = instance
                updateNotification(instance.status())
                Log.i(TAG, instance.status())
            } catch (e: Exception) {
                Log.e(TAG, "No se pudo iniciar el motor propio de JARVIS", e)
                updateNotification("Motor propio disponible con funciones locales; revisa el registro")
            }
        }
    }

'''
service = service[:start] + native_init + service[end:]

start = service.find("    private suspend fun respondNaturally(input: String) {")
end = service.find("    private fun beep() {", start)
if start < 0 or end < 0:
    raise SystemExit("No se encontró el método de respuesta para conectar el cerebro propio.")
native_reply = '''    private suspend fun respondNaturally(input: String) {
        if (runNaturalPhoneAction(input)) return
        val brain = nativeBrain
        if (brain == null) {
            speak("El núcleo propio se está iniciando. Repite la pregunta en un momento.")
            return
        }
        try {
            val answer = withContext(Dispatchers.Default) {
                brain.reply(input, dialogueHistory)
            }.trim().ifBlank {
                "Te escuché, pero todavía no tengo una respuesta entrenada para eso."
            }
            dialogueHistory.add("user" to input.take(500))
            dialogueHistory.add("jarvis" to answer.take(700))
            while (dialogueHistory.size > 12) dialogueHistory.removeAt(0)
            speak(answer.take(1600))
        } catch (e: Exception) {
            Log.e(TAG, "Falló el motor neuronal propio de JARVIS", e)
            speak("No pude procesar esa pregunta con el motor local. Puedes repetirla.")
        }
    }

'''
service = service[:start] + native_reply + service[end:]
service = service.replace("Cerebro local · Qwen3", "Motor neuronal propio JARVIS")
service = service.replace("Cerebro local Qwen3 inicializado correctamente", "Motor neuronal propio JARVIS inicializado correctamente")
for forbidden in ["brainConversation", "brainEngine", "EngineConfig", "sendMessageAsync", "Qwen3", "litertlm"]:
    if forbidden.lower() in service.lower():
        raise SystemExit("Quedó una referencia del motor externo en JarvisService.kt: " + forbidden)
if "JarvisNativeBrain" not in service or "runNaturalPhoneAction(input)" not in service:
    raise SystemExit("El runtime propio o el enrutador de acciones no quedó conectado.")
service_path.write_text(service, encoding="utf-8")

# Remove the model tool adapter: native intent routing calls the Android capabilities directly.
tools_path = root / "app/src/main/java/com/jarvis/personal/JarvisTools.kt"
if tools_path.exists():
    tools_path.unlink()

# Remove LiteRT-LM from Gradle. No third-party LLM runtime is part of the APK.
for gradle_path in [root / "app/build.gradle.kts", root / "app/build.gradle"]:
    if gradle_path.exists():
        text = gradle_path.read_text(encoding="utf-8")
        text = re.sub(
            r'(?m)^\s*implementation\("com\.google\.ai\.edge\.litertlm:litertlm-android:[^"]+"\)\s*\n',
            "",
            text
        )
        gradle_path.write_text(text, encoding="utf-8")

# Remove any legacy first-run download gate, regardless of indentation or copy version.
first = main.find("val brainFile = File(noBackupFilesDir")
if first >= 0:
    finish = main.find("val serviceIntent = Intent(this, JarvisService::class.java)", first)
    if finish >= 0:
        line_start = main.rfind("\n", 0, first) + 1
        main = main[:line_start] + main[finish:]
# Drop any leftover file-gating declarations in the upgrade path.
main = re.sub(r"(?m)^\s*val brainFile = File\(noBackupFilesDir,.*\n", "", main)
main = re.sub(
    r"(?m)^\s*val modelAccepted = brainFile\.exists\(\) \|\| statePrefs\.getBoolean\(.*\n",
    "                    val modelAccepted = true\n",
    main
)
main = re.sub(r"(?i)qwen[0-9-]*", "motor neuronal propio", main)
main = re.sub(r"(?i)litertlm", "", main)
main = main.replace("Aprox. 932 MB, una sola vez", "sin descargar un modelo externo")
main = main.replace("El modelo se descarga una vez al teléfono.", "Motor propio local, sin modelo lingüístico externo.")
main = re.sub(r"(?m)^import java\.io\.File\s*\n", "", main) if "File(" not in main else main
if "Qwen" in main or "litertlm" in main:
    raise SystemExit("Quedó una referencia Qwen/LiteRT en MainActivity.kt:\n" + "\n".join(line for line in main.splitlines() if re.search(r"qwen|litertlm", line, re.I)))
if "private fun startJarvis()" in main and "val serviceIntent = Intent(this, JarvisService::class.java)" not in main:
    raise SystemExit("Se perdió el inicio del servicio Android.")
main_path.write_text(main, encoding="utf-8")

# Remove native-library declarations that were required only by the old GPU LLM runtime.
manifest_path = root / "app/src/main/AndroidManifest.xml"
if manifest_path.exists():
    manifest = manifest_path.read_text(encoding="utf-8")
    manifest = re.sub(r"(?m)^\s*<uses-native-library android:name=\"lib(?:vndksupport|OpenCL)\.so\" android:required=\"false\" />\s*\n", "", manifest)
    manifest_path.write_text(manifest, encoding="utf-8")

# Install our self-written inference runtime into the Android app.
source = repo / "brain/android/JarvisNativeBrain.kt"
if not source.is_file():
    raise SystemExit("Falta brain/android/JarvisNativeBrain.kt.")
destination = root / "app/src/main/java/com/jarvis/personal/JarvisNativeBrain.kt"
destination.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(source, destination)

# A trained checkpoint is optional until the first from-scratch training run is completed.
assets = root / "app/src/main/assets"
assets.mkdir(parents=True, exist_ok=True)
seed_corpus = repo / "data/seed/jarvis_core.jsonl"
if not seed_corpus.is_file():
    raise SystemExit("Falta el corpus semilla original de JARVIS.")
shutil.copyfile(seed_corpus, assets / "jarvis-knowledge.jsonl")

checkpoint = repo / "brain/artifacts/jarvis-brain.bin"
target = assets / "jarvis-brain.bin"
if checkpoint.is_file():
    shutil.copyfile(checkpoint, target)
elif target.exists():
    target.unlink()

# Final hard gate: no third-party LLM package, URL, or runtime call can ship in this APK.
for path in (root / "app/src/main").rglob("*"):
    if not path.is_file() or path.suffix not in {".kt", ".xml"}:
        continue
    content = path.read_text(encoding="utf-8", errors="ignore").lower()
    forbidden = ("qwen", "litertlm", "com.google.ai.edge.litertlm", "sendmessageasync")
    if any(item in content for item in forbidden):
        raise SystemExit("Se detectó un motor lingüístico externo en el código Android: " + str(path))

print("JARVIS Android: motor conversacional propio conectado; Qwen/LiteRT y sus descargas eliminados.")
