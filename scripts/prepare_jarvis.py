from pathlib import Path
import re
import sys

root = Path(sys.argv[1])

def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit("No se encontró el bloque esperado: " + label)
    return text.replace(old, new, 1)

# ── Servicio: reconocimiento offline y habilidades locales.
service_path = root / "app/src/main/java/com/jarvis/personal/JarvisService.kt"
s = service_path.read_text(encoding="utf-8")
s = s.replace("import android.media.AudioManager\n", "import android.media.AudioManager\nimport android.media.AudioFormat\nimport android.media.AudioRecord\nimport android.media.MediaRecorder\n", 1)
s = s.replace("import org.vosk.LibVosk\n", "import org.json.JSONObject\nimport org.vosk.LibVosk\nimport org.vosk.Recognizer\n", 1)
s = s.replace("import java.io.FileOutputStream\n", "import java.io.FileOutputStream\nimport java.net.URLEncoder\n", 1)

# Ensure the imports used by the local Vosk microphone recognizer exist even if the ZIP changes import order.
required_imports = [
    "import android.media.AudioFormat",
    "import android.media.AudioRecord",
    "import android.media.MediaRecorder",
    "import org.json.JSONObject",
    "import org.vosk.Recognizer",
    "import java.net.URLEncoder",
]
package_line = "package com.jarvis.personal\n"
if package_line not in s:
    raise SystemExit("No se encontró el paquete Java esperado en JarvisService.kt")
for required_import in required_imports:
    if required_import not in s:
        s = s.replace(package_line, package_line + required_import + chr(10), 1)

s = replace_once(s, '        const val PREF_COUNTRY = "country_code"\n', '        const val PREF_COUNTRY = "country_code"\n', "código de país")
s = replace_once(s, "    private var busy = false\n", "    private var busy = false\n    private val dialogueHistory = ArrayList<Pair<String, String>>()\n    private var ownerSessionUntilMs = 0L\n", "sesión local y verificación de voz")

conversation = r'''    /** Una activación abre varios turnos; no exige repetir la frase en cada orden. */
    private suspend fun conversation() {
        if (!OwnerVoiceVerifier.isEnrolled(this)) {
            updateNotification("Configura tu voz en Jarvis antes de usar la escucha personalizada")
            return
        }
        updateNotification("Verificando la voz del propietario")
        delay(200)
        while (running) {
            val heard = listen()
            if (heard.isNullOrBlank()) {
                // Silence, unrelated media, or an unverified speaker must never close the owner session
                // or make Jarvis speak. Keep listening until the owner says the deactivation command.
                delay(150)
                continue
            }
            val clean = heard.trim()
            Log.d(TAG, "Orden autorizada por voz: " + clean)
            updateNotification("Conversación activa: orden de voz autorizada")
            val command = Parser.parse(clean)
            handle(command)
            if (command == Cmd.Cancel) break
            delay(250)
        }
    }

    private suspend fun handle(cmd: Cmd) {
        when (cmd) {
            is Cmd.Call -> doCall(cmd.target)
            is Cmd.Message -> doMessage(cmd)
            is Cmd.OpenApp -> doOpenApp(cmd.name)
            Cmd.Time -> speak(timeText())
            Cmd.DateToday -> speak(dateText())
            Cmd.Cancel -> speak("Está bien.")
            is Cmd.Unknown -> respondNaturally(cmd.raw)
        }
    }

'''
s, count = re.subn(r'(?ms)^    private suspend fun conversation\(\) \{.*?^    private suspend fun handle\(cmd: Cmd\) \{.*?^    \}\n', lambda _: conversation, s, count=1)
if count != 1:
    raise SystemExit("No se pudo cambiar el flujo de conversación")

s = s.replace(
'''        if (!Settings.canDrawOverlays(this)) {
            speak("Para abrir WhatsApp desde segundo plano necesito el permiso de mostrar sobre otras apps.")
            return
        }''',
'''        if (!Settings.canDrawOverlays(this)) {
            speak("Android bloquea abrir WhatsApp por voz cuando Jarvis está en segundo plano. Activa Mostrar sobre otras apps en los permisos de Jarvis.")
            return
        }''', 1)

open_app = r'''    private suspend fun doOpenApp(name: String) {
        val pm = packageManager
        val launcher = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val q = strip(name).trim().removePrefix("la app ").removePrefix("aplicacion de ").trim()
        if (q.isBlank()) { speak("Dime qué aplicación quieres abrir."); return }
        val activities = pm.queryIntentActivities(launcher, 0)
        val match = activities.sortedBy { info ->
            val label = strip(info.loadLabel(pm).toString()).trim()
            when {
                label == q -> 0
                label.startsWith(q) -> 1
                label.contains(q) -> 2
                q.contains(label) -> 3
                else -> 10
            }
        }.firstOrNull { info ->
            val label = strip(info.loadLabel(pm).toString()).trim()
            label == q || label.startsWith(q) || label.contains(q) || q.contains(label)
        }
        if (match == null) {
            speak("No encontré una aplicación llamada " + name + ". Usa el nombre que aparece debajo de su icono.")
            return
        }
        // Android limita abrir actividades desde un servicio en segundo plano.
        if (!Settings.canDrawOverlays(this)) {
            speak("Para abrir aplicaciones por voz con Jarvis en segundo plano, Android exige activar Mostrar sobre otras apps en los permisos.")
            return
        }
        val intent = pm.getLaunchIntentForPackage(match.activityInfo.packageName)
        if (intent == null) { speak("Android no ofrece un acceso directo para abrir " + name + "."); return }
        try {
            startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            speak("Abriendo " + match.loadLabel(pm) + ".")
        } catch (e: Exception) {
            Log.e(TAG, "abrir app falló", e)
            speak("Android bloqueó la apertura de " + name + ". Abre Jarvis en pantalla y vuelve a intentarlo.")
        }
    }

'''
s, count = re.subn(r'(?ms)^    private suspend fun doOpenApp\(name: String\) \{.*?^    private fun timeText\(\): String \{', lambda _: open_app + '    private fun timeText(): String {', s, count=1)
if count != 1:
    raise SystemExit("No se pudo actualizar el buscador de aplicaciones")

