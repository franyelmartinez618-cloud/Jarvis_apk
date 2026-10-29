from pathlib import Path
import re
import sys

root = Path(sys.argv[1])

def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit("No se encontró el bloque esperado: " + label)
    return text.replace(old, new, 1)

# ── Servicio: conversación por varios turnos, voz offline y Gemini opcional.
service_path = root / "app/src/main/java/com/jarvis/personal/JarvisService.kt"
s = service_path.read_text(encoding="utf-8")
s = s.replace("import android.media.AudioManager\n", "import android.media.AudioManager\nimport android.media.AudioFormat\nimport android.media.AudioRecord\nimport android.media.MediaRecorder\n", 1)
s = s.replace("import org.vosk.LibVosk\n", "import org.json.JSONArray\nimport org.json.JSONObject\nimport org.vosk.LibVosk\nimport org.vosk.Recognizer\n", 1)
s = s.replace("import java.io.FileOutputStream\n", "import java.io.FileOutputStream\nimport java.net.HttpURLConnection\nimport java.net.URL\nimport java.net.URLEncoder\n", 1)

# Ensure the imports used by the local Vosk microphone recognizer exist even if the ZIP changes import order.
required_imports = [
    "import android.media.AudioFormat",
    "import android.media.AudioRecord",
    "import android.media.MediaRecorder",
    "import org.json.JSONArray",
    "import org.json.JSONObject",
    "import org.vosk.Recognizer",
    "import java.net.HttpURLConnection",
    "import java.net.URL",
    "import java.net.URLEncoder",
]
package_line = "package com.jarvis.personal\n"
if package_line not in s:
    raise SystemExit("No se encontró el paquete Java esperado en JarvisService.kt")
for required_import in required_imports:
    if required_import not in s:
        s = s.replace(package_line, package_line + required_import + chr(10), 1)

