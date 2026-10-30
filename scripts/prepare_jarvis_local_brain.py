from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
service_path = root / "app/src/main/java/com/jarvis/personal/JarvisService.kt"
main_path = root / "app/src/main/java/com/jarvis/personal/MainActivity.kt"
manifest_path = root / "app/src/main/AndroidManifest.xml"
app_gradle = root / "app/build.gradle.kts"
root_gradle = root / "build.gradle.kts"

# LiteRT-LM 0.18.x carries Kotlin 2.4 metadata and requires a Kotlin 2.3+ compiler.
root_text = root_gradle.read_text(encoding="utf-8")
root_text = root_text.replace('id("com.android.application") version "8.5.2"', 'id("com.android.application") version "8.13.2"')
root_text = root_text.replace('id("org.jetbrains.kotlin.android") version "1.9.24"', 'id("org.jetbrains.kotlin.android") version "2.3.0"')
if 'version "8.13.2"' not in root_text or 'version "2.3.0"' not in root_text:
    raise SystemExit("No se pudieron actualizar los plugins de Gradle para LiteRT-LM.")
root_gradle.write_text(root_text, encoding="utf-8")

gradle_text = app_gradle.read_text(encoding="utf-8")
dep = 'implementation("com.google.ai.edge.litertlm:litertlm-android:0.18.1")'
if dep not in gradle_text:
    gradle_text = gradle_text.replace(
        '    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")',
        '    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")\n    ' + dep
    )
if dep not in gradle_text:
    raise SystemExit("No se pudo añadir LiteRT-LM al módulo Android.")
legacy_kotlin_options = '    kotlinOptions {\n        jvmTarget = "17"\n    }\n'
gradle_text = gradle_text.replace(legacy_kotlin_options, "")
compiler_block = '''kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

'''
if "compilerOptions {" not in gradle_text:
    gradle_text = gradle_text.replace("dependencies {", compiler_block + "dependencies {", 1)
app_gradle.write_text(gradle_text, encoding="utf-8")

service = service_path.read_text(encoding="utf-8")
package_line = "package com.jarvis.personal\n"
imports = [
    "import android.app.ActivityManager",
    "import android.os.StatFs",
    "import android.provider.AlarmClock",
    "import android.provider.CalendarContract",
    "import android.provider.MediaStore",
    "import android.provider.ContactsContract",
    "import android.hardware.camera2.CameraCharacteristics",
    "import android.hardware.camera2.CameraManager",
    "import java.net.HttpURLConnection",
    "import java.net.URL",
    "import java.security.MessageDigest",
    "import com.google.ai.edge.litertlm.*",
    "import kotlinx.coroutines.flow.collect",
    "import kotlinx.coroutines.sync.Mutex",
    "import kotlinx.coroutines.sync.withLock",
]
for line in imports:
    if line + "\n" not in service:
        service = service.replace(package_line, package_line + line + "\n", 1)

service = service.replace(
    '        private const val SPEECH_LANG = "es-419"\n',
    '        private const val SPEECH_LANG = "es-419"\n'
    '        private const val BRAIN_URL = "https://huggingface.co/litert-community/Qwen3-1.7B/resolve/main/Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm"\n'
    '        private const val BRAIN_SHA256 = "2eeffef7b51bc3e1225ea69fe7aa5f417397934b56a5b6c20cc068d6fd2c918b"\n'
)
fields = (
    "    @Volatile private var brainLoading = false\n"
    "    @Volatile private var brainEngine: Engine? = null\n"
    "    @Volatile private var brainConversation: Conversation? = null\n"
    "    private val brainMutex = Mutex()\n"
    "    @Volatile private var pendingModelAction: PendingModelAction? = null\n"
    "    private data class PendingModelAction(val kind: String, val target: String, val body: String? = null)\n"
)
if "private var brainEngine: Engine?" not in service:
    service = service.replace("    private val dialogueHistory = ArrayList<Pair<String, String>>()\n",
                              "    private val dialogueHistory = ArrayList<Pair<String, String>>()\n" + fields, 1)

service = service.replace(
    "        try { model?.close() } catch (_: Exception) {}\n",
    "        try { brainConversation?.close() } catch (_: Exception) {}\n"
    "        try { brainEngine?.close() } catch (_: Exception) {}\n"
    "        try { model?.close() } catch (_: Exception) {}\n",
    1
)

# Initialize the LLM in parallel with the voice listener. The chat itself remains fully local.
wake_end = "        wake = WakeWordListener(m) { onWake() }.also { it.start() }\n"
if wake_end not in service:
    raise SystemExit("No se encontró el punto de arranque del detector de activación.")
service = service.replace(wake_end, wake_end + "        initializeLocalBrain()\n", 1)

# No superposición especial es requisito para abrir aplicaciones o pasar a WhatsApp. Android
# puede bloquear un salto iniciado desde segundo plano; en ese caso se deja una notificación tocable.
overlay_wa = '''        if (!Settings.canDrawOverlays(this)) {
            speak("Android bloquea abrir WhatsApp por voz cuando Jarvis está en segundo plano. Activa Mostrar sobre otras apps en los permisos de Jarvis.")
            return
        }
'''
service = service.replace(overlay_wa, "", 1)
overlay_app = '''        // Android limits opening activities from a foreground service on some versions.
        if (!Settings.canDrawOverlays(this)) {
            speak("Android puede bloquear la apertura de aplicaciones desde segundo plano. Activa Mostrar sobre otras apps en los permisos de Jarvis.")
            return
        }
'''
service = service.replace(overlay_app, "", 1)

# The existing deterministic command path now shares the same fuzzy launcher used by the model tools.
start = service.find("    private suspend fun doOpenApp(name: String) {")
end = service.find("    private suspend fun handleScreenCommand(raw: String): Boolean {", start)
if start < 0 or end < 0:
    raise SystemExit("No se encontró el método de apertura de apps para reemplazar.")
do_open = '''    private suspend fun doOpenApp(name: String) {
        speak(openAppFromModel(name))
    }

'''
service = service[:start] + do_open + service[end:]