voice_and_ai = r'''    /** Reconoce las órdenes directamente con Vosk y el modelo español incluido. */
    private suspend fun listen(): String? {
        val localModel = model ?: return null
        return withContext(Dispatchers.IO) {
            var record: AudioRecord? = null
            var recognizer: Recognizer? = null
            try {
                val sampleRate = 16000
                val minBuffer = AudioRecord.getMinBufferSize(
                    sampleRate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT
                )
                if (minBuffer <= 0) return@withContext null
                record = AudioRecord(
                    MediaRecorder.AudioSource.MIC, sampleRate,
                    AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT,
                    maxOf(minBuffer, sampleRate * 2)
                )
                if (record.state != AudioRecord.STATE_INITIALIZED) return@withContext null
                recognizer = Recognizer(localModel, sampleRate.toFloat())
                record.startRecording()
                val buffer = ShortArray(4000)
                val capturedAudio = ArrayList<Float>(sampleRate * 6)
                val started = SystemClock.elapsedRealtime()
                while (SystemClock.elapsedRealtime() - started < 12_000 && running) {
                    val count = record.read(buffer, 0, buffer.size)
                    if (count <= 0) { delay(20); continue }
                    for (index in 0 until count) capturedAudio.add(buffer[index] / 32768.0f)
                    if (recognizer.acceptWaveForm(buffer, count)) {
                        val spoken = JSONObject(recognizer.getResult()).optString("text").trim()
                        if (spoken.isNotBlank()) {
                            val authorized = verifiedVoice(capturedAudio)
                            if (authorized) return@withContext spoken
                            Log.i(TAG, "Voz no autorizada; la orden no se ejecutará")
                            return@withContext null
                        }
                    }
                }
                val finalText = JSONObject(recognizer.getFinalResult()).optString("text").trim()
                if (finalText.isBlank()) null else if (
                    verifiedVoice(capturedAudio)
                ) finalText else {
                    Log.i(TAG, "Voz final no autorizada; no responderé")
                    null
                }
            } catch (e: Exception) {
                Log.e(TAG, "El reconocimiento local falló", e)
                null
            } finally {
                try { if (record?.recordingState == AudioRecord.RECORDSTATE_RECORDING) record?.stop() } catch (_: Exception) {}
                try { record?.release() } catch (_: Exception) {}
                try { recognizer?.close() } catch (_: Exception) {}
            }
        }
    }

    /** Motor local propio basado en intenciones; no llama a una IA remota. */
    private fun verifiedVoice(audio: List<Float>): Boolean {
        val now = SystemClock.elapsedRealtime()
        if (now < ownerSessionUntilMs) return true
        val recent = audio.takeLast(16000 * 3).toFloatArray()
        val matched = OwnerVoiceVerifier.matches(this, recent)
        if (matched) ownerSessionUntilMs = now + 90_000L
        return matched
    }

    private suspend fun respondNaturally(input: String) {
        val normalized = strip(input).trim()
        val answer = localReply(normalized)
        dialogueHistory.add("user" to input.take(180))
        dialogueHistory.add("jarvis" to answer.take(240))
        while (dialogueHistory.size > 8) dialogueHistory.removeAt(0)
        speak(answer)
    }

    private fun localReply(text: String): String {
        return when {
            text.isBlank() -> "Te escucho. Dime qué necesitas."
            Regex("\\b(hola|buenas|buenos dias|buenas tardes|buenas noches)\\b").containsMatchIn(text) ->
                "Hola. Soy Jarvis. Estoy trabajando localmente en este teléfono. ¿Qué hacemos?"
            Regex("\\b(como estas|que tal estas|estas bien)\\b").containsMatchIn(text) ->
                "Estoy activo y listo para recibir órdenes."
            Regex("\\b(quien eres|que eres|como te llamas)\\b").containsMatchIn(text) ->
                "Soy Jarvis, tu asistente local. No envío tu conversación a una IA remota. Ejecuto las habilidades instaladas en esta aplicación."
            Regex("\\b(ayuda|que puedes hacer|que sabes hacer|comandos)\\b").containsMatchIn(text) ->
                "Puedo abrir aplicaciones, decir la hora y la fecha, buscar contactos, preparar mensajes y llamadas con confirmación, y controlar elementos visibles si activas Accesibilidad."
            Regex("\\b(estas escuchando|jarvis estas activo|estas activo)\\b").containsMatchIn(text) ->
                "Sí. Estoy activo en este dispositivo."
            Regex("\\b(privacidad|internet|conectado a una ia|ia remota|gemini|qwen)\\b").containsMatchIn(text) ->
                "No uso Gemini ni otro servicio de inteligencia artificial remoto. La voz se reconoce localmente; las actualizaciones de la aplicación solo consultan GitHub."
            Regex("\\b(gracias|muchas gracias)\\b").containsMatchIn(text) ->
                "De nada. Estoy aquí para ayudarte."
            Regex("\\b(apaga|detente|silencio|cancela)\\b").containsMatchIn(text) ->
                "Entendido. Dime «Jarvis, activa» cuando quieras volver a dar órdenes."
            else ->
                "Todavía no tengo una habilidad local para resolver esa pregunta. No voy a inventar una respuesta ni enviar tus palabras a otra IA. Puedes pedirme una acción instalada o indicar qué habilidad local debemos añadir."
        }
    }

'''
s, count = re.subn(r'(?ms)^    /\*\* Escucha una frase con el reconocimiento de voz de Android\..*?^    private fun beep\(\) \{', lambda _: voice_and_ai + '    private fun beep() {', s, count=1)
if count != 1:
    raise SystemExit("No se pudo sustituir el reconocimiento de voz")
service_path.write_text(s, encoding="utf-8")

# ── Minimal sherpa-onnx Android wrappers matching the pinned v2.0.1 native runtime.
sherpa_api_dir = root / "app/src/main/java/com/k2fsa/sherpa/onnx"
sherpa_api_dir.mkdir(parents=True, exist_ok=True)
(sherpa_api_dir / "SpeakerEmbeddingExtractorConfig.kt").write_text(r"""package com.k2fsa.sherpa.onnx

data class SpeakerEmbeddingExtractorConfig(
    val model: String = "",
    var numThreads: Int = 1,
    var debug: Boolean = false,
    var provider: String = "cpu",
)
""", encoding="utf-8")
(sherpa_api_dir / "OnlineStream.kt").write_text(r"""package com.k2fsa.sherpa.onnx

class OnlineStream(var ptr: Long = 0) {
    init {
        require(ptr != 0L) { "Failed to create native OnlineStream" }
    }

    fun acceptWaveform(samples: FloatArray, sampleRate: Int) =
        acceptWaveform(ptr, samples, sampleRate)

    fun inputFinished() = inputFinished(ptr)

    protected fun finalize() {
        if (ptr != 0L) {
            delete(ptr)
            ptr = 0
        }
    }

    fun release() = finalize()

    private external fun acceptWaveform(ptr: Long, samples: FloatArray, sampleRate: Int)
    private external fun inputFinished(ptr: Long)
    private external fun delete(ptr: Long)

    companion object {
        init {
            System.loadLibrary("sherpa-onnx-jni")
        }
    }
}
""", encoding="utf-8")
(sherpa_api_dir / "Speaker.kt").write_text(r"""package com.k2fsa.sherpa.onnx

import android.content.res.AssetManager

class SpeakerEmbeddingExtractor(
    assetManager: AssetManager? = null,
    config: SpeakerEmbeddingExtractorConfig,
) {
    private var ptr: Long

    init {
        ptr = if (assetManager != null) {
            newFromAsset(assetManager, config)
        } else {
            newFromFile(config)
        }
        require(ptr != 0L) {
            "Invalid SpeakerEmbeddingExtractorConfig: failed to create native SpeakerEmbeddingExtractor"
        }
    }

    protected fun finalize() {
        if (ptr != 0L) {
            delete(ptr)
            ptr = 0
        }
    }

    fun release() = finalize()

    fun createStream(): OnlineStream = OnlineStream(createStream(ptr))
    fun isReady(stream: OnlineStream) = isReady(ptr, stream.ptr)
    fun compute(stream: OnlineStream) = compute(ptr, stream.ptr)
    fun dim() = dim(ptr)

    private external fun newFromAsset(
        assetManager: AssetManager,
        config: SpeakerEmbeddingExtractorConfig,
    ): Long
    private external fun newFromFile(config: SpeakerEmbeddingExtractorConfig): Long
    private external fun delete(ptr: Long)
    private external fun createStream(ptr: Long): Long
    private external fun isReady(ptr: Long, streamPtr: Long): Boolean
    private external fun compute(ptr: Long, streamPtr: Long): FloatArray
    private external fun dim(ptr: Long): Int

    companion object {
        init {
            System.loadLibrary("sherpa-onnx-jni")
        }
    }
}
""", encoding="utf-8")