s = replace_once(s, '        const val PREF_COUNTRY = "country_code"\n', '        const val PREF_COUNTRY = "country_code"\n        const val PREF_GEMINI_KEY = "gemini_api_key"\n', "preferencia Gemini")
s = replace_once(s, "    private var busy = false\n", "    private var busy = false\n    private val dialogueHistory = ArrayList<Pair<String, String>>()\n", "historial de conversación")

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
                            val authorized = OwnerVoiceVerifier.matches(this@JarvisService, capturedAudio.toFloatArray())
                            if (authorized) return@withContext spoken
                            Log.i(TAG, "Voz no autorizada; la orden no se ejecutará")
                            return@withContext null
                        }
                    }
                }
                val finalText = JSONObject(recognizer.getFinalResult()).optString("text").trim()
                if (finalText.isBlank()) null else if (
                    OwnerVoiceVerifier.matches(this@JarvisService, capturedAudio.toFloatArray())
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

    /** La IA solo genera texto; no recibe permiso para ejecutar acciones del dispositivo. */
    private suspend fun respondNaturally(input: String) {
        val key = getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(PREF_GEMINI_KEY, "")?.trim().orEmpty()
        val answer = if (key.isNotBlank()) {
            try { askGemini(key, input) }
            catch (e: Exception) {
                Log.w(TAG, "Gemini no disponible; usaré respuestas locales", e)
                offlineReply(input, onlineFailed = true)
            }
        } else offlineReply(input)
        dialogueHistory.add("user" to input.take(500))
        dialogueHistory.add("model" to answer.take(700))
        while (dialogueHistory.size > 10) dialogueHistory.removeAt(0)
        speak(answer)
    }

    private suspend fun askGemini(apiKey: String, input: String): String = withContext(Dispatchers.IO) {
        val contents = JSONArray()
        for ((role, text) in dialogueHistory.takeLast(8)) {
            contents.put(JSONObject().put("role", role).put("parts", JSONArray().put(JSONObject().put("text", text))))
        }
        contents.put(JSONObject().put("role", "user").put("parts", JSONArray().put(JSONObject().put("text", input.take(1200)))))
        val payload = JSONObject()
            .put("systemInstruction", JSONObject().put("parts", JSONArray().put(JSONObject().put(
                "text", "Eres Jarvis, un asistente personal para Android. Habla en español natural, claro y conciso. No tienes voluntad propia, no inicies tareas ni inventes acciones realizadas. Solo respondes texto; no ejecutas herramientas ni acciones del dispositivo. Para llamadas, SMS, WhatsApp y abrir aplicaciones, el usuario debe dar una orden directa a la app; Jarvis pide confirmación para acciones sensibles. Nunca afirmes haber llamado, enviado o abierto nada."
            ))))
            .put("contents", contents)
            .put("generationConfig", JSONObject().put("maxOutputTokens", 220))
        val endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key=" +
            URLEncoder.encode(apiKey, "UTF-8")
        val connection = (URL(endpoint).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 8000
            readTimeout = 15000
            doOutput = true
            setRequestProperty("Content-Type", "application/json; charset=utf-8")
        }
        try {
            connection.outputStream.use { it.write(payload.toString().toByteArray(Charsets.UTF_8)) }
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val response = stream.bufferedReader(Charsets.UTF_8).use { it.readText() }
            if (code !in 200..299) throw IllegalStateException("Gemini HTTP " + code + ": " + response.take(180))
            val answer = JSONObject(response).optJSONArray("candidates")?.optJSONObject(0)
                ?.optJSONObject("content")?.optJSONArray("parts")?.optJSONObject(0)?.optString("text")?.trim()
            answer?.takeIf { it.isNotBlank() } ?: "No recibí una respuesta útil. Dime otra vez qué necesitas."
        } finally {
            connection.disconnect()
        }
    }

    private fun offlineReply(input: String, onlineFailed: Boolean = false): String {
        val t = strip(input)
        if (onlineFailed) return "Ahora no pude conectar con la IA por internet. Sigo disponible para órdenes y respuestas básicas sin conexión."
        return when {
            Regex("\\b(hola|buenas|buenos dias|buenas tardes|buenas noches)\\b").containsMatchIn(t) -> "Hola. Estoy aquí y te escucho. ¿Qué necesitas?"
            Regex("\\b(como estas|que tal estas)\\b").containsMatchIn(t) -> "Funcionando correctamente y listo para ayudarte. ¿Qué hacemos?"
            Regex("\\b(quien eres|que eres|como te llamas)\\b").containsMatchIn(t) -> "Soy Jarvis, tu asistente personal. No tengo voluntad propia: respondo a tus órdenes y mantengo las acciones sensibles bajo tu confirmación."
            Regex("\\b(gracias|muchas gracias)\\b").containsMatchIn(t) -> "Con gusto. Aquí estoy cuando me necesites."
            Regex("\\b(que puedes hacer|que sabes hacer|comandos|ayuda)\\b").containsMatchIn(t) -> "Puedo abrir aplicaciones por su nombre, consultar la hora y fecha, buscar contactos, preparar WhatsApp y hacer llamadas o SMS con confirmación. Para conversación abierta, configura la clave opcional de Gemini."
            Regex("\\b(estas conectado|tienes internet|ia online|gemini)\\b").containsMatchIn(t) -> "Las órdenes de voz se reconocen localmente. La conversación abierta por internet requiere una clave de Gemini válida; sin ella sigo en modo offline básico."
            else -> "Te escuché, pero esta pregunta necesita conversación abierta. Añade una clave opcional de Gemini API en la pantalla de Jarvis. Las órdenes y el reconocimiento de voz siguen funcionando localmente."
        }
    }

'''
s, count = re.subn(r'(?ms)^    /\*\* Escucha una frase con el reconocimiento de voz de Android\..*?^    private fun beep\(\) \{', lambda _: voice_and_ai + '    private fun beep() {', s, count=1)
if count != 1:
    raise SystemExit("No se pudo sustituir el reconocimiento de voz")
service_path.write_text(s, encoding="utf-8")

# ── Pantalla: aspecto oscuro, estado individual de permisos y clave opcional.
main_path = root / "app/src/main/java/com/jarvis/personal/MainActivity.kt"
m = main_path.read_text(encoding="utf-8")
m = m.replace("private lateinit var status: TextView", "private lateinit var status: TextView" + chr(10) + "    private val permissionQueue = mutableListOf<String>()", 1)
permission_callback = r'''    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 100) {
            refresh()
            status.postDelayed({ requestNextQueuedPermission() }, 250)
        } else if (requestCode == 101) {
            refresh()
        }
    }'''
m, callback_count = re.subn(
    r'(?ms)^    override fun onRequestPermissionsResult\([^)]*\) \{.*?^    \}',
    lambda _: permission_callback, m, count=1
)
if callback_count != 1:
    raise SystemExit("No se encontró el callback existente para actualizar")
m = m.replace("import android.graphics.Color\n", "import android.graphics.Color\nimport android.graphics.drawable.GradientDrawable\n", 1)
m = m.replace('''        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad * 2, pad, pad)
        }''', '''        window.statusBarColor = Color.parseColor("#07111D")
        window.navigationBarColor = Color.parseColor("#07111D")
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad * 2, pad, pad)
            setBackgroundColor(Color.parseColor("#07111D"))
        }''', 1)
m = m.replace('''            gravity = Gravity.CENTER
            setPadding(0, 0, 0, pad)
        })''', '''            gravity = Gravity.CENTER
            setTextColor(Color.parseColor("#9AB1C5"))
            setPadding(0, 0, 0, pad)
        })''', 1)
m = m.replace('''        status = TextView(this).apply { textSize = 15f; setPadding(0, 0, 0, pad) }''', '''        status = TextView(this).apply {
            textSize = 14f
            setTextColor(Color.parseColor("#E5F1FA"))
            setPadding(0, 0, 0, pad)
        }''', 1)
m = m.replace('''        root.addView(countryInput)
        root.addView(button("Guardar código de país") {
            prefs().edit()
                .putString(JarvisService.PREF_COUNTRY, countryInput.text.toString().trim())
                .apply()
            Toast.makeText(this, "Guardado", Toast.LENGTH_SHORT).show()
        })