# Expose a controlled set of real Android actions to the local model.
tool_methods = r'''    fun openAppFromModel(name: String): String {
        val q = strip(name).trim()
            .removePrefix("la app ").removePrefix("aplicacion de ")
            .removePrefix("aplicacion ").removePrefix("app ").trim()
        if (q.isBlank()) return "No se indicó el nombre de la aplicación."
        val pm = packageManager
        val launcher = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val aliases = mapOf(
            "cod" to listOf("call of duty", "call of duty mobile"),
            "call of duty" to listOf("call of duty mobile"),
            "free fair" to listOf("free fire", "free fire max"),
            "free fire" to listOf("free fire max"),
            "brawl star" to listOf("brawl stars"),
            "facebook" to listOf("facebook lite"),
            "instagram" to listOf("instagram lite")
        )
        val candidates = mutableListOf(q)
        aliases.forEach { (key, values) ->
            if (q == key || values.any { it == q }) {
                candidates.addAll(values)
                candidates.add(key)
            }
        }
        fun distance(a: String, b: String): Int {
            var previous = IntArray(b.length + 1) { it }
            for (i in a.indices) {
                val current = IntArray(b.length + 1)
                current[0] = i + 1
                for (j in b.indices) {
                    val cost = if (a[i] == b[j]) 0 else 1
                    current[j + 1] = minOf(current[j] + 1, previous[j + 1] + 1, previous[j] + cost)
                }
                previous = current
            }
            return previous[b.length]
        }
        val match = pm.queryIntentActivities(launcher, 0).mapNotNull { info ->
            val label = strip(info.loadLabel(pm).toString()).trim()
            var score = 0
            for (candidate in candidates) {
                val left = candidate.replace(" ", "")
                val right = label.replace(" ", "")
                val candidateScore = when {
                    left == right -> 120
                    right.startsWith(left) -> 110
                    right.contains(left) -> 105
                    else -> {
                        val d = distance(left, right)
                        if (d <= if (left.length <= 8) 2 else 3) 80 - d * 10 else 0
                    }
                }
                score = maxOf(score, candidateScore)
            }
            if (score == 0) null else info to score
        }.maxByOrNull { it.second }?.first
        if (match == null) return "No encontré una aplicación instalada que coincida con «" + name + "»."
        val launch = pm.getLaunchIntentForPackage(match.activityInfo.packageName)
            ?: return "Android no ofrece un acceso directo para " + match.loadLabel(pm) + "."
        val label = match.loadLabel(pm).toString()
        try {
            launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            startActivity(launch)
            return "He abierto " + label + "."
        } catch (e: Exception) {
            Log.w(TAG, "Android bloqueó el inicio directo de " + label, e)
            try {
                val pending = PendingIntent.getActivity(
                    this, match.activityInfo.packageName.hashCode(), launch,
                    PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
                )
                val notice = Notification.Builder(this, CHANNEL_ID)
                    .setSmallIcon(R.drawable.ic_launcher)
                    .setContentTitle("JARVIS · Abrir " + label)
                    .setContentText("Android requiere que toques esta notificación para abrir la aplicación.")
                    .setContentIntent(pending)
                    .setAutoCancel(true)
                    .build()
                getSystemService(NotificationManager::class.java).notify(42, notice)
                return "Android no permitió abrirla directamente desde segundo plano. Dejé una notificación; tócala para abrir " + label + "."
            } catch (notifyError: Exception) {
                Log.e(TAG, "No se pudo crear la notificación de apertura", notifyError)
                return "Android bloqueó la apertura de " + label + ". Trae Jarvis al frente y repite la orden."
            }
        }
    }

    fun listInstalledAppsForModel(): List<String> {
        val launcher = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        return packageManager.queryIntentActivities(launcher, 0)
            .map { it.loadLabel(packageManager).toString() }
            .distinct()
            .sorted()
            .take(120)
    }

    fun findContactsForModel(query: String): List<String> {
        if (!has(Manifest.permission.READ_CONTACTS)) return listOf("PERMISO_PENDIENTE: READ_CONTACTS. Abre Jarvis y concede Contactos.")
        return try {
            Contacts.find(this, query).take(6).map { it.name + " · " + it.number }
        } catch (e: Exception) {
            Log.e(TAG, "Búsqueda de contactos falló", e)
            listOf("No pude consultar los contactos.")
        }
    }

    fun queueCallFromModel(contactName: String): String {
        if (!has(Manifest.permission.READ_CONTACTS) || !has(Manifest.permission.CALL_PHONE)) {
            return "PERMISO_PENDIENTE: Jarvis necesita Contactos y Llamadas. Debe solicitarlos desde la pantalla principal."
        }
        pendingModelAction = PendingModelAction("call", contactName)
        return "Solicitud preparada. Antes de llamar, Jarvis resolverá el contacto y pedirá confirmación hablada."
    }

    fun queueWhatsAppFromModel(contactName: String, message: String): String {
        if (!has(Manifest.permission.READ_CONTACTS)) {
            return "PERMISO_PENDIENTE: Jarvis necesita Contactos."
        }
        if (contactName.isBlank() || message.isBlank()) return "Falta el contacto o el contenido del mensaje."
        pendingModelAction = PendingModelAction("whatsapp", contactName, message)
        return "Mensaje preparado. Jarvis mostrará el contacto y el texto y pedirá confirmación hablada antes de abrir WhatsApp."
    }

    fun queueSmsFromModel(contactName: String, message: String): String {
        if (!has(Manifest.permission.READ_CONTACTS) || !has(Manifest.permission.SEND_SMS)) {
            return "PERMISO_PENDIENTE: Jarvis necesita Contactos y SMS."
        }
        if (contactName.isBlank() || message.isBlank()) return "Falta el contacto o el contenido del SMS."
        pendingModelAction = PendingModelAction("sms", contactName, message)
        return "SMS preparado. Antes de enviarlo, Jarvis mostrará el contacto y el texto y pedirá confirmación hablada."
    }

    fun createContactForModel(name: String, phone: String): String {
        if (name.isBlank() || phone.isBlank()) return "Falta el nombre o el número del contacto."
        return try {
            val intent = Intent(Intent.ACTION_INSERT, ContactsContract.Contacts.CONTENT_URI)
                .putExtra(ContactsContract.Intents.Insert.NAME, name)
                .putExtra(ContactsContract.Intents.Insert.PHONE, phone)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            startActivity(intent)
            "Abrí el formulario para guardar el contacto " + name + ". Revisa los datos y pulsa Guardar."
        } catch (e: Exception) {
            Log.e(TAG, "No se pudo abrir el editor de contactos", e)
            "No pude abrir el formulario de contactos."
        }
    }

    fun readVisibleScreenForModel(): String {
        return JarvisAccessibilityService.readScreen()
            ?: "ACCESIBILIDAD_PENDIENTE: activa Control de pantalla de Jarvis en Ajustes > Accesibilidad."
    }

    fun scrollScreenForModel(direction: String): String {
        if (!JarvisAccessibilityService.isConnected()) return "ACCESIBILIDAD_PENDIENTE: activa Control de pantalla de Jarvis."
        val forward = strip(direction) !in listOf("arriba", "up", "retroceder", "back")
        return if (JarvisAccessibilityService.scroll(forward)) "Desplazamiento realizado." else "No encontré un área desplazable."
    }

    fun tapVisibleControlForModel(target: String): String {
        if (!JarvisAccessibilityService.isConnected()) return "ACCESIBILIDAD_PENDIENTE: activa Control de pantalla de Jarvis."
        if (target.isBlank()) return "Falta indicar el texto del control."
        val risky = Regex("\\\\b(enviar|send|publicar|postear|pagar|pago|comprar|eliminar|borrar|delete|transferir|confirmar compra|finalizar compra)\\\\b")
            .containsMatchIn(strip(target))
        if (risky) {
            pendingSensitiveUiTarget = target
            return "ACCIÓN PENDIENTE DE CONFIRMACIÓN: se necesita que el usuario diga «confirma acción» antes de pulsar «" + target + "»."
        }
        return if (JarvisAccessibilityService.clickByText(target)) "Pulsé «" + target + "»."
        else "No encontré un control visible llamado «" + target + "»."
    }

    fun typeIntoScreenForModel(text: String): String {
        if (!JarvisAccessibilityService.isConnected()) return "ACCESIBILIDAD_PENDIENTE: activa Control de pantalla de Jarvis."
        if (text.length > 2000) return "El texto es demasiado largo; limita la entrada a 2000 caracteres."
        return if (JarvisAccessibilityService.typeIntoFocusedField(text)) "Texto escrito en el campo activo."
        else "No encontré un campo de texto activo. El usuario debe seleccionar primero el campo."
    }

    fun searchWebForModel(query: String): String {
        if (query.isBlank()) return "Falta el texto que quieres buscar."
        return try {
            val uri = Uri.parse("https://www.google.com/search?q=" + URLEncoder.encode(query, "UTF-8"))
            startActivity(Intent(Intent.ACTION_VIEW, uri).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            "Abrí una búsqueda web para: " + query
        } catch (e: Exception) {
            Log.e(TAG, "No se pudo abrir búsqueda web", e)
            "Android no permitió abrir el navegador."
        }
    }

    fun openSettingsForModel(section: String): String {
        val normalized = strip(section)
        val intent = when {
            normalized.contains("accesibilidad") || normalized.contains("pantalla") ->
                Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
            normalized.contains("sobre otras") || normalized.contains("superposicion") || normalized.contains("ventana") ->
                Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:" + packageName))
            normalized.contains("bateria") || normalized.contains("segundo plano") ->
                Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:" + packageName))
            normalized.contains("wifi") || normalized.contains("internet") ->
                Intent(Settings.ACTION_WIFI_SETTINGS)
            normalized.contains("bluetooth") ->
                Intent(Settings.ACTION_BLUETOOTH_SETTINGS)
            normalized.contains("brillo") || normalized.contains("ajustes del sistema") ->
                Intent(Settings.ACTION_MANAGE_WRITE_SETTINGS, Uri.parse("package:" + packageName))
            normalized.contains("notificacion") ->
                Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, packageName)
            else -> Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + packageName))
        }
        return try {
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            startActivity(intent)
            "Abrí los ajustes de Android solicitados. El usuario debe activar el permiso en la pantalla del sistema."
        } catch (e: Exception) {
            Log.e(TAG, "No pude abrir ajustes de Android", e)
            "Android no permitió abrir esos ajustes."
        }
    }

    private suspend fun runPendingModelAction() {
        val pending = pendingModelAction ?: return
        pendingModelAction = null
        when (pending.kind) {
            "call" -> doCall(pending.target)
            "whatsapp" -> doMessage(Cmd.Message(Via.WHATSAPP, pending.target, pending.body))
            "sms" -> doMessage(Cmd.Message(Via.SMS, pending.target, pending.body))
        }
    }

'''
if "fun openAppFromModel(" not in service:
    service = service.replace("    private suspend fun handleScreenCommand(raw: String): Boolean {", tool_methods + "    private suspend fun handleScreenCommand(raw: String): Boolean {", 1)