# ── Owner-only voice identity (offline speaker embeddings; no raw audio is stored).
owner_voice = r'''package com.jarvis.personal

import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.SystemClock
import android.util.Log
import com.k2fsa.sherpa.onnx.OnlineStream
import com.k2fsa.sherpa.onnx.SpeakerEmbeddingExtractor
import com.k2fsa.sherpa.onnx.SpeakerEmbeddingExtractorConfig
import org.json.JSONArray
import kotlin.math.sqrt

object OwnerVoiceVerifier {
    private const val STORE = "jarvis_owner_voice"
    private const val EMBEDDING_KEY = "owner_embedding_v1"
    private const val SAMPLE_RATE = 16000
    private const val MODEL_ASSET = "jarvis-speaker.onnx"
    private const val MIN_VERIFY_SAMPLES = SAMPLE_RATE * 2
    // Initial threshold; it must be tuned against real recordings on the target phone.
    private const val SIMILARITY_THRESHOLD = 0.74f
    @Volatile private var extractor: SpeakerEmbeddingExtractor? = null
    @Volatile private var cachedEnrollmentJson: String? = null
    @Volatile private var cachedEnrollmentEmbedding: FloatArray? = null

    fun warmUp(context: Context) {
        Thread({
            try { getExtractor(context.applicationContext) }
            catch (e: Exception) { Log.e("JarvisVoice", "No se pudo precargar el verificador local", e) }
        }, "jarvis-voice-warmup").apply { isDaemon = true; start() }
    }

    fun isEnrolled(context: Context): Boolean =
        !context.getSharedPreferences(STORE, Context.MODE_PRIVATE).getString(EMBEDDING_KEY, null).isNullOrBlank()

    fun clearEnrollment(context: Context) {
        cachedEnrollmentJson = null
        cachedEnrollmentEmbedding = null
        context.getSharedPreferences(STORE, Context.MODE_PRIVATE).edit().remove(EMBEDDING_KEY).apply()
    }

    private fun getExtractor(context: Context): SpeakerEmbeddingExtractor {
        val current = extractor
        if (current != null) return current
        synchronized(this) {
            val again = extractor
            if (again != null) return again
            val created = SpeakerEmbeddingExtractor(
                assetManager = context.applicationContext.assets,
                config = SpeakerEmbeddingExtractorConfig(
                    model = MODEL_ASSET,
                    numThreads = 2,
                    debug = false,
                    provider = "cpu"
                )
            )
            extractor = created
            return created
        }
    }

    fun captureOwnerSample(context: Context): FloatArray? {
        val minBuffer = AudioRecord.getMinBufferSize(
            SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT
        )
        if (minBuffer <= 0) return null
        var recorder: AudioRecord? = null
        return try {
            recorder = AudioRecord(
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                maxOf(minBuffer, SAMPLE_RATE * 2)
            )
            if (recorder.state != AudioRecord.STATE_INITIALIZED) return null
            recorder.startRecording()
            val expected = SAMPLE_RATE * 3
            val pcm = FloatArray(expected)
            val buffer = ShortArray(1600)
            var written = 0
            val start = SystemClock.elapsedRealtime()
            while (written < expected && SystemClock.elapsedRealtime() - start < 5000) {
                val count = recorder.read(buffer, 0, minOf(buffer.size, expected - written))
                if (count > 0) {
                    for (i in 0 until count) pcm[written + i] = buffer[i] / 32768.0f
                    written += count
                }
            }
            if (written < SAMPLE_RATE * 2) null else embedding(context, pcm.copyOf(written))
        } catch (e: Exception) {
            Log.e("JarvisVoice", "No se pudo grabar la muestra de voz", e)
            null
        } finally {
            try {
                if (recorder?.recordingState == AudioRecord.RECORDSTATE_RECORDING) recorder?.stop()
            } catch (_: Exception) {}
            try { recorder?.release() } catch (_: Exception) {}
        }
    }

    fun saveOwner(context: Context, recordings: List<FloatArray>): Boolean {
        if (recordings.size < 2) return false
        val dimensions = recordings.first().size
        if (dimensions == 0 || recordings.any { it.size != dimensions }) return false
        val mean = FloatArray(dimensions) { i ->
            recordings.sumOf { it[i].toDouble() }.toFloat() / recordings.size
        }
        val normalized = normalize(mean) ?: return false
        val json = JSONArray()
        normalized.forEach { json.put(it.toDouble()) }
        val encoded = json.toString()
        val saved = context.getSharedPreferences(STORE, Context.MODE_PRIVATE)
            .edit().putString(EMBEDDING_KEY, encoded).commit()
        if (saved) {
            cachedEnrollmentJson = encoded
            cachedEnrollmentEmbedding = normalized
        }
        return saved
    }

    fun matches(context: Context, audio: FloatArray): Boolean {
        if (audio.size < MIN_VERIFY_SAMPLES) return false
        val raw = context.getSharedPreferences(STORE, Context.MODE_PRIVATE)
            .getString(EMBEDDING_KEY, null) ?: return false
        return try {
            val cached = cachedEnrollmentEmbedding
            val enrolled = if (cached != null && raw == cachedEnrollmentJson) {
                cached
            } else {
                val json = JSONArray(raw)
                FloatArray(json.length()) { json.getDouble(it).toFloat() }.also {
                    cachedEnrollmentJson = raw
                    cachedEnrollmentEmbedding = it
                }
            }
            val candidate = embedding(context, audio.takeLast(SAMPLE_RATE * 3).toFloatArray()) ?: return false
            if (candidate.size != enrolled.size) return false
            val score = cosine(enrolled, candidate)
            Log.d("JarvisVoice", "Coincidencia de voz local: " + score)
            score >= SIMILARITY_THRESHOLD
        } catch (e: Exception) {
            Log.e("JarvisVoice", "Falló la verificación local de voz", e)
            false
        }
    }

    private fun embedding(context: Context, audio: FloatArray): FloatArray? {
        if (audio.size < SAMPLE_RATE) return null
        var energy = 0.0
        for (sample in audio) energy += sample * sample
        val rms = sqrt(energy / audio.size).toFloat()
        if (rms < 0.005f) return null
        val model = getExtractor(context)
        val stream: OnlineStream = model.createStream()
        try {
            var offset = 0
            while (offset < audio.size) {
                val end = minOf(offset + 1600, audio.size)
                stream.acceptWaveform(audio.copyOfRange(offset, end), SAMPLE_RATE)
                offset = end
            }
            stream.inputFinished()
            if (!model.isReady(stream)) return null
            return normalize(model.compute(stream))
        } catch (e: Exception) {
            Log.e("JarvisVoice", "No se pudo calcular la identidad de voz", e)
            return null
        } finally {
            try { stream.release() } catch (_: Exception) {}
        }
    }

    private fun normalize(input: FloatArray): FloatArray? {
        var sum = 0.0
        for (value in input) sum += value * value
        val norm = sqrt(sum).toFloat()
        if (norm <= 0.000001f) return null
        return FloatArray(input.size) { input[it] / norm }
    }

    private fun cosine(a: FloatArray, b: FloatArray): Float {
        var dot = 0.0
        var na = 0.0
        var nb = 0.0
        for (i in a.indices) {
            dot += a[i] * b[i]
            na += a[i] * a[i]
            nb += b[i] * b[i]
        }
        if (na <= 0.0 || nb <= 0.0) return -1f
        return (dot / (sqrt(na) * sqrt(nb))).toFloat()
    }
}
'''
owner_path = root / "app/src/main/java/com/jarvis/personal/OwnerVoiceVerifier.kt"
owner_path.write_text(owner_voice, encoding="utf-8")