''', '''        root.addView(countryInput)
        root.addView(button("Guardar código de país") {
            prefs().edit()
                .putString(JarvisService.PREF_COUNTRY, countryInput.text.toString().trim())
                .apply()
            Toast.makeText(this, "Guardado", Toast.LENGTH_SHORT).show()
        })

        root.addView(TextView(this).apply {
            text = "Conversación online opcional (Gemini). Sin clave, Jarvis mantiene las órdenes y respuestas básicas offline. La clave se guarda solo en este teléfono; el plan gratuito tiene límites y Google puede usar sus solicitudes para mejorar sus productos."
            textSize = 13f
            setTextColor(Color.parseColor("#9AB1C5"))
        })
        val geminiInput = EditText(this).apply {
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            hint = "Clave opcional de Gemini API"
            setHintTextColor(Color.parseColor("#7890A5"))
            setTextColor(Color.parseColor("#E5F1FA"))
            setSingleLine(true)
            setText(prefs().getString(JarvisService.PREF_GEMINI_KEY, ""))
        }
        root.addView(geminiInput)
        root.addView(button("Guardar clave de Gemini") {
            prefs().edit().putString(JarvisService.PREF_GEMINI_KEY, geminiInput.text.toString().trim()).apply()
            Toast.makeText(this, "Clave guardada solo en este teléfono", Toast.LENGTH_LONG).show()
            refresh()
        })
        root.addView(button("Obtener clave opcional en Google AI Studio") {
            openSafely(Intent(Intent.ACTION_VIEW, Uri.parse("https://aistudio.google.com/apikey")))
        })
        root.addView(button("Configurar mi voz (necesario para usar Jarvis)") {
            if (JarvisService.running) stopService(Intent(this, JarvisService::class.java))
            openSafely(Intent(this, VoiceSetupActivity::class.java))
        })