# Add the download, integrity check and on-device conversation engine.
brain_methods = r'''    private fun initializeLocalBrain() {
        if (brainLoading || brainConversation != null) return
        brainLoading = true
        scope.launch {
            var createdEngine: Engine? = null
            try {
                updateNotification("Preparando el cerebro local de Jarvis")
                val modelFile = withContext(Dispatchers.IO) { ensureLocalBrainModel() }
                updateNotification("Inicializando cerebro local · Qwen3")
                val activityManager = getSystemService(ActivityManager::class.java)
                val memory = ActivityManager.MemoryInfo().also { activityManager.getMemoryInfo(it) }
                try {
                    createdEngine = Engine(
                        EngineConfig(modelPath = modelFile.absolutePath, backend = Backend.GPU(), cacheDir = cacheDir.absolutePath)
                    )
                    withContext(Dispatchers.IO) { createdEngine!!.initialize() }
                } catch (gpuError: Exception) {
                    try { createdEngine?.close() } catch (_: Exception) {}
                    createdEngine = null
                    Log.w(TAG, "GPU no disponible para el modelo local; evaluando CPU", gpuError)
                    if (memory.availMem < 3_000_000_000L) {
                        throw IllegalStateException("El motor GPU no está disponible y la memoria libre no alcanza para el modo CPU.")
                    }
                    createdEngine = Engine(
                        EngineConfig(modelPath = modelFile.absolutePath, backend = Backend.CPU(), cacheDir = cacheDir.absolutePath)
                    )
                    withContext(Dispatchers.IO) { createdEngine!!.initialize() }
                }
                val config = ConversationConfig(
                    systemInstruction = Contents.of(
                        "Eres JARVIS, un asistente personal de voz en español latino, natural, atento, directo y conversacional. " +
                        "Habla como un asistente humano competente, no como un menú ni como un chatbot rígido. " +
                        "Comprende frases coloquiales, errores leves de transcripción y peticiones expresadas de muchas maneras. " +
                        "Usa las herramientas disponibles cuando el usuario pida una acción real; no afirmes que la ejecutaste hasta recibir el resultado de la herramienta. " +
                        "Para llamadas y mensajes solicita confirmación hablada; nunca envíes, llames, pagues, borres o publiques sin confirmación explícita. " +
                        "Si un permiso está pendiente, explica exactamente cuál falta y cómo habilitarlo. Si Android bloquea una acción, dilo y ofrece el siguiente paso posible. " +
                        "No inventes que tienes acceso a una aplicación, archivo o dato que no te entregó una herramienta. " +
                        "Mantén las respuestas orales breves, normalmente una o dos frases, y continúa la conversación con naturalidad. " +
                        "Tu motor es local; no envías conversaciones a una IA remota."
                    ),
                    tools = listOf(tool(JarvisTools(this@JarvisService))),
                    samplerConfig = SamplerConfig(topK = 20, topP = 0.9, temperature = 0.65),
                    maxOutputToken = 512
                )
                val conversation = createdEngine!!.createConversation(config)
                brainEngine = createdEngine
                brainConversation = conversation
                createdEngine = null
                updateNotification("Cerebro local activo · escucha por voz")
                Log.i(TAG, "Cerebro local Qwen3 inicializado correctamente")
            } catch (e: Exception) {
                Log.e(TAG, "No se pudo inicializar el cerebro local", e)
                updateNotification("Cerebro local no disponible · abre Jarvis para revisar")
            } finally {
                try { createdEngine?.close() } catch (_: Exception) {}
                brainLoading = false
            }
        }
    }

    private fun ensureLocalBrainModel(): File {
        val target = File(noBackupFilesDir, "jarvis-brain-qwen3-1.7b.litertlm")
        val marker = File(noBackupFilesDir, "jarvis-brain-qwen3-1.7b.sha256")
        if (target.exists() && target.length() > 900_000_000L && marker.exists() &&
            marker.readText().trim() == BRAIN_SHA256) return target

        val available = StatFs(noBackupFilesDir.absolutePath).availableBytes
        if (available < 1_200_000_000L) {
            throw IllegalStateException("Se necesita al menos 1.2 GB libres para descargar el cerebro local.")
        }

        val temp = File(noBackupFilesDir, "jarvis-brain-qwen3-1.7b.download")
        if (temp.exists()) temp.delete()
        val connection = (URL(BRAIN_URL).openConnection() as HttpURLConnection).apply {
            instanceFollowRedirects = true
            requestMethod = "GET"
            connectTimeout = 20000
            readTimeout = 90000
            setRequestProperty("User-Agent", "JarvisAndroid-LocalModel")
            setRequestProperty("Accept", "application/octet-stream")
        }
        try {
            val response = connection.responseCode
            if (response !in 200..299) throw IllegalStateException("Descarga del cerebro local: HTTP " + response)
            val expected = connection.contentLengthLong
            if (expected > 0 && expected < 900_000_000L) {
                throw IllegalStateException("El archivo descargado es demasiado pequeño para ser el modelo esperado.")
            }
            var copied = 0L
            var lastReported = -1
            connection.inputStream.buffered().use { input ->
                FileOutputStream(temp).buffered().use { output ->
                    val buffer = ByteArray(1024 * 1024)
                    while (true) {
                        val count = input.read(buffer)
                        if (count < 0) break
                        output.write(buffer, 0, count)
                        copied += count
                        if (copied - lastReported >= 20L * 1024L * 1024L) {
                            lastReported = copied.toInt()
                            val percent = if (expected > 0) ((copied * 100L) / expected).toInt().coerceIn(0, 99) else -1
                            updateNotification(if (percent >= 0) "Descargando cerebro local · " + percent + "%"
                                else "Descargando cerebro local · " + (copied / 1_000_000L) + " MB")
                        }
                    }
                    output.flush()
                }
            }
            if (temp.length() < 900_000_000L) {
                throw IllegalStateException("La descarga del modelo quedó incompleta.")
            }
            updateNotification("Verificando integridad del cerebro local")
            val digest = MessageDigest.getInstance("SHA-256")
            temp.inputStream().buffered().use { input ->
                val buffer = ByteArray(1024 * 1024)
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    digest.update(buffer, 0, count)
                }
            }
            val actual = digest.digest().joinToString("") { "%02x".format(it) }
            if (actual != BRAIN_SHA256) {
                throw IllegalStateException("La verificación SHA-256 del modelo falló; no se cargó un archivo alterado.")
            }
            if (target.exists()) target.delete()
            if (!temp.renameTo(target)) throw IllegalStateException("No se pudo guardar el modelo local.")
            marker.writeText(BRAIN_SHA256)
            return target
        } catch (e: Exception) {
            try { temp.delete() } catch (_: Exception) {}
            throw e
        } finally {
            connection.disconnect()
        }
    }

'''
if "private fun initializeLocalBrain()" not in service:
    service = service.replace("    private suspend fun respondNaturally(input: String) {", brain_methods + "    private suspend fun respondNaturally(input: String) {", 1)

# Replace the hard-coded localReply responses with a real on-device LLM.
start = service.find("    private suspend fun respondNaturally(input: String) {")
end = service.find("    private fun beep() {", start)
if start < 0 or end < 0:
    raise SystemExit("No se encontró el motor de respuestas fijas para sustituir.")