voice_setup = r'''package com.jarvis.personal

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast

class VoiceSetupActivity : Activity() {
    private val recordings = mutableListOf<FloatArray>()
    private lateinit var status: TextView
    private lateinit var recordButton: Button
    private var busy = false
    private val pad by lazy { (resources.displayMetrics.density * 20).toInt() }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = Color.parseColor("#07111D")
        window.navigationBarColor = Color.parseColor("#07111D")
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad * 2, pad, pad)
            setBackgroundColor(Color.parseColor("#07111D"))
        }
        root.addView(TextView(this).apply {
            text = "JARVIS · REGISTRO DE VOZ"
            textSize = 22f
            setTextColor(Color.parseColor("#D9F7FF"))
        })
        root.addView(TextView(this).apply {
            text = "Graba dos muestras de tu voz. En cada una habla con naturalidad durante tres segundos. El procesamiento es local y solo se guarda una representación numérica de la voz; no se guardan las grabaciones."
            textSize = 15f
            setTextColor(Color.parseColor("#AFC5D6"))
            setPadding(0, pad, 0, pad)
        })
        status = TextView(this).apply {
            text = "Muestras registradas: 0 de 2"
            textSize = 16f
            setTextColor(Color.parseColor("#E5F1FA"))
            setPadding(0, pad, 0, pad)
        }
        root.addView(status)
        recordButton = button("Grabar muestra 1 de 2") { recordOne() }
        root.addView(recordButton)
        root.addView(button("Borrar registro de voz") {
            OwnerVoiceVerifier.clearEnrollment(this)
            recordings.clear()
            status.text = "Registro borrado. Muestras: 0 de 2."
            recordButton.isEnabled = true
            recordButton.text = "Grabar muestra 1 de 2"
            Toast.makeText(this, "Registro de voz borrado", Toast.LENGTH_SHORT).show()
        })
        root.addView(button("Volver") { finish() })
        setContentView(root)
    }

    private fun recordOne() {
        if (busy) return
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 75)
            return
        }
        busy = true
        recordButton.isEnabled = false
        status.text = "Grabando muestra " + (recordings.size + 1) + " de 2. Habla ahora durante tres segundos."
        Thread {
            val result = OwnerVoiceVerifier.captureOwnerSample(this)
            runOnUiThread {
                busy = false
                recordButton.isEnabled = true
                if (result == null) {
                    status.text = "No pude obtener una muestra clara. Comprueba el micrófono y vuelve a intentarlo."
                    recordButton.text = "Reintentar muestra " + (recordings.size + 1) + " de 2"
                    return@runOnUiThread
                }
                recordings.add(result)
                if (recordings.size < 2) {
                    status.text = "Muestra guardada. Muestras registradas: " + recordings.size + " de 2. Continúa hablando con naturalidad."
                    recordButton.text = "Grabar muestra " + (recordings.size + 1) + " de 2"
                } else {
                    val ok = OwnerVoiceVerifier.saveOwner(this, recordings)
                    status.text = if (ok) "Voz del propietario registrada en este teléfono. Jarvis solo procesará órdenes que superen la comparación local." else "No pude guardar el registro. Intenta configurar la voz otra vez."
                    recordButton.text = if (ok) "Voz registrada" else "Reintentar registro"
                    recordButton.isEnabled = !ok
                    if (ok) Toast.makeText(this, "Voz del propietario registrada", Toast.LENGTH_LONG).show()
                }
            }
        }.start()
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 75 && grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) recordOne()
    }

    private fun button(label: String, action: () -> Unit) = Button(this).apply {
        text = label
        isAllCaps = false
        setTextColor(Color.parseColor("#E5F1FA"))
        background = GradientDrawable().apply {
            setColor(Color.parseColor("#172B3F"))
            cornerRadius = 18f
            setStroke(1, Color.parseColor("#2F4C63"))
        }
        setPadding(12, 4, 12, 4)
        setOnClickListener { action() }
    }
}
'''
(root / "app/src/main/java/com/jarvis/personal/VoiceSetupActivity.kt").write_text(voice_setup, encoding="utf-8")

# Register the onboarding screen in Android.
manifest = root / "app/src/main/AndroidManifest.xml"
xml = manifest.read_text(encoding="utf-8")
if 'android:name=".VoiceSetupActivity"' not in xml:
    xml = xml.replace("</application>", '        <activity android:name=".VoiceSetupActivity" android:exported="false" />\n    </application>', 1)
manifest.write_text(xml, encoding="utf-8")

# Vector app icon: futuristic reactor palette; no external image dependency.
icon = root / "app/src/main/res/drawable/ic_launcher.xml"
icon.write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="96dp" android:height="96dp"
    android:viewportWidth="96" android:viewportHeight="96">
    <path android:fillColor="#06101D" android:pathData="M48,2a46,46 0,1 0,0 92a46,46 0,1 0,0 -92" />
    <path android:fillColor="#10253A" android:pathData="M48,9a39,39 0,1 0,0 78a39,39 0,1 0,0 -78" />
    <path android:fillColor="#00E5FF" android:pathData="M48,12a36,36 0,1 0,0 72a36,36 0,1 0,0 -72 M48,16a32,32 0,1 1,0 64a32,32 0,1 1,0 -64" />
    <path android:fillColor="#06101D" android:pathData="M48,22a26,26 0,1 0,0 52a26,26 0,1 0,0 -52" />
    <path android:fillColor="#17435A" android:pathData="M48,27a21,21 0,1 0,0 42a21,21 0,1 0,0 -42" />
    <path android:fillColor="#00E5FF" android:pathData="M34,31 L60,31 L60,38 L42,38 L42,53 C42,59 46,62 51,58 L55,54 L61,59 L56,65 C46,73 34,66 34,54 Z" />
    <path android:fillColor="#D6FBFF" android:pathData="M48,6a3,3 0,1 0,0 6a3,3 0,1 0,0 -6 M48,84a3,3 0,1 0,0 6a3,3 0,1 0,0 -6 M6,48a3,3 0,1 0,0 6a3,3 0,1 0,0 -6 M84,48a3,3 0,1 0,0 6a3,3 0,1 0,0 -6" />
