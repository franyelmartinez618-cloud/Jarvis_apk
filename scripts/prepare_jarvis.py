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
s = replace_once(s, '        const val PREF_COUNTRY = "country_code"\n', '        const val PREF_COUNTRY = "country_code"\n        const val PREF_GEMINI_KEY = "gemini_api_key"\n', "preferencia Gemini")
s = replace_once(s, "    private var busy = false\n", "    private var busy = false\n    private val dialogueHistory = ArrayList<Pair<String, String>>()\n", "historial de conversación")

conversation = r'''    /** Una activación abre varios turnos; no exige repetir la frase en cada orden. */
    private suspend fun conversation() {
        updateNotification("Conversación activa: habla con Jarvis")
        beep()
        speak("A tus órdenes. Te escucho.")
        delay(200)
        var turns = 0
        while (running && turns < 8) {
            val heard = listen() ?: break
            val clean = heard.trim()
            if (clean.isBlank()) break
            Log.d(TAG, "Escuché: " + clean)
            turns++
            val command = Parser.parse(clean)
            handle(command)
            if (command == Cmd.Cancel) break
            delay(250)
        }
        if (turns == 0) speak("No te escuché. Cuando quieras, vuelve a decir Jarvis, activa.")
        else if (turns >= 8) speak("Dejo la conversación en espera. Di Jarvis, activa para volver a hablar.")
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
                val started = SystemClock.elapsedRealtime()
                while (SystemClock.elapsedRealtime() - started < 12_000 && running) {
                    val count = record.read(buffer, 0, buffer.size)
                    if (count <= 0) { delay(20); continue }
                    if (recognizer.acceptWaveForm(buffer, count)) {
                        val spoken = JSONObject(recognizer.getResult()).optString("text").trim()
                        if (spoken.isNotBlank()) return@withContext spoken
                    }
                }
                val finalText = JSONObject(recognizer.getFinalResult()).optString("text").trim()
                finalText.ifBlank { null }
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
            text = "\\nConversación online opcional (Gemini). Sin clave, Jarvis mantiene las órdenes y respuestas básicas offline. La clave se guarda solo en este teléfono; el plan gratuito tiene límites y Google puede usar sus solicitudes para mejorar sus productos."
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

print("Parche funcional aplicado: conversación por turnos, Vosk local, Gemini opcional, panel y permisos visibles.")