phone_command_router = r'''    private fun spanishNumber(token: String): Int? {
        token.toIntOrNull()?.let { return it }
        return when (strip(token).trim()) {
            "uno", "una" -> 1
            "dos" -> 2
            "tres" -> 3
            "cuatro" -> 4
            "cinco" -> 5
            "seis" -> 6
            "siete" -> 7
            "ocho" -> 8
            "nueve" -> 9
            "diez" -> 10
            "once" -> 11
            "doce" -> 12
            "trece" -> 13
            "catorce" -> 14
            "quince" -> 15
            "dieciseis" -> 16
            "diecisiete" -> 17
            "dieciocho" -> 18
            "diecinueve" -> 19
            "veinte" -> 20
            "veintiuno" -> 21
            "veintidos" -> 22
            "veintitres" -> 23
            "veinticuatro" -> 24
            "veinticinco" -> 25
            "veintiseis" -> 26
            "veintisiete" -> 27
            "veintiocho" -> 28
            "veintinueve" -> 29
            "treinta" -> 30
            "cuarenta" -> 40
            "cincuenta" -> 50
            else -> null
        }
    }

    private suspend fun runNaturalPhoneAction(raw: String): Boolean {
        val text = strip(raw).lowercase().replace(Regex("[¿?¡!.,;]"), " ").trim()
        if (text.isBlank()) return false

        // Camera and flashlight.
        if (Regex("\\b(abre|abrir|inicia|iniciar|enciende|abreme)\\b.*\\b(camara|camara del telefono)\\b").containsMatchIn(text) ||
            Regex("\\b(toma|saca|haz)\\s+(una\\s+)?foto\\b").containsMatchIn(text)) {
            speak(openCameraForModel())
            return true
        }
        if (Regex("\\b(enciende|prende|activa)\\b.*\\b(linterna|flash)\\b").containsMatchIn(text)) {
            speak(setTorchForModel(true))
            return true
        }
        if (Regex("\\b(apaga|desactiva)\\b.*\\b(linterna|flash)\\b").containsMatchIn(text)) {
            speak(setTorchForModel(false))
            return true
        }

        // Alarm and timer, supporting digits and common spoken Spanish numbers.
        if (Regex("\\b(temporizador|temporizador de cuenta regresiva|cuenta regresiva|cronometro)\\b").containsMatchIn(text) ||
            Regex("\\bpon (un )?timer\\b").containsMatchIn(text)) {
            val amount = Regex("(\\d+|uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|quince|veinte|treinta)\\s*(segundos?|secs?|minutos?|mins?|horas?)")
                .find(text)
            val number = amount?.let { spanishNumber(it.groupValues[1]) }
            val unit = amount?.groupValues?.get(2).orEmpty()
            if (number == null) {
                speak("¿Cuánto debe durar el temporizador?")
                return true
            }
            val seconds = when {
                unit.startsWith("hora") -> number * 3600
                unit.startsWith("min") -> number * 60
                else -> number
            }
            speak(setTimerForModel(seconds, "JARVIS"))
            return true
        }

        if (Regex("\\b(alarma|despertador)\\b").containsMatchIn(text) &&
            Regex("\\b(pon|ponme|crea|crear|configura|programa|despiertame)\\b").containsMatchIn(text)) {
            val match = Regex("(?:a las|para las|a la)\\s+(\\d{1,2}|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce)(?:\\s*(?::|y)\\s*(\\d{1,2}|media|cuarto))?")
                .find(text)
            val hour = match?.let { spanishNumber(it.groupValues[1]) }
            if (hour == null || hour !in 0..23) {
                speak("¿A qué hora quieres la alarma? Dime, por ejemplo, a las siete y media.")
                return true
            }
            val minuteToken = match.groupValues.getOrNull(2).orEmpty()
            val minute = when (minuteToken) {
                "media" -> 30
                "cuarto" -> 15
                else -> minuteToken.toIntOrNull() ?: 0
            }
            var adjustedHour = hour
            if (Regex("\\b(tarde|noche|pm)\\b").containsMatchIn(text) && adjustedHour in 1..11) adjustedHour += 12
            if (Regex("\\b(mananas|manana|am)\\b").containsMatchIn(text) && adjustedHour == 12) adjustedHour = 0
            speak(setAlarmForModel(adjustedHour, minute, "JARVIS"))
            return true
        }

        // Maps and web searches.
        val mapMatch = Regex("^(?:como llegar a|navega(?:r)? a|llevame a|busca(?:r)?|encuentra)\\s+(.+?)\\s+(?:en|con)\\s+(?:google )?(?:maps|mapas)$")
            .find(text)
        if (mapMatch != null) {
            speak(openMapsForModel(mapMatch.groupValues[1].trim()))
            return true
        }
        val destination = Regex("^(?:como llegar a|navega(?:r)? a|llevame a|abre el mapa para)\\s+(.+)$").find(text)
        if (destination != null) {
            speak(openMapsForModel(destination.groupValues[1].trim()))
            return true
        }
        val search = Regex("^(?:busca|buscar|buscame|investiga|consulta)\\s+(.+?)(?:\\s+en\\s+(?:google|internet|la web|web))?$")
            .find(text)
        if (search != null) {
            speak(searchWebForModel(search.groupValues[1].trim()))
            return true
        }

        // Device controls.
        val percent = Regex("(?:al|a|en)\\s*(\\d{1,3})\\s*(?:por ciento|%)?").find(text)?.groupValues?.get(1)?.toIntOrNull()
        if (Regex("\\b(volumen|audio)\\b").containsMatchIn(text) &&
            Regex("\\b(pon|sube|baja|ajusta|ajustar|cambia|establece)\\b").containsMatchIn(text)) {
            val value = percent ?: when {
                Regex("\\b(sube|aumenta)\\b").containsMatchIn(text) -> 75
                Regex("\\b(baja|disminuye)\\b").containsMatchIn(text) -> 25
                else -> null
            }
            if (value != null) {
                speak(setMediaVolumeForModel(value))
                return true
            }
        }
        if (Regex("\\b(brillo|iluminacion de pantalla)\\b").containsMatchIn(text) &&
            Regex("\\b(pon|sube|baja|ajusta|cambia|establece)\\b").containsMatchIn(text)) {
            if (percent != null) {
                speak(setScreenBrightnessForModel(percent))
                return true
            }
            speak("¿A qué porcentaje quieres el brillo?")
            return true
        }
        val setting = when {
            Regex("\\b(wifi|wi fi|red inalambrica)\\b").containsMatchIn(text) -> "wifi"
            Regex("\\b(bluetooth)\\b").containsMatchIn(text) -> "bluetooth"
            Regex("\\b(accesibilidad|control de pantalla)\\b").containsMatchIn(text) -> "accesibilidad"
            Regex("\\b(sobre otras aplicaciones|superposicion|ventanas flotantes)\\b").containsMatchIn(text) -> "superposicion"
            Regex("\\b(bateria|ahorro de energia)\\b").containsMatchIn(text) -> "bateria"
            Regex("\\b(ajustes|configuracion|permisos)\\b").containsMatchIn(text) -> "app"
            else -> null
        }
        if (setting != null && Regex("\\b(ajustes|configuracion|abre|abrir|activa|activar|permiso)\\b").containsMatchIn(text)) {
            speak(openSettingsForModel(setting))
            return true
        }

        // Open arbitrary apps even when the user says "arranca", "ejecuta" or "ponme".
        val app = Regex("^(?:por favor )?(?:abre|abrime|abrir|inicia|iniciar|ejecuta|ejecutar|lanza|arranca|ponme|quiero abrir)\\s+(?:la app |la aplicacion |aplicacion |app |el juego |el )?(.+)$")
            .find(text)
        if (app != null) {
            speak(openAppFromModel(app.groupValues[1].trim()))
            return true
        }
        return false
    }

'''
if "private suspend fun runNaturalPhoneAction(" not in service:
    service = service.replace("    private suspend fun respondNaturally(input: String) {", phone_command_router + "    private suspend fun respondNaturally(input: String) {", 1)

respond = r'''    private suspend fun respondNaturally(input: String) {
        if (runNaturalPhoneAction(input)) return
        val conversation = brainConversation
        if (conversation == null) {
            val message = if (brainLoading) {
                "Estoy descargando y preparando mi cerebro local. La descarga es grande; te avisaré cuando esté listo. Mientras tanto, puedo ejecutar las órdenes básicas que ya tengo instaladas."
            } else {
                "Mi cerebro local no ha podido iniciarse. Abre Jarvis y revisa el espacio libre, la conexión inicial o la memoria disponible del teléfono."
            }
            speak(message)
            return
        }
        val output = StringBuilder()
        try {
            brainMutex.withLock {
                withContext(Dispatchers.IO) {
                    conversation.sendMessageAsync(input).collect { piece ->
                        output.append(piece.toString())
                    }
                }
            }
            val answer = output.toString().trim()
            val finalText = if (answer.isNotBlank()) answer.take(1800)
                else "Te escuché, pero no pude formular una respuesta. Dímelo de otra manera."
            dialogueHistory.add("user" to input.take(500))
            dialogueHistory.add("jarvis" to finalText.take(700))
            while (dialogueHistory.size > 12) dialogueHistory.removeAt(0)
            speak(finalText)
            runPendingModelAction()
        } catch (e: Exception) {
            Log.e(TAG, "Falló la conversación con el cerebro local", e)
            speak("Tuve un problema al procesar eso localmente. Puedes repetirlo.")
        }
    }

'''
# Recompute after inserting the router; the earlier offsets no longer match the modified source.
start = service.find("    private suspend fun respondNaturally(input: String) {")
end = service.find("    private fun beep() {", start)
if start < 0 or end < 0:
    raise SystemExit("No se pudo aislar la respuesta fija anterior.")