</vector>
''', encoding="utf-8")


# Ensure the Vosk Android Java API is available to Kotlin compilation.
gradle_candidates = [root / "app/build.gradle.kts", root / "app/build.gradle"]
gradle_path = next((path for path in gradle_candidates if path.exists()), None)
if gradle_path is None:
    raise SystemExit("No se encontró app/build.gradle.kts ni app/build.gradle")
gradle_text = gradle_path.read_text(encoding="utf-8")
vosk_dependency = "com.alphacephei:vosk-android"
if vosk_dependency in gradle_text:
    gradle_text = re.sub(r"(com\.alphacephei:vosk-android:)[0-9.]+", r"\g<1>0.3.75", gradle_text)
else:
    if gradle_path.name.endswith(".kts"):
        dependency_line = '    implementation("com.alphacephei:vosk-android:0.3.75")'
    else:
        dependency_line = "    implementation 'com.alphacephei:vosk-android:0.3.75'"
    if "dependencies {" not in gradle_text:
        raise SystemExit("No se encontró el bloque dependencies en el archivo Gradle de la app")
    gradle_text = gradle_text.replace("dependencies {", "dependencies {" + chr(10) + dependency_line, 1)
gradle_path.write_text(gradle_text, encoding='utf-8')

print("Parche aplicado: voz del propietario, sesión persistente y cerebro local LiteRT-LM descargable.")

# ── Opt-in Android accessibility controls for visible app UI.
service_path = root / "app/src/main/java/com/jarvis/personal/JarvisService.kt"
service_text = service_path.read_text(encoding="utf-8")
for import_line in ("import android.net.Uri", "import java.net.URLEncoder", "import android.content.Intent"):
    if import_line not in service_text:
        service_text = service_text.replace("package com.jarvis.personal\n", "package com.jarvis.personal\n" + import_line + "\n", 1)

if "private var pendingSensitiveUiTarget: String? = null" not in service_text:
    service_text = replace_once(
        service_text,
        "    private var busy = false\n",
        "    private var busy = false\n    private var pendingSensitiveUiTarget: String? = null\n",
        "estado de confirmación de acciones de pantalla"
    )
service_text = replace_once(
    service_text,
    "is Cmd.Unknown -> respondNaturally(cmd.raw)",
    "is Cmd.Unknown -> if (!handleScreenCommand(cmd.raw)) respondNaturally(cmd.raw)",
    "despacho de órdenes a controles de pantalla"
)
service_text = replace_once(
    service_text,
    'Cmd.Cancel -> speak("Está bien.")',
    'Cmd.Cancel -> { pendingSensitiveUiTarget = null; speak("Está bien.") }',
    "cancelación de acción pendiente"
)

screen_methods = r'''    private suspend fun handleScreenCommand(raw: String): Boolean {
        val cleaned = raw.trim()
        val normalized = strip(raw)
        val confirmPhrases = listOf("confirma accion", "confirmar accion", "confirmo la accion", "si confirma", "si, confirma", "confirmar")
        if (pendingSensitiveUiTarget != null) {
            if (normalized in confirmPhrases) {
                val target = pendingSensitiveUiTarget ?: return true
                pendingSensitiveUiTarget = null
                val success = JarvisAccessibilityService.clickByText(target)
                speak(if (success) "Acción confirmada. Pulsé " + target + "." else "No pude encontrar el control " + target + ". No se ejecutó la acción.")
                return true
            }
            if (normalized in listOf("cancela accion", "cancelar accion", "no, cancelar", "no")) {
                pendingSensitiveUiTarget = null
                speak("Acción cancelada.")
                return true
            }
            pendingSensitiveUiTarget = null
        }

        if (normalized in listOf("atras", "volver", "retrocede", "vuelve atras", "regresa")) {
            if (!JarvisAccessibilityService.isConnected()) speak("Para controlar otras aplicaciones, activa el servicio de Accesibilidad de Jarvis desde su pantalla principal.")
            else speak(if (JarvisAccessibilityService.navigate("back")) "Volviendo atrás." else "No pude volver atrás en esta pantalla.")
            return true
        }
        if (normalized in listOf("inicio", "pantalla principal", "vuelve al inicio", "ir a inicio")) {
            if (!JarvisAccessibilityService.isConnected()) speak("Activa primero el control de pantalla de Jarvis en los ajustes de Accesibilidad.")
            else speak(if (JarvisAccessibilityService.navigate("home")) "Volviendo a la pantalla principal." else "Android no permitió ir al inicio.")
            return true
        }
        if (normalized in listOf("muestra notificaciones", "abre notificaciones", "panel de notificaciones")) {
            if (!JarvisAccessibilityService.isConnected()) speak("Activa primero el control de pantalla de Jarvis en los ajustes de Accesibilidad.")
            else speak(if (JarvisAccessibilityService.navigate("notifications")) "Abriendo notificaciones." else "No pude abrir las notificaciones.")
            return true
        }
        if (normalized in listOf("abre ajustes rapidos", "muestra ajustes rapidos", "panel rapido")) {
            if (!JarvisAccessibilityService.isConnected()) speak("Activa primero el control de pantalla de Jarvis en los ajustes de Accesibilidad.")
            else speak(if (JarvisAccessibilityService.navigate("quick_settings")) "Abriendo ajustes rápidos." else "No pude abrir los ajustes rápidos.")
            return true
        }
        if (Regex("(baja|desplaza hacia abajo|desliza hacia abajo|scroll abajo|desplazate abajo)").containsMatchIn(normalized)) {
            if (!JarvisAccessibilityService.isConnected()) speak("Activa primero el control de pantalla de Jarvis en los ajustes de Accesibilidad.")
            else speak(if (JarvisAccessibilityService.scroll(true)) "Desplazando hacia abajo." else "No encontré una zona desplazable en esta pantalla.")
            return true
        }
        if (Regex("(sube|desplaza hacia arriba|desliza hacia arriba|scroll arriba|desplazate arriba)").containsMatchIn(normalized)) {
            if (!JarvisAccessibilityService.isConnected()) speak("Activa primero el control de pantalla de Jarvis en los ajustes de Accesibilidad.")
            else speak(if (JarvisAccessibilityService.scroll(false)) "Desplazando hacia arriba." else "No encontré una zona desplazable en esta pantalla.")
            return true
        }
        if (Regex("(lee la pantalla|que dice la pantalla|que hay en pantalla|describe esta pantalla|lee lo que aparece)").containsMatchIn(normalized)) {
            val summary = JarvisAccessibilityService.readScreen()
            speak(summary ?: "No tengo acceso al contenido de esta pantalla. Abre Jarvis y activa el servicio de Accesibilidad si deseas usar esta función.")
            return true
        }

        val youtubeSearch = Regex("^(?:busca|buscar|buscame)\\s+(.+?)\\s+en\\s+youtube$", RegexOption.IGNORE_CASE).find(cleaned)
        if (youtubeSearch != null) {
            val query = youtubeSearch.groupValues[1].trim()
            try {
                val uri = Uri.parse("https://www.youtube.com/results?search_query=" + URLEncoder.encode(query, "UTF-8"))
                startActivity(Intent(Intent.ACTION_VIEW, uri).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                speak("Buscando en YouTube: " + query)
            } catch (e: Exception) {
                Log.e(TAG, "No pude abrir la búsqueda de YouTube", e)
                speak("No pude abrir YouTube ahora mismo.")
            }
            return true
        }

        val clickMatch = Regex("^(?:toca|pulsa|presiona|haz clic en|selecciona|elige)(?:\\s+(?:el|la|los|las))?(?:\\s+(?:boton|botón|opcion|opción|enlace))?\\s+(.+)$", RegexOption.IGNORE_CASE).find(cleaned)
        if (clickMatch != null) {
            val target = clickMatch.groupValues[1].trim().trimEnd('.')
            if (!JarvisAccessibilityService.isConnected()) {
                speak("Para pulsar controles de otras aplicaciones, activa el servicio de Accesibilidad de Jarvis desde su pantalla principal.")
                return true
            }
            val sensitive = Regex("\\b(enviar|send|publicar|postear|pagar|pago|comprar|eliminar|borrar|delete|transferir|confirmar compra)\\b").containsMatchIn(strip(target))
            if (sensitive) {
                pendingSensitiveUiTarget = target
                speak("El control " + target + " podría enviar, publicar, pagar o borrar información. Si confirmas que quieres pulsarlo, di confirma acción. Para cancelar, di cancela.")
                return true
            }
            val success = JarvisAccessibilityService.clickByText(target)
            speak(if (success) "Listo. Pulsé " + target + "." else "No encontré un control visible llamado " + target + ". Dime el texto exacto que aparece en pantalla.")
            return true
        }

        val typeMatch = Regex("^(?:escribe|teclea|introduce|ingresa)\\s+(.+)$", RegexOption.IGNORE_CASE).find(cleaned)
        if (typeMatch != null) {
            val value = typeMatch.groupValues[1].trim()
            if (!JarvisAccessibilityService.isConnected()) speak("Para escribir dentro de otras aplicaciones, activa el servicio de Accesibilidad de Jarvis desde su pantalla principal.")
            else speak(if (JarvisAccessibilityService.typeIntoFocusedField(value)) "Texto escrito en el campo activo." else "No encontré un campo de texto activo. Pulsa primero el campo donde quieres escribir.")
            return true
        }
        return false
    }

'''
service_text = service_text.replace("    private fun timeText(): String {", screen_methods + "    private fun timeText(): String {", 1);
service_path.write_text(service_text, encoding="utf-8");

accessibility_service_path = root / "app/src/main/java/com/jarvis/personal/JarvisAccessibilityService.kt"
accessibility_service_path.parent.mkdir(parents=True, exist_ok=True)
accessibility_service_path.write_text(r'''package com.jarvis.personal

import android.accessibilityservice.AccessibilityService
import android.os.Bundle
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

/**
 * Accesibilidad opcional controlada por la persona propietaria desde los ajustes de Android.
 * No registra ni transmite eventos; solo procesa la pantalla cuando Jarvis recibe una orden.
 */
class JarvisAccessibilityService : AccessibilityService() {
    override fun onServiceConnected() {
        super.onServiceConnected()
        current = this
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // No guardamos texto, pulsaciones ni contenido de eventos.
    }

    override fun onInterrupt() {
        // Android puede interrumpir temporalmente el servicio.
    }

    override fun onDestroy() {
        if (current === this) current = null
        super.onDestroy()
    }

    companion object {
        @Volatile private var current: JarvisAccessibilityService? = null

        fun isConnected(): Boolean = current != null

        fun navigate(action: String): Boolean {
            val service = current ?: return false
            val globalAction = when (action) {
                "back" -> AccessibilityService.GLOBAL_ACTION_BACK
                "home" -> AccessibilityService.GLOBAL_ACTION_HOME
                "notifications" -> AccessibilityService.GLOBAL_ACTION_NOTIFICATIONS
                "quick_settings" -> AccessibilityService.GLOBAL_ACTION_QUICK_SETTINGS
                else -> return false
            }
            return try { service.performGlobalAction(globalAction) } catch (_: Exception) { false }
        }

        fun clickByText(query: String): Boolean {
            val service = current ?: return false
            val root = service.rootInActiveWindow ?: return false
            return try {
                val nodes = root.findAccessibilityNodeInfosByText(query)
                for (node in nodes) {
                    var candidate: AccessibilityNodeInfo? = node
                    var depth = 0
                    while (candidate != null && depth < 8) {
                        if (candidate.isEnabled && candidate.isClickable &&
                            candidate.performAction(AccessibilityNodeInfo.ACTION_CLICK)) return true
                        candidate = candidate.parent
                        depth += 1
                    }
                    if (node.isEnabled && node.performAction(AccessibilityNodeInfo.ACTION_CLICK)) return true
                }
                false
            } catch (_: Exception) { false }
        }

        fun typeIntoFocusedField(value: String): Boolean {
            val service = current ?: return false
            val root = service.rootInActiveWindow ?: return false
            return try {
                val field = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
                if (field == null || !field.isEditable || !field.isEnabled) return false
                val args = Bundle().apply {
                    putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, value)
                }
                field.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
            } catch (_: Exception) { false }
        }

        fun scroll(forward: Boolean): Boolean {
            val root = current?.rootInActiveWindow ?: return false
            val action = if (forward) AccessibilityNodeInfo.ACTION_SCROLL_FORWARD else AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD
            fun visit(node: AccessibilityNodeInfo?, depth: Int): Boolean {
                if (node == null || depth > 14) return false
                if (node.isScrollable && node.isEnabled && node.performAction(action)) return true
                for (index in 0 until node.childCount) {
                    val child = node.getChild(index) ?: continue
                    if (visit(child, depth + 1)) return true
                }
                return false
            }
            return try { visit(root, 0) } catch (_: Exception) { false }
        }

        fun readScreen(): String? {
            val root = current?.rootInActiveWindow ?: return null
            val output = mutableListOf<String>()
            fun visit(node: AccessibilityNodeInfo?, depth: Int) {
                if (node == null || depth > 14 || output.size >= 45) return
                if (node.isVisibleToUser) {
                    val text = node.text?.toString()?.trim().orEmpty()
                    val description = node.contentDescription?.toString()?.trim().orEmpty()
                    if (text.isNotBlank()) output.add(text)
                    else if (description.isNotBlank()) output.add(description)
                }
                for (index in 0 until node.childCount) {
                    if (output.size >= 45) break
                    visit(node.getChild(index), depth + 1)
                }
            }
            return try {
                visit(root, 0)
                output.distinct().joinToString(". ").take(700).takeIf { it.isNotBlank() }
            } catch (_: Exception) { null }
        }
    }
}
''', encoding="utf-8")

accessibility_xml_dir = root / "app/src/main/res/xml"
accessibility_xml_dir.mkdir(parents=True, exist_ok=True)
(accessibility_xml_dir / "jarvis_accessibility_service.xml").write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<accessibility-service xmlns:android="http://schemas.android.com/apk/res/android"
    android:accessibilityEventTypes="typeWindowStateChanged|typeWindowContentChanged"
    android:accessibilityFeedbackType="feedbackGeneric"
    android:notificationTimeout="100"
    android:canRetrieveWindowContent="true" />
''', encoding="utf-8")