''', 1)
m = m.replace('''        root.addView(TextView(this).apply {
            text = "\\nÓrdenes que entiende:\\n" +''', '''        root.addView(TextView(this).apply {
            setTextColor(Color.parseColor("#E5F1FA"))
            text = "\\nÓrdenes que entiende:\\n" +''', 1)
m = m.replace('''        root.addView(TextView(this).apply {
            text = "\\nCódigo de país para WhatsApp (ej. 54 Argentina, 52 México, 57 Colombia). " +''', '''        root.addView(TextView(this).apply {
            setTextColor(Color.parseColor("#E5F1FA"))
            text = "\\nCódigo de país para WhatsApp (ej. 54 Argentina, 52 México, 57 Colombia). " +''', 1)
m = m.replace('''            inputType = InputType.TYPE_CLASS_NUMBER
            hint = "54"
            setText(prefs().getString(JarvisService.PREF_COUNTRY, ""))''', '''            inputType = InputType.TYPE_CLASS_NUMBER
            hint = "57"
            setHintTextColor(Color.parseColor("#7890A5"))
            setTextColor(Color.parseColor("#E5F1FA"))
            setText(prefs().getString(JarvisService.PREF_COUNTRY, "57"))''', 1)
m = m.replace('''    private fun button(label: String, onClick: () -> Unit) = Button(this).apply {
        text = label
        isAllCaps = false
        setOnClickListener { onClick() }
    }''', '''    private fun button(label: String, onClick: () -> Unit) = Button(this).apply {
        text = label
        isAllCaps = false
        setTextColor(Color.parseColor("#E5F1FA"))
        background = GradientDrawable().apply {
            setColor(Color.parseColor("#172B3F"))
            cornerRadius = 18f
            setStroke(1, Color.parseColor("#2F4C63"))
        }
        setPadding(12, 4, 12, 4)
        setOnClickListener { onClick() }
    }''', 1)
m = re.sub(r'(?ms)^    private fun refresh\(\) \{.*?^    \}\n\n    private fun startJarvis\(\)', lambda _: r'''    private fun refresh() {
        val rows = runtimePermissions.map { permission ->
            val label = when (permission) {
                Manifest.permission.RECORD_AUDIO -> "Micrófono y escucha"
                Manifest.permission.CALL_PHONE -> "Realizar llamadas"
                Manifest.permission.READ_PHONE_STATE -> "Estado de llamadas"
                Manifest.permission.READ_CONTACTS -> "Leer contactos"
                Manifest.permission.SEND_SMS -> "Enviar SMS"
                Manifest.permission.POST_NOTIFICATIONS -> "Notificaciones"
                else -> permission
            }
            (if (granted(permission)) "✓  " else "○  ") + label
        }.toMutableList()
        val overlay = Settings.canDrawOverlays(this)
        val battery = getSystemService(PowerManager::class.java).isIgnoringBatteryOptimizations(packageName)
        rows += (if (overlay) "✓  " else "○  ") + "Abrir apps desde segundo plano"
        rows += (if (battery) "✓  " else "○  ") + "Sin restricción de batería"
        rows += (if (OwnerVoiceVerifier.isEnrolled(this)) "✓  " else "○  ") + "Voz del propietario registrada"
        rows += (if (prefs().getString(JarvisService.PREF_GEMINI_KEY, "").isNullOrBlank()) "○  " else "✓  ") + "IA online configurada"
        rows += ""
        rows += if (JarvisService.running) "● Jarvis está ESCUCHANDO" else "○ Jarvis está DETENIDO"
        status.text = rows.joinToString("\n")
    }

    private fun requestNextPermission() {
        permissionQueue.clear()
        permissionQueue.addAll(runtimePermissions.filter { !granted(it) })
        requestNextQueuedPermission()
    }

    private fun requestNextQueuedPermission() {
        while (permissionQueue.isNotEmpty() && granted(permissionQueue.first())) {
            permissionQueue.removeAt(0)
        }
        val next = if (permissionQueue.isEmpty()) null else permissionQueue.removeAt(0)
        if (next == null) {
            refresh()
            Toast.makeText(this, "Terminaste la revisión de permisos. Revisa los indicadores.", Toast.LENGTH_LONG).show()
        } else {
            requestPermissions(arrayOf(next), 100)
        }
    }

    private fun startJarvis()''', m, count=1)
m = m.replace('''            requestPermissions(runtimePermissions, 100)''', '''            requestNextPermission()''')
m = m.replace('''            requestPermissions(runtimePermissions, 100)
            return''', '''            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 100)
            return''')
# Make EditText fields readable against dark system panels.
m = m.replace('''            inputType = InputType.TYPE_CLASS_NUMBER
            hint = "54"''', '''            inputType = InputType.TYPE_CLASS_NUMBER
            hint = "57"
            setTextColor(Color.parseColor("#E5F1FA"))
            setHintTextColor(Color.parseColor("#7890A5"))''', 1)
main_path.write_text(m, encoding="utf-8")

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
    private const val MIN_VERIFY_SAMPLES = SAMPLE_RATE
    // Initial threshold; it must be tuned against real recordings on the target phone.
    private const val SIMILARITY_THRESHOLD = 0.74f
    @Volatile private var extractor: SpeakerEmbeddingExtractor? = null

    fun isEnrolled(context: Context): Boolean =
        !context.getSharedPreferences(STORE, Context.MODE_PRIVATE).getString(EMBEDDING_KEY, null).isNullOrBlank()

    fun clearEnrollment(context: Context) {
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
            val expected = SAMPLE_RATE * 5
            val pcm = FloatArray(expected)
            val buffer = ShortArray(1600)
            var written = 0
            val start = SystemClock.elapsedRealtime()
            while (written < expected && SystemClock.elapsedRealtime() - start < 7000) {
                val count = recorder.read(buffer, 0, minOf(buffer.size, expected - written))
                if (count > 0) {
                    for (i in 0 until count) pcm[written + i] = buffer[i] / 32768.0f
                    written += count
                }
            }
            if (written < SAMPLE_RATE * 3) null else embedding(context, pcm.copyOf(written))
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
        if (recordings.size < 3) return false
        val dimensions = recordings.first().size
        if (dimensions == 0 || recordings.any { it.size != dimensions }) return false
        val mean = FloatArray(dimensions) { i ->
            recordings.sumOf { it[i].toDouble() }.toFloat() / recordings.size
        }
        val normalized = normalize(mean) ?: return false
        val json = JSONArray()
        normalized.forEach { json.put(it.toDouble()) }
        return context.getSharedPreferences(STORE, Context.MODE_PRIVATE)
            .edit().putString(EMBEDDING_KEY, json.toString()).commit()
    }

    fun matches(context: Context, audio: FloatArray): Boolean {
        if (audio.size < MIN_VERIFY_SAMPLES) return false
        val raw = context.getSharedPreferences(STORE, Context.MODE_PRIVATE)
            .getString(EMBEDDING_KEY, null) ?: return false
        return try {
            val json = JSONArray(raw)
            val enrolled = FloatArray(json.length()) { json.getDouble(it).toFloat() }
            val candidate = embedding(context, audio) ?: return false
            if (candidate.size != enrolled.size) return false
            val score = cosine(enrolled, candidate)
            Log.d("JarvisVoice", "Coincidencia de voz: " + score)
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
            text = "Graba tres muestras de tu voz. En cada una habla de forma natural durante cinco segundos. El procesamiento es local y solo se guarda una representación numérica de la voz; no se guardan las grabaciones."
            textSize = 15f
            setTextColor(Color.parseColor("#AFC5D6"))
            setPadding(0, pad, 0, pad)
        })
        status = TextView(this).apply {
            text = "Muestras registradas: 0 de 3"
            textSize = 16f
            setTextColor(Color.parseColor("#E5F1FA"))
            setPadding(0, pad, 0, pad)
        }
        root.addView(status)
        recordButton = button("Grabar muestra 1 de 3") { recordOne() }
        root.addView(recordButton)
        root.addView(button("Borrar registro de voz") {
            OwnerVoiceVerifier.clearEnrollment(this)
            recordings.clear()
            status.text = "Registro borrado. Muestras: 0 de 3."
            recordButton.isEnabled = true
            recordButton.text = "Grabar muestra 1 de 3"
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
        status.text = "Grabando muestra " + (recordings.size + 1) + " de 3. Habla ahora durante cinco segundos."
        Thread {
            val result = OwnerVoiceVerifier.captureOwnerSample(this)
            runOnUiThread {
                busy = false
                recordButton.isEnabled = true
                if (result == null) {
                    status.text = "No pude obtener una muestra clara. Comprueba el micrófono y vuelve a intentarlo."
                    recordButton.text = "Reintentar muestra " + (recordings.size + 1) + " de 3"
                    return@runOnUiThread
                }
                recordings.add(result)
                if (recordings.size < 3) {
                    status.text = "Muestra guardada. Muestras registradas: " + recordings.size + " de 3. Continúa hablando con naturalidad."
                    recordButton.text = "Grabar muestra " + (recordings.size + 1) + " de 3"
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

# Internet is used only for the optional text conversation with Gemini.
manifest = root / "app/src/main/AndroidManifest.xml"
xml = manifest.read_text(encoding="utf-8")
if "android.permission.INTERNET" not in xml:
    xml = xml.replace('    <uses-permission android:name="android.permission.RECORD_AUDIO" />',
                      '    <uses-permission android:name="android.permission.INTERNET" />\n    <uses-permission android:name="android.permission.RECORD_AUDIO" />', 1)
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

print("Parche aplicado: imports Vosk, API local y panel/permisos.")