service = service[:start] + respond + service[end:]

# If the Vosk service starts but the LLM is still loading, keep the voice path available and retry.
# The notification is updated when the local brain becomes ready.
service_path.write_text(service, encoding="utf-8")

phone_action_methods = r'''    fun setAlarmForModel(hour: Int, minute: Int, label: String): String {
        if (hour !in 0..23 || minute !in 0..59) return "La hora de la alarma no es válida."
        return try {
            val intent = Intent(AlarmClock.ACTION_SET_ALARM)
                .putExtra(AlarmClock.EXTRA_HOUR, hour)
                .putExtra(AlarmClock.EXTRA_MINUTES, minute)
                .putExtra(AlarmClock.EXTRA_MESSAGE, label.ifBlank { "JARVIS" })
                .putExtra(AlarmClock.EXTRA_SKIP_UI, false)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            startActivity(intent)
            "Abrí el reloj con una alarma para las " + "%02d:%02d".format(hour, minute) + ". Confirma y guarda la alarma allí."
        } catch (e: Exception) {
            Log.e(TAG, "No se pudo abrir la alarma", e)
            "No encontré una aplicación de reloj compatible."
        }
    }

    fun setTimerForModel(seconds: Int, label: String): String {
        if (seconds !in 1..86400) return "El temporizador debe durar entre un segundo y 24 horas."
        return try {
            val intent = Intent(AlarmClock.ACTION_SET_TIMER)
                .putExtra(AlarmClock.EXTRA_LENGTH, seconds)
                .putExtra(AlarmClock.EXTRA_MESSAGE, label.ifBlank { "JARVIS" })
                .putExtra(AlarmClock.EXTRA_SKIP_UI, false)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            startActivity(intent)
            "Abrí el temporizador por " + seconds + " segundos. Confirma el inicio en el reloj."
        } catch (e: Exception) {
            Log.e(TAG, "No se pudo abrir el temporizador", e)
            "No encontré una aplicación de reloj compatible."
        }
    }

    fun openCameraForModel(): String = try {
        startActivity(Intent(MediaStore.ACTION_IMAGE_CAPTURE).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        "Abrí la cámara."
    } catch (e: Exception) {
        Log.e(TAG, "No se pudo abrir la cámara", e)
        "No encontré una aplicación de cámara compatible."
    }

    fun openMapsForModel(place: String): String {
        if (place.isBlank()) return "Dime el lugar o la dirección que buscas."
        return try {
            val uri = Uri.parse("geo:0,0?q=" + URLEncoder.encode(place, "UTF-8"))
            startActivity(Intent(Intent.ACTION_VIEW, uri).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            "Abrí el mapa para buscar " + place + "."
        } catch (e: Exception) {
            Log.e(TAG, "No se pudo abrir el mapa", e)
            "No pude abrir una aplicación de mapas."
        }
    }

    fun createCalendarEventForModel(title: String, minutesFromNow: Int, durationMinutes: Int, note: String): String {
        if (title.isBlank()) return "Falta el título del evento."
        if (minutesFromNow !in 0..525600 || durationMinutes !in 1..1440) return "La fecha o la duración no es válida."
        return try {
            val begin = System.currentTimeMillis() + minutesFromNow.toLong() * 60_000L
            val end = begin + durationMinutes.toLong() * 60_000L
            val intent = Intent(Intent.ACTION_INSERT, CalendarContract.Events.CONTENT_URI)
                .putExtra(CalendarContract.Events.TITLE, title)
                .putExtra(CalendarContract.Events.DESCRIPTION, note)
                .putExtra(CalendarContract.EXTRA_EVENT_BEGIN_TIME, begin)
                .putExtra(CalendarContract.EXTRA_EVENT_END_TIME, end)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            startActivity(intent)
            "Abrí el calendario con el evento «" + title + "». Revisa la fecha y pulsa Guardar."
        } catch (e: Exception) {
            Log.e(TAG, "No se pudo crear el evento", e)
            "No encontré una aplicación de calendario compatible."
        }
    }

    fun setMediaVolumeForModel(percent: Int): String {
        if (percent !in 0..100) return "El volumen debe estar entre cero y cien por ciento."
        return try {
            val audio = getSystemService(AudioManager::class.java)
            val maximum = audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
            val value = (maximum * percent / 100f).toInt().coerceIn(0, maximum)
            audio.setStreamVolume(AudioManager.STREAM_MUSIC, value, AudioManager.FLAG_SHOW_UI)
            "Ajusté el volumen multimedia al " + percent + " por ciento."
        } catch (e: Exception) {
            Log.e(TAG, "No se pudo cambiar el volumen", e)
            "Android no permitió modificar el volumen."
        }
    }

    fun setTorchForModel(enabled: Boolean): String {
        if (!has(Manifest.permission.CAMERA)) return "PERMISO_PENDIENTE: activa Cámara para poder controlar la linterna."
        return try {
            val camera = getSystemService(CameraManager::class.java)
            val id = camera.cameraIdList.firstOrNull {
                camera.getCameraCharacteristics(it).get(CameraCharacteristics.FLASH_INFO_AVAILABLE) == true
            } ?: return "Este teléfono no informa de un flash compatible."
            camera.setTorchMode(id, enabled)
            if (enabled) "Encendí la linterna." else "Apagué la linterna."
        } catch (e: Exception) {
            Log.e(TAG, "No se pudo controlar la linterna", e)
            "Android no permitió controlar la linterna. Comprueba el permiso de cámara."
        }
    }

    fun setScreenBrightnessForModel(percent: Int): String {
        if (percent !in 1..100) return "El brillo debe estar entre uno y cien por ciento."
        if (!Settings.System.canWrite(this)) {
            return try {
                startActivity(Intent(Settings.ACTION_MANAGE_WRITE_SETTINGS, Uri.parse("package:" + packageName))
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                "Android abrió el permiso Modificar ajustes del sistema. Actívalo y vuelve a pedirme el brillo."
            } catch (e: Exception) {
                "Abre Ajustes de Jarvis y permite Modificar ajustes del sistema."
            }
        }
        return try {
            Settings.System.putInt(contentResolver, Settings.System.SCREEN_BRIGHTNESS_MODE, Settings.System.SCREEN_BRIGHTNESS_MODE_MANUAL)
            Settings.System.putInt(contentResolver, Settings.System.SCREEN_BRIGHTNESS, (percent * 255 / 100).coerceIn(1, 255))
            "Ajusté el brillo de la pantalla al " + percent + " por ciento."
        } catch (e: Exception) {
            Log.e(TAG, "No se pudo ajustar el brillo", e)
            "Android no permitió cambiar el brillo."
        }
    }

'''
if "fun setAlarmForModel(" not in service:
    service = service.replace("    private suspend fun runPendingModelAction() {", phone_action_methods + "    private suspend fun runPendingModelAction() {", 1)