manifest = root / "app/src/main/AndroidManifest.xml"
xml = manifest.read_text(encoding="utf-8")
if 'android:name=".JarvisAccessibilityService"' not in xml:
    entry = r'''        <service
            android:name=".JarvisAccessibilityService"
            android:label="Control de pantalla de Jarvis"
            android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE"
            android:exported="true">
            <intent-filter>
                <action android:name="android.accessibilityservice.AccessibilityService" />
            </intent-filter>
            <meta-data
                android:name="android.accessibilityservice"
                android:resource="@xml/jarvis_accessibility_service" />
        </service>
'''
    if "</application>" not in xml:
        raise SystemExit("No se encontró el cierre application en AndroidManifest.xml")
    xml = xml.replace("</application>", entry + "    </application>", 1)
manifest.write_text(xml, encoding="utf-8")

print("Añadido control de pantalla opcional mediante Accesibilidad de Android.")


# ── Final privacy-safe Android home screen: one primary button, first-run permissions and update restart countdown.
main_activity = r'''package com.jarvis.personal

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.provider.Settings
import android.view.Gravity
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast

class MainActivity : Activity() {
    private lateinit var status: TextView
    private lateinit var mainButton: Button
    private val handler = Handler(Looper.getMainLooper())
    private val permissionQueue = mutableListOf<String>()
    private var countdownActive = false
    private var lastKnownVersion = 0
    private val statePrefs by lazy { getSharedPreferences("jarvis_runtime", Context.MODE_PRIVATE) }
    private val setupPrefs by lazy { getSharedPreferences("jarvis_setup", Context.MODE_PRIVATE) }
    private val pad by lazy { (resources.displayMetrics.density * 22).toInt() }
    private val runtimePermissions: List<String>
        get() = buildList {
            add(Manifest.permission.RECORD_AUDIO)
            add(Manifest.permission.READ_CONTACTS)
            add(Manifest.permission.CALL_PHONE)
            add(Manifest.permission.READ_PHONE_STATE)
            add(Manifest.permission.SEND_SMS)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) add(Manifest.permission.POST_NOTIFICATIONS)
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = Color.parseColor("#06101D")
        window.navigationBarColor = Color.parseColor("#06101D")
        window.decorView.setBackgroundColor(Color.parseColor("#06101D"))

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(pad, pad * 2, pad, pad * 2)
            background = GradientDrawable(
                GradientDrawable.Orientation.TOP_BOTTOM,
                intArrayOf(Color.parseColor("#06101D"), Color.parseColor("#0B2032"), Color.parseColor("#06101D"))
            )
        }
        val reactor = TextView(this).apply {
            text = "⟡"
            textSize = 60f
            gravity = Gravity.CENTER
            typeface = Typeface.create("sans-serif-light", Typeface.NORMAL)
            setTextColor(Color.parseColor("#00E5FF"))
            background = GradientDrawable().apply {
                shape = GradientDrawable.OVAL
                setColor(Color.parseColor("#10273A"))
                setStroke((resources.displayMetrics.density * 2).toInt(), Color.parseColor("#00BFD8"))
            }
            val size = (resources.displayMetrics.density * 112).toInt()
            layoutParams = LinearLayout.LayoutParams(size, size).apply { bottomMargin = pad }
        }
        root.addView(reactor)
        root.addView(TextView(this).apply {
            text = "J A R V I S"
            textSize = 30f
            gravity = Gravity.CENTER
            typeface = Typeface.create("sans-serif-light", Typeface.NORMAL)
            setTextColor(Color.parseColor("#E6FCFF"))
            letterSpacing = 0.18f
        })
        root.addView(TextView(this).apply {
            text = "ASISTENTE PRIVADO · PROCESAMIENTO LOCAL"
            textSize = 11f
            gravity = Gravity.CENTER
            setTextColor(Color.parseColor("#7DA3B8"))
            setPadding(0, pad / 3, 0, pad)
        })
        status = TextView(this).apply {
            text = "SISTEMA EN ESPERA"
            textSize = 13f
            gravity = Gravity.CENTER
            setTextColor(Color.parseColor("#9EDAE5"))
            setPadding(0, pad, 0, pad * 2)
        }
        root.addView(status)
        mainButton = makeMainButton("INICIAR JARVIS")
        root.addView(mainButton)
        root.addView(TextView(this).apply {
            text = "Sin Gemini ni IA remota. Tus órdenes se procesan localmente. Internet se usa únicamente para revisar actualizaciones de la aplicación."
            textSize = 11f
            gravity = Gravity.CENTER
            setTextColor(Color.parseColor("#65869A"))
            setPadding(0, pad, 0, 0)
        })
        setContentView(root)

        // Warm the local speaker verifier while the first-run dialog/permissions are being handled.
        OwnerVoiceVerifier.warmUp(applicationContext)
        handleVersionChange()
        if (!setupPrefs.getBoolean("setup_complete", false) &&
            !setupPrefs.getBoolean("welcome_dialog_seen", false)) {
            handler.postDelayed({ showWelcomeDialog() }, 450)
        }
        refreshUi()
    }

    override fun onResume() {
        super.onResume()
        if (setupPrefs.getBoolean("voice_setup_pending", false)) {
            setupPrefs.edit().putBoolean("voice_setup_pending", false).apply()
            if (OwnerVoiceVerifier.isEnrolled(this) && hasPermission(Manifest.permission.RECORD_AUDIO)) {
                completeSetupAndStart()
            } else {
                status.text = "REGISTRO DE VOZ PENDIENTE · PULSA INICIAR PARA CONTINUAR"
            }
        }
        refreshUi()
    }

    private fun showWelcomeDialog() {
        setupPrefs.edit().putBoolean("welcome_dialog_seen", true).apply()
        AlertDialog.Builder(this)
            .setTitle("JARVIS · CONFIGURACIÓN INICIAL")
            .setMessage(
                "JARVIS funciona en este teléfono y no envía tus conversaciones a Gemini ni a otra IA remota. Esta versión utiliza habilidades locales creadas para la aplicación; no es una IA general entrenada desde cero.\n\n" +
                "Al continuar, Android te pedirá los permisos del micrófono y de las funciones opcionales, uno por uno. Después registrarás dos muestras cortas de tu voz."
            )
            .setPositiveButton("CONTINUAR Y DAR PERMISOS") { _, _ -> beginPermissionFlow() }
            .setNegativeButton("MÁS TARDE") { _, _ ->
                status.text = "LISTO PARA CONFIGURAR · PULSA INICIAR"
                refreshUi()
            }
            .show()
    }

    private fun beginPermissionFlow() {
        permissionQueue.clear()
        permissionQueue.addAll(runtimePermissions.filterNot { hasPermission(it) })
        requestNextPermission()
    }

    private fun requestNextPermission() {
        while (permissionQueue.isNotEmpty() && hasPermission(permissionQueue.first())) {
            permissionQueue.removeAt(0)
        }
        val next = permissionQueue.firstOrNull()
        if (next != null) {
            permissionQueue.removeAt(0)
            requestPermissions(arrayOf(next), 201)
            return
        }
        if (!hasPermission(Manifest.permission.RECORD_AUDIO)) {
            AlertDialog.Builder(this)
                .setTitle("JARVIS necesita el micrófono")
                .setMessage("Sin permiso de micrófono no puede escuchar ni ejecutar órdenes por voz.")
                .setPositiveButton("ABRIR AJUSTES") { _, _ ->
                    startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + packageName)))
                }
                .setNegativeButton("CERRAR", null)
                .show()
            status.text = "FALTA EL PERMISO DE MICRÓFONO"
            return
        }
        if (!OwnerVoiceVerifier.isEnrolled(this)) {
            setupPrefs.edit().putBoolean("voice_setup_pending", true).apply()
            startActivity(Intent(this, VoiceSetupActivity::class.java))
            return
        }
        completeSetupAndStart()
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 201) {
            refreshUi()
            handler.postDelayed({ requestNextPermission() }, 180)
        }
    }

    private fun hasPermission(permission: String): Boolean =
        Build.VERSION.SDK_INT < Build.VERSION_CODES.M ||
            checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED

    private fun completeSetupAndStart() {
        setupPrefs.edit().putBoolean("setup_complete", true).apply()
        startJarvis()
        Toast.makeText(this, "Configuración terminada. JARVIS está listo.", Toast.LENGTH_LONG).show()
    }

    private fun onMainButton() {
        if (JarvisService.running) {
            stopService(Intent(this, JarvisService::class.java))
            statePrefs.edit().putBoolean("was_running", false).apply()
            refreshUi()
            Toast.makeText(this, "JARVIS detenido.", Toast.LENGTH_SHORT).show()
            return
        }
        if (!setupPrefs.getBoolean("setup_complete", false)) {
            showWelcomeDialog()
            return
        }
        startJarvis()
    }

    private fun startJarvis() {
        if (!hasPermission(Manifest.permission.RECORD_AUDIO)) {
            setupPrefs.edit().putBoolean("welcome_dialog_seen", false).apply()
            showWelcomeDialog()
            return
        }
        if (!OwnerVoiceVerifier.isEnrolled(this)) {
            setupPrefs.edit().putBoolean("voice_setup_pending", true).apply()
            startActivity(Intent(this, VoiceSetupActivity::class.java))
            return
        }
        val serviceIntent = Intent(this, JarvisService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(serviceIntent) else startService(serviceIntent)
        statePrefs.edit().putBoolean("was_running", true).apply()
        refreshUi()
    }

    private fun handleVersionChange() {
        val current = try { packageManager.getPackageInfo(packageName, 0).versionCode }
            catch (_: Exception) { return }
        val previous = statePrefs.getInt("last_seen_version_code", 0)
        statePrefs.edit().putInt("last_seen_version_code", current).apply()
        if (previous <= 0 || current <= previous) return
        countdownActive = true
        var remaining = 3
        fun tick() {
            status.text = "ACTUALIZACIÓN APLICADA · v" + current + "\nREINICIANDO EN " + remaining + "..."
            mainButton.text = "REINICIO · " + remaining
            if (remaining > 1) {
                remaining -= 1
                handler.postDelayed({ tick() }, 1000)
            } else {
                val restartService = statePrefs.getBoolean("was_running", false)
                stopService(Intent(this, JarvisService::class.java))
                handler.postDelayed({
                    if (restartService && hasPermission(Manifest.permission.RECORD_AUDIO) && OwnerVoiceVerifier.isEnrolled(this)) {
                        val serviceIntent = Intent(this, JarvisService::class.java)
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(serviceIntent) else startService(serviceIntent)
                        statePrefs.edit().putBoolean("was_running", true).apply()
                    }
                    countdownActive = false
                    refreshUi()
                    Toast.makeText(this, "Cambios aplicados. JARVIS quedó actualizado.", Toast.LENGTH_LONG).show()
                }, 250)
            }
        }
        tick()
    }

    private fun refreshUi() {
        if (countdownActive || !::status.isInitialized || !::mainButton.isInitialized) return
        if (JarvisService.running) {
            status.text = "● JARVIS ACTIVO · ESCUCHANDO EN LOCAL"
            status.setTextColor(Color.parseColor("#00E5FF"))
            mainButton.text = "DETENER JARVIS"
        } else {
            status.text = if (OwnerVoiceVerifier.isEnrolled(this)) "SISTEMA LISTO · VOZ REGISTRADA" else "SISTEMA EN ESPERA"
            status.setTextColor(Color.parseColor("#9EDAE5"))
            mainButton.text = "INICIAR JARVIS"
        }
    }

    private fun makeMainButton(label: String) = Button(this).apply {
        text = label
        isAllCaps = false
        textSize = 16f
        typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
        setTextColor(Color.parseColor("#06101D"))
        background = GradientDrawable().apply {
            setColor(Color.parseColor("#00D7F0"))
            cornerRadius = resources.displayMetrics.density * 20
            setStroke((resources.displayMetrics.density * 1.5f).toInt(), Color.parseColor("#75F3FF"))
        }
        setPadding(pad, pad / 2, pad, pad / 2)
        layoutParams = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            (resources.displayMetrics.density * 62).toInt()
        )
        setOnClickListener { onMainButton() }
    }
}
'''
main_path = root / "app/src/main/java/com/jarvis/personal/MainActivity.kt"
main_path.write_text(main_activity, encoding="utf-8")

# Do not package a downloaded third-party language model or its inference runtime.
local_brain_path = root / "app/src/main/java/com/jarvis/personal/LocalBrain.kt"
if local_brain_path.exists():
    local_brain_path.unlink()
gradle_candidates = [root / "app/build.gradle.kts", root / "app/build.gradle"]
gradle_path = next((path for path in gradle_candidates if path.exists()), None)
if gradle_path is not None:
    gradle_text = gradle_path.read_text(encoding="utf-8")
    gradle_text = re.sub(
        r'(?m)^\s*implementation\("com\.google\.ai\.edge\.litertlm:litertlm-android:[^"]+"\)\s*\n',
        '',
        gradle_text
    )
    gradle_text = gradle_text.replace('        freeCompilerArgs += "-Xskip-metadata-version-check"' + chr(10), '')
    gradle_path.write_text(gradle_text, encoding="utf-8")

# Remove obsolete credential plumbing from the generated service.
service_path = root / "app/src/main/java/com/jarvis/personal/JarvisService.kt"
service_text = service_path.read_text(encoding="utf-8")
service_text = service_text.replace('        const val PREF_GEMINI_KEY = "gemini_api_key"' + chr(10), '')
service_path.write_text(service_text, encoding="utf-8")