# Add the local tool bridge. Sensitive actions are queued and the existing call/message confirmation flow handles them.
tools_path = root / "app/src/main/java/com/jarvis/personal/JarvisTools.kt"
tools_path.write_text(r'''package com.jarvis.personal

import com.google.ai.edge.litertlm.Tool
import com.google.ai.edge.litertlm.ToolParam
import com.google.ai.edge.litertlm.ToolSet

class JarvisTools(private val service: JarvisService) : ToolSet {

    @Tool(description = "Open an Android app already installed on the phone. Use the app's familiar name; the system resolves approximate spellings.")
    fun openApplication(
        @ToolParam(description = "Installed application name, such as WhatsApp, Free Fire, YouTube or Settings.") applicationName: String
    ): String = service.openAppFromModel(applicationName)

    @Tool(description = "List installed applications visible to Android's launcher.")
    fun listInstalledApplications(): List<String> = service.listInstalledAppsForModel()

    @Tool(description = "Search the user's phone contacts by name or nickname. This only reads contacts and never calls or sends messages.")
    fun searchContacts(
        @ToolParam(description = "Person's name, family relation or nickname.") personName: String
    ): List<String> = service.findContactsForModel(personName)

    @Tool(description = "Prepare a phone call. This does not call immediately; Jarvis will identify the contact and ask the user for spoken confirmation.")
    fun requestPhoneCall(
        @ToolParam(description = "Contact name or family nickname.") contactName: String
    ): String = service.queueCallFromModel(contactName)

    @Tool(description = "Prepare a WhatsApp message. This does not send it; Jarvis will show the contact and message and ask for spoken confirmation.")
    fun requestWhatsAppMessage(
        @ToolParam(description = "Contact name or family nickname.") contactName: String,
        @ToolParam(description = "Exact message text to send.") message: String
    ): String = service.queueWhatsAppFromModel(contactName, message)

    @Tool(description = "Read text visible on the currently open app screen. Requires Jarvis Screen Control accessibility to be enabled.")
    fun readCurrentScreen(): String = service.readVisibleScreenForModel()

    @Tool(description = "Scroll the currently open app screen. Direction can be up or down. Requires Jarvis Screen Control accessibility.")
    fun scrollCurrentScreen(
        @ToolParam(description = "Scroll direction: up or down.") direction: String
    ): String = service.scrollScreenForModel(direction)

    @Tool(description = "Tap a visible button or control by the text shown on screen. Payment, send, delete, purchase and publish controls require spoken confirmation.")
    fun tapVisibleControl(
        @ToolParam(description = "Visible button or control label.") controlText: String
    ): String = service.tapVisibleControlForModel(controlText)

    @Tool(description = "Enter text in the currently focused text field of the open app. Requires Jarvis Screen Control accessibility.")
    fun typeIntoFocusedField(
        @ToolParam(description = "Text to enter into the focused field.") text: String
    ): String = service.typeIntoScreenForModel(text)

    @Tool(description = "Open a web search in the phone's browser. It does not send the user's conversation to an AI service.")
    fun searchTheWeb(
        @ToolParam(description = "Search terms.") query: String
    ): String = service.searchWebForModel(query)

    @Tool(description = "Open a specific Android settings section. Use accessibility, overlay, battery, Wi-Fi, Bluetooth, notifications, or app.")
    fun openAndroidSettings(
        @ToolParam(description = "Android settings section.") section: String
    ): String = service.openSettingsForModel(section)

    @Tool(description = "Tell the current phone time.")
    fun getCurrentTime(): String = service.currentTimeForModel()

    @Tool(description = "Tell today's date.")
    fun getTodayDate(): String = service.todayDateForModel()
}
''', encoding="utf-8")

tool_source = tools_path.read_text(encoding="utf-8")
if "fun requestSmsMessage(" not in tool_source:
    tool_source = tool_source.replace(
        '    @Tool(description = "Read text visible on the currently open app screen. Requires Jarvis Screen Control accessibility to be enabled.")',
        r'''    @Tool(description = "Prepare an SMS. Jarvis reads the contact, shows the exact message, and asks for spoken confirmation before sending.")
    fun requestSmsMessage(
        @ToolParam(description = "Contact name or family nickname.") contactName: String,
        @ToolParam(description = "Exact SMS text to send.") message: String
    ): String = service.queueSmsFromModel(contactName, message)

    @Tool(description = "Open the Android contact editor with a new person's name and phone number. The user reviews and saves the contact.")
    fun createContact(
        @ToolParam(description = "Person's full name.") name: String,
        @ToolParam(description = "Phone number, preferably with country code.") phone: String
    ): String = service.createContactForModel(name, phone)

    @Tool(description = "Read text visible on the currently open app screen. Requires Jarvis Screen Control accessibility to be enabled.")''',
        1
    )
if "fun setAlarm(" not in tool_source:
    tool_source = tool_source.replace(
        '    @Tool(description = "Tell the current phone time.")',
        r'''    @Tool(description = "Set a phone alarm; the clock app opens and the user confirms saving it.")
    fun setAlarm(
        @ToolParam(description = "Hour in 24-hour format, 0 through 23.") hour: Int,
        @ToolParam(description = "Minute, 0 through 59.") minute: Int,
        @ToolParam(description = "Alarm label.") label: String
    ): String = service.setAlarmForModel(hour, minute, label)

    @Tool(description = "Start a countdown timer using the phone clock app.")
    fun setTimer(
        @ToolParam(description = "Timer length in seconds, 1 through 86400.") seconds: Int,
        @ToolParam(description = "Timer label.") label: String
    ): String = service.setTimerForModel(seconds, label)

    @Tool(description = "Open the phone camera app.")
    fun openCamera(): String = service.openCameraForModel()

    @Tool(description = "Open maps and search for a place or address.")
    fun searchMaps(
        @ToolParam(description = "Place, address or destination.") place: String
    ): String = service.openMapsForModel(place)

    @Tool(description = "Prepare a calendar event. Android opens the calendar editor; the user reviews and saves it.")
    fun createCalendarEvent(
        @ToolParam(description = "Event title.") title: String,
        @ToolParam(description = "Minutes from now until the event begins.") minutesFromNow: Int,
        @ToolParam(description = "Duration of the event in minutes.") durationMinutes: Int,
        @ToolParam(description = "Event notes or location.") note: String
    ): String = service.createCalendarEventForModel(title, minutesFromNow, durationMinutes, note)

    @Tool(description = "Set media volume from zero to one hundred percent.")
    fun setMediaVolume(
        @ToolParam(description = "Volume percentage, zero through 100.") percent: Int
    ): String = service.setMediaVolumeForModel(percent)

    @Tool(description = "Turn the phone flashlight on or off. Requires the Camera permission.")
    fun controlFlashlight(
        @ToolParam(description = "True to turn on, false to turn off.") enabled: Boolean
    ): String = service.setTorchForModel(enabled)

    @Tool(description = "Set screen brightness from one to one hundred percent. Android may ask for Modify System Settings permission.")
    fun setScreenBrightness(
        @ToolParam(description = "Brightness percentage, 1 through 100.") percent: Int
    ): String = service.setScreenBrightnessForModel(percent)

    @Tool(description = "Tell the current phone time.")''',
        1
    )
    tools_path.write_text(tool_source, encoding="utf-8")

# Add small public wrappers and keep direct launcher path free of the overlay-permission gate.
if "fun currentTimeForModel()" not in service:
    service = service.replace(
        "    private fun dateText(): String {",
        "    fun currentTimeForModel(): String = timeText()\n"
        "    fun todayDateForModel(): String = dateText()\n\n"
        "    private fun dateText(): String {",
        1
    )
if "fun runPendingModelAction()" not in service:
    raise SystemExit("No se añadió el despacho de acciones pendientes.")
service_path.write_text(service, encoding="utf-8")

# Fuzzy contact matches: tolerate short ASR errors and family-name variants without guessing between people.
contacts_path = root / "app/src/main/java/com/jarvis/personal/Contacts.kt"
contacts = contacts_path.read_text(encoding="utf-8")
old_filter = '''                val n = strip(name)
                if (tokens.all { n.contains(it) }) {
'''
new_filter = '''                val n = strip(name).replace("mi ", "").trim()
                fun distance(a: String, b: String): Int {
                    var previous = IntArray(b.length + 1) { it }
                    for (i in a.indices) {
                        val current = IntArray(b.length + 1)
                        current[0] = i + 1
                        for (j in b.indices) {
                            val cost = if (a[i] == b[j]) 0 else 1
                            current[j + 1] = minOf(current[j] + 1, previous[j + 1] + 1, previous[j] + cost)
                        }
                        previous = current
                    }
                    return previous[b.length]
                }
                val familyAliases = mapOf(
                    "mama" to listOf("mama", "madre", "mami", "mamita", "mom"),
                    "papa" to listOf("papa", "padre", "papi", "papito", "dad"),
                    "abuela" to listOf("abuela", "abuelita", "nana"),
                    "abuelo" to listOf("abuelo", "abuelito", "nono"),
                    "hermana" to listOf("hermana", "hermanita"),
                    "hermano" to listOf("hermano", "hermanito")
                )
                val expanded = tokens.flatMap { token -> familyAliases[token] ?: listOf(token) }.distinct()
                val nameTokens = n.split(Regex("\\\\s+")).filter { it.isNotBlank() }
                val matches = expanded.map { token ->
                    nameTokens.any { part ->
                        part.contains(token) || token.contains(part) ||
                            (minOf(part.length, token.length) >= 4 && distance(part, token) <= 1)
                    }
                }
                if (matches.any { it } && (matches.count { it } >= minOf(tokens.size, 1))) {
'''
if old_filter in contacts:
    contacts = contacts.replace(old_filter, new_filter, 1)
else:
    raise SystemExit("No se encontró el filtro base de contactos.")
contacts_path.write_text(contacts, encoding="utf-8")

# Android permissions: regular runtime permissions are requested after each app upgrade if they are missing;
# special grants must be switched on by the user in Android Settings.
main = main_path.read_text(encoding="utf-8")
if "add(Manifest.permission.CAMERA)" not in main:
    main = main.replace(
        "            add(Manifest.permission.RECORD_AUDIO)",
        "            add(Manifest.permission.CAMERA)\n            add(Manifest.permission.RECORD_AUDIO)",
        1
    )
if "import java.io.File" not in main:
    main = main.replace("package com.jarvis.personal\n", "package com.jarvis.personal\nimport java.io.File\n", 1)

# Ask explicitly before the one-time, large local-model download on the phone.
start_marker = "        val serviceIntent = Intent(this, JarvisService::class.java)\n"
start_replacement = """        val brainFile = File(noBackupFilesDir, "jarvis-brain-qwen3-1.7b.litertlm")
        if (!brainFile.exists() && !statePrefs.getBoolean("brain_download_accepted", false)) {
            AlertDialog.Builder(this)
                .setTitle("JARVIS · Descargar cerebro local")
                .setMessage("Para conversar con naturalidad y entender órdenes abiertas, Jarvis necesita descargar Qwen3 (aprox. 932 MB, una sola vez). Después queda guardado en el teléfono y las conversaciones se procesan sin enviarlas a una IA remota. Necesitas internet para esta descarga y al menos 1.2 GB libres.")
                .setPositiveButton("DESCARGAR CEREBRO") { _, _ ->
                    statePrefs.edit().putBoolean("brain_download_accepted", true).apply()
                    startJarvis()
                }
                .setNegativeButton("MÁS TARDE", null)
                .show()
            return
        }
""" + start_marker
if start_marker not in main:
    raise SystemExit("No se encontró el inicio del servicio para solicitar consentimiento de descarga.")
main = main.replace(start_marker, start_replacement, 1)

# The first-run permission queue also explains special Android grants that require manual Settings approval.
permission_flow_end = """        completeSetupAndStart()
    }

    override fun onRequestPermissionsResult"""
permission_flow_new = """        handler.postDelayed({ showSpecialAccessReminder() }, 450)
        completeSetupAndStart()
    }

    override fun onRequestPermissionsResult"""
if permission_flow_end in main:
    main = main.replace(permission_flow_end, permission_flow_new, 1)
main = main.replace(
    'text = "J A R V I S"',
    'text = "J A R V I S"',
    1
)
main = main.replace(
    'text = "VOICE INTERFACE  •  OFFLINE CORE"',
    'text = "VOICE INTERFACE  •  LOCAL AI CORE"',
    1
)
main = main.replace(
    '        root.addView(TextView(this).apply {\n            text = "NO GEMINI  /  NO API CONVERSACIONAL REMOTA\\nMicrófono y permisos bajo control de Android."',
    '        root.addView(TextView(this).apply {\n            text = "CEREBRO LOCAL  /  SIN IA REMOTA\\nEl modelo se descarga una vez al teléfono."',
    1
)
button_marker = '''        root.addView(TextView(this).apply {
            text = "CEREBRO LOCAL  /  SIN IA REMOTA\\nEl modelo se descarga una vez al teléfono."
'''
# Add a dedicated permission/settings surface after the small privacy note and before setContentView.
insert_marker = "        scroll.addView(root)\n"
permission_ui = '''        root.addView(makeSecondaryButton("PERMISOS Y CONTROL DEL TELÉFONO") {
            showPhoneCapabilitiesDialog()
        }, LinearLayout.LayoutParams(-1, dp(48)).apply { topMargin = dp(12) })

'''
if "showPhoneCapabilitiesDialog()" not in main:
    if insert_marker not in main:
        raise SystemExit("No se encontró el punto para añadir los controles de permisos.")
    main = main.replace(insert_marker, permission_ui + insert_marker, 1)

# Re-audit existing installations after an upgrade, even when setup_complete was already true in v89.
old_after = '''        handleVersionChange()
        if (!countdownActive && !setupPrefs.getBoolean("setup_complete", false) &&
            !setupPrefs.getBoolean("welcome_dialog_seen", false)) {
            handler.postDelayed({ showWelcomeDialog() }, 450)
        }
        refreshUi()
'''
new_after = '''        handleVersionChange()
        if (!countdownActive && !setupPrefs.getBoolean("setup_complete", false) &&
            !setupPrefs.getBoolean("welcome_dialog_seen", false)) {
            handler.postDelayed({ showWelcomeDialog() }, 450)
        }
        handler.postDelayed({ auditRuntimePermissionsAfterUpgrade() }, 900)
        refreshUi()
'''
if old_after not in main:
    raise SystemExit("No se encontró el bloque de inicialización para revisar permisos tras actualizar.")
main = main.replace(old_after, new_after, 1)

# Updating from v89 must not silently start the new one-time model download.
restart_old = """                    if (restartService && hasPermission(Manifest.permission.RECORD_AUDIO)) {
                        val serviceIntent = Intent(this, JarvisService::class.java)
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(serviceIntent) else startService(serviceIntent)
                        statePrefs.edit().putBoolean("was_running", true).apply()
                    }"""
restart_new = """                    val brainFile = File(noBackupFilesDir, "jarvis-brain-qwen3-1.7b.litertlm")
                    val modelAccepted = brainFile.exists() || statePrefs.getBoolean("brain_download_accepted", false)
                    if (restartService && hasPermission(Manifest.permission.RECORD_AUDIO) && modelAccepted) {
                        val serviceIntent = Intent(this, JarvisService::class.java)
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(serviceIntent) else startService(serviceIntent)
                        statePrefs.edit().putBoolean("was_running", true).apply()
                    } else {
                        statePrefs.edit().putBoolean("was_running", false).apply()
                        if (restartService && !modelAccepted) {
                            status.text = "ACTUALIZACIÓN LISTA · PULSA INICIAR PARA CONFIGURAR EL CEREBRO LOCAL"
                        }
                    }"""
if restart_old not in main:
    raise SystemExit("No se encontró el reinicio automático que debe respetar el consentimiento del modelo.")
main = main.replace(restart_old, restart_new, 1)

# First-run copy must explain the local model download, not claim that only canned skills are used.
main = main.replace(
    "JARVIS funciona en este teléfono y no envía tus conversaciones a Gemini ni a otra IA remota. Esta versión utiliza habilidades locales creadas para la aplicación; no es una IA general entrenada desde cero.\\n\\n",
    "JARVIS ejecuta su cerebro conversacional en este teléfono. El modelo Qwen3 se descarga una vez (aprox. 932 MB) y después las conversaciones se procesan localmente; no se envían a Gemini, ChatGPT ni a otra IA remota.\\n\\n"
)
main = main.replace(
    "Al continuar, Android te pedirá permiso para el micrófono y las notificaciones. No grabamos una huella biométrica ni comparamos quién habla: Jarvis escucha la frase de activación, entiende tus palabras localmente y te responde con voz.",
    "Al continuar, Android solicitará los permisos normales que falten. Los accesos especiales (Accesibilidad, mostrar sobre otras apps y batería) se activan manualmente desde Ajustes. No identificamos quién habla ni guardamos huellas biométricas."
)

permission_methods = r'''    private fun auditRuntimePermissionsAfterUpgrade() {
        if (!setupPrefs.getBoolean("setup_complete", false)) return
        if (countdownActive) {
            handler.postDelayed({ auditRuntimePermissionsAfterUpgrade() }, 4000)
            return
        }
        val currentVersion = try { packageManager.getPackageInfo(packageName, 0).versionCode }
            catch (_: Exception) { 0 }
        val auditedVersion = setupPrefs.getInt("permissions_audited_version", 0)
        if (currentVersion <= auditedVersion) return
        setupPrefs.edit().putInt("permissions_audited_version", currentVersion).apply()
        val missing = runtimePermissions.filterNot { hasPermission(it) }
        if (missing.isEmpty()) {
            showSpecialAccessReminder()
            return
        }
        val names = missing.map { permission ->
            when (permission) {
                Manifest.permission.CAMERA -> "Cámara (necesaria para controlar la linterna)"
                Manifest.permission.RECORD_AUDIO -> "Micrófono (necesario para hablar con Jarvis)"
                Manifest.permission.READ_CONTACTS -> "Contactos (buscar familiares y conocidos)"
                Manifest.permission.CALL_PHONE -> "Llamadas (llamar después de confirmar)"
                Manifest.permission.SEND_SMS -> "SMS (enviar después de confirmar)"
                Manifest.permission.READ_PHONE_STATE -> "Estado del teléfono (detectar el resultado de llamadas)"
                Manifest.permission.POST_NOTIFICATIONS -> "Notificaciones (mostrar estado y acciones de Jarvis)"
                else -> permission
            }
        }.joinToString("\\n")
        AlertDialog.Builder(this)
            .setTitle("JARVIS · Permisos pendientes")
            .setMessage("La actualización detectó permisos que todavía no están concedidos:\\n\\n" + names + "\\n\\nAndroid te los preguntará uno por uno. Puedes rechazar cualquiera; la función que dependa de él quedará desactivada.")
            .setPositiveButton("SOLICITAR PERMISOS") { _, _ -> beginPermissionFlow() }
            .setNegativeButton("AHORA NO", null)
            .show()
    }

    private fun showSpecialAccessReminder() {
        val accessibilityEnabled = try {
            Settings.Secure.getInt(contentResolver, Settings.Secure.ACCESSIBILITY_ENABLED, 0) == 1 &&
                Settings.Secure.getString(contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES)
                    ?.contains(packageName) == true
        } catch (_: Exception) { false }
        val overlayEnabled = Build.VERSION.SDK_INT < 23 || Settings.canDrawOverlays(this)
        val writeSettingsEnabled = Build.VERSION.SDK_INT < 23 || Settings.System.canWrite(this)
        val powerManager = getSystemService(PowerManager::class.java)
        val batteryAllowed = Build.VERSION.SDK_INT < 23 || powerManager.isIgnoringBatteryOptimizations(packageName)
        if (!accessibilityEnabled || !overlayEnabled || !writeSettingsEnabled || !batteryAllowed) {
            AlertDialog.Builder(this)
                .setTitle("JARVIS · Activar control avanzado")
                .setMessage("Para tocar botones, escribir y leer pantallas de otras apps, activa Control de pantalla en Accesibilidad. Mostrar sobre otras apps puede ayudar a abrir interfaces desde segundo plano. Android no permite que Jarvis active estos accesos por sí solo.")
                .setPositiveButton("VER CÓMO ACTIVARLOS") { _, _ -> showPhoneCapabilitiesDialog() }
                .setNegativeButton("MÁS TARDE", null)
                .show()
        }
    }

    private fun showPhoneCapabilitiesDialog() {
        val options = arrayOf(
            "Solicitar permisos normales que falten",
            "Activar Control de pantalla (Accesibilidad)",
            "Permitir Mostrar sobre otras apps",
            "Permitir actividad en segundo plano (Batería)",
            "Permitir modificar ajustes del sistema (brillo)",
            "Abrir permisos de Jarvis en Android"
        )
        AlertDialog.Builder(this)
            .setTitle("JARVIS · Capacidades del teléfono")
            .setItems(options) { _, which ->
                when (which) {
                    0 -> beginPermissionFlow()
                    1 -> try { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }
                         catch (e: Exception) { openAppSettings() }
                    2 -> try { startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:" + packageName))) }
                         catch (e: Exception) { openAppSettings() }
                    3 -> requestBackgroundReliability()
                    4 -> try { startActivity(Intent(Settings.ACTION_MANAGE_WRITE_SETTINGS, Uri.parse("package:" + packageName))) }
                         catch (e: Exception) { openAppSettings() }
                    5 -> openAppSettings()
                }
            }
            .setNegativeButton("CERRAR", null)
            .show()
    }

    private fun openAppSettings() {
        try {
            startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + packageName)))
        } catch (_: Exception) {
            Toast.makeText(this, "Abre Ajustes > Aplicaciones > Jarvis.", Toast.LENGTH_LONG).show()
        }
    }

    private fun makeSecondaryButton(label: String, action: () -> Unit) = Button(this).apply {
        text = label
        isAllCaps = false
        textSize = 11f
        letterSpacing = 0.03f
        typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
        setTextColor(Color.parseColor("#8DEBFA"))
        background = panelBackground("#121A23", "#3F6472")
        setOnClickListener { action() }
    }

'''
if "private fun auditRuntimePermissionsAfterUpgrade()" not in main:
    # requestBackgroundReliability is added by the update script; insert the new methods just before it.
    marker = "    private fun requestBackgroundReliability() {"
    if marker not in main:
        raise SystemExit("No se encontró el área de métodos de permisos de Android.")
    main = main.replace(marker, permission_methods + marker, 1)

main_path.write_text(main, encoding="utf-8")

# LiteRT-LM GPU backend needs optional native-library declarations on Android.
manifest = manifest_path.read_text(encoding="utf-8")
native_lines = '''        <uses-native-library android:name="libvndksupport.so" android:required="false" />
        <uses-native-library android:name="libOpenCL.so" android:required="false" />
'''
if "libOpenCL.so" not in manifest:
    app_end = '        android:theme="@android:style/Theme.Material.Light.NoActionBar">'
    if app_end not in manifest:
        raise SystemExit("No se encontró el final de los atributos de application en el manifiesto.")
    manifest = manifest.replace(app_end, app_end + "\n" + native_lines, 1)
if "android.permission.CAMERA" not in manifest:
    manifest = manifest.replace(
        '    <uses-permission android:name="android.permission.INTERNET" />',
        '    <uses-permission android:name="android.permission.INTERNET" />\n    <uses-permission android:name="android.permission.CAMERA" />',
        1
    )
if "android.permission.WRITE_SETTINGS" not in manifest:
    manifest = manifest.replace(
        '    <uses-permission android:name="android.permission.INTERNET" />',
        '    <uses-permission android:name="android.permission.INTERNET" />\n    <uses-permission android:name="android.permission.WRITE_SETTINGS" />',
        1
    )
if "com.android.alarm.permission.SET_ALARM" not in manifest:
    manifest = manifest.replace(
        '    <uses-permission android:name="android.permission.RECORD_AUDIO" />',
        '    <uses-permission android:name="android.permission.RECORD_AUDIO" />\n    <uses-permission android:name="com.android.alarm.permission.SET_ALARM" />',
        1
    )
if "android.permission.ACCESS_NETWORK_STATE" not in manifest:
    manifest = manifest.replace(
        '    <uses-permission android:name="android.permission.INTERNET" />',
        '    <uses-permission android:name="android.permission.INTERNET" />\n    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />',
        1
    )
manifest_path.write_text(manifest, encoding="utf-8")

# Guardrails: no biometrics, preserve voice input/output, model loading and all primary launcher actions.
if "OwnerVoiceVerifier" in service or "verifiedVoice(" in service:
    raise SystemExit("La biometría de voz no debe reintroducirse.")
if "AudioRecord" not in service or "Recognizer" not in service or "speak(" not in service:
    raise SystemExit("La ruta de voz a voz debe seguir presente.")
if "initializeLocalBrain()" not in service or "JarvisTools" not in service or "sendMessageAsync" not in service:
    raise SystemExit("El cerebro local o el puente de herramientas no quedó integrado.")
if "showPhoneCapabilitiesDialog()" not in main or "auditRuntimePermissionsAfterUpgrade()" not in main:
    raise SystemExit("No se integró el flujo de permisos actualizado.")
print("Jarvis preparado con cerebro Qwen3 local, herramientas Android y auditoría de permisos.")
