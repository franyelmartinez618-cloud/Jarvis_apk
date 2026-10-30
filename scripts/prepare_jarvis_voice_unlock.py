from pathlib import Path
import re
import shutil
import sys

root = Path(sys.argv[1])
service_path = root / "app/src/main/java/com/jarvis/personal/JarvisService.kt"
main_path = root / "app/src/main/java/com/jarvis/personal/MainActivity.kt"
manifest_path = root / "app/src/main/AndroidManifest.xml"

service = service_path.read_text(encoding="utf-8")

# Preserve speech recognition (ASR), remove speaker biometrics completely.
service = service.replace(
    "    private var ownerSessionUntilMs = 0L\n",
    ""
)

# Permit longer spoken phrases; recognition stops early as soon as Vosk detects an endpoint.
if "started < 8_000" in service:
    service = service.replace("started < 8_000", "started < 20_000", 1)
elif "started < 20_000" not in service:
    raise SystemExit("No se encontró el límite de escucha del reconocedor local.")

conversation = r'''    /** Conversación continua de voz: ASR local para entender y TTS para responder. */
    private suspend fun conversation() {
        updateNotification("Escuchando en local")
        delay(120)
        while (running) {
            val heard = listen()
            if (heard.isNullOrBlank()) {
                delay(120)
                continue
            }
            val clean = heard.trim()
            Log.d(TAG, "Frase reconocida localmente: " + clean)
            updateNotification("Jarvis está respondiendo")
            val command = Parser.parse(clean)
            handle(command)
            if (command == Cmd.Cancel) break
            delay(180)
        }
    }

    private suspend fun handle(cmd: Cmd) {
        when (cmd) {
            is Cmd.Call -> doCall(cmd.target)
            is Cmd.Message -> doMessage(cmd)
            is Cmd.OpenApp -> doOpenApp(cmd.name)
            Cmd.Time -> speak(timeText())
            Cmd.DateToday -> speak(dateText())
            Cmd.Cancel -> speak("De acuerdo. Quedo en espera.")
            is Cmd.Unknown -> if (!handleScreenCommand(cmd.raw)) respondNaturally(cmd.raw)
        }
    }

'''
service, count = re.subn(
    r'(?ms)^    /\*\* Una activación abre varios turnos;.*?^    private suspend fun handle\(cmd: Cmd\) \{.*?^    \}\n',
    lambda _: conversation,
    service,
    count=1
)
if count != 1:
    raise SystemExit("No se pudo quitar la barrera biométrica del ciclo de conversación.")

# A recognized sentence is accepted immediately; no speaker embedding is computed.
service = service.replace(
'''                val capturedAudio = ArrayList<Float>(sampleRate * 6)
''',
    ""
)
service = service.replace(
'''                    for (index in 0 until count) capturedAudio.add(buffer[index] / 32768.0f)
''',
    ""
)
old_spoken = '''                        if (spoken.isNotBlank()) {
                            val authorized = verifiedVoice(capturedAudio)
                            if (authorized) return@withContext spoken
                            Log.i(TAG, "Voz no autorizada; la orden no se ejecutará")
                            return@withContext null
                        }'''
new_spoken = '''                        if (spoken.isNotBlank()) return@withContext spoken'''
if old_spoken not in service:
    raise SystemExit("No se encontró la verificación biométrica tras el primer resultado ASR.")
service = service.replace(old_spoken, new_spoken, 1)

old_final = '''                if (finalText.isBlank()) null else if (
                    verifiedVoice(capturedAudio)
                ) finalText else {
                    Log.i(TAG, "Voz final no autorizada; no responderé")
                    null
                }'''
if old_final not in service:
    raise SystemExit("No se encontró la verificación biométrica del resultado final.")
service = service.replace(old_final, "                finalText.ifBlank { null }", 1)

service, count = re.subn(
    r'(?ms)^    /\*\* Motor local propio basado en intenciones;.*?^    private suspend fun respondNaturally',
    "    private suspend fun respondNaturally",
    service,
    count=1
)
if count != 1:
    raise SystemExit("No se pudo eliminar la función de verificación biométrica.")

if "OwnerVoiceVerifier" in service or "verifiedVoice(" in service or "capturedAudio" in service:
    raise SystemExit("Quedaron referencias a biometría de voz en JarvisService.")
service_path.write_text(service, encoding="utf-8")

# Remove biometric enrollment screen and speaker-identification engine/assets.
for relative in [
    "app/src/main/java/com/jarvis/personal/OwnerVoiceVerifier.kt",
    "app/src/main/java/com/jarvis/personal/VoiceSetupActivity.kt",
]:
    path = root / relative
    if path.exists():
        path.unlink()

for relative in [
    "app/src/main/java/com/k2fsa/sherpa",
    "app/src/main/jniLibs",
]:
    path = root / relative
    if path.exists():
        shutil.rmtree(path)

assets = root / "app/src/main/assets"
if assets.exists():
    speaker_model = assets / "jarvis-speaker.onnx"
    if speaker_model.exists():
        speaker_model.unlink()

# Main screen still uses the same one-button voice assistant; it only asks for
# microphone/notification and the optional phone permissions, never voice enrollment.
main = main_path.read_text(encoding="utf-8")
main = main.replace("        OwnerVoiceVerifier.warmUp(applicationContext)\n", "")

on_resume_pattern = re.compile(
    r'(?ms)^    override fun onResume\(\) \{.*?^    \}\n\n(?=    private fun showWelcomeDialog)'
)
main, count = on_resume_pattern.subn(
    "    override fun onResume() {\n        super.onResume()\n        desiredActive = JarvisService.running\n        handler.removeCallbacks(serviceWatcher)\n        handler.post(serviceWatcher)\n        refreshUi()\n    }\n\n    override fun onPause() {\n        handler.removeCallbacks(serviceWatcher)\n        super.onPause()\n    }\n\n",
    main,
    count=1
)
if count != 1:
    raise SystemExit("No se pudo retirar el flujo de registro biométrico de onResume().")

main = main.replace(
    "Al continuar, Android te pedirá los permisos del micrófono y de las funciones opcionales, uno por uno. Después registrarás dos muestras cortas de tu voz.",
    "Al continuar, Android te pedirá permiso para el micrófono y las notificaciones. No grabamos una huella biométrica ni comparamos quién habla: Jarvis escucha la frase de activación, entiende tus palabras localmente y te responde con voz."
)

enrollment_block = '''        if (!OwnerVoiceVerifier.isEnrolled(this)) {
            setupPrefs.edit().putBoolean("voice_setup_pending", true).apply()
            startActivity(Intent(this, VoiceSetupActivity::class.java))
            return
        }
'''
if main.count(enrollment_block) != 2:
    raise SystemExit("No se encontraron las dos barreras de inscripción de voz esperadas.")
main = main.replace(enrollment_block, "", 2)
main = main.replace(
    "if (restartService && hasPermission(Manifest.permission.RECORD_AUDIO) && OwnerVoiceVerifier.isEnrolled(this)) {",
    "if (restartService && hasPermission(Manifest.permission.RECORD_AUDIO)) {",
    1
)
main = main.replace(
    'status.text = if (OwnerVoiceVerifier.isEnrolled(this)) "SISTEMA LISTO · VOZ REGISTRADA" else "SISTEMA EN ESPERA"',
    'status.text = "SISTEMA LISTO · VOZ LOCAL PREPARADA"',
    1
)
main = main.replace(
    "        if (setupPrefs.getBoolean(\"voice_setup_pending\", false)) {\n            setupPrefs.edit().putBoolean(\"voice_setup_pending\", false).apply()\n            if (OwnerVoiceVerifier.isEnrolled(this) && hasPermission(Manifest.permission.RECORD_AUDIO)) {\n                completeSetupAndStart()\n            } else {\n                status.text = \"REGISTRO DE VOZ PENDIENTE · PULSA INICIAR PARA CONTINUAR\"\n            }\n        }\n",
    ""
)
if "OwnerVoiceVerifier" in main or "VoiceSetupActivity" in main:
    raise SystemExit("Quedaron referencias a la inscripción biométrica en MainActivity.")
main_path.write_text(main, encoding="utf-8")


# ── Stark-inspired native cockpit UI and reliable service state.
main = main_path.read_text(encoding="utf-8")
for import_line in [
    "import android.graphics.Canvas",
    "import android.graphics.Paint",
    "import android.graphics.RectF",
    "import android.os.SystemClock",
    "import android.view.View",
    "import android.widget.ScrollView",
]:
    if import_line not in main:
        main = main.replace("import android.graphics.Color\n", "import android.graphics.Color\n" + import_line + "\n", 1)

main = main.replace(
    "    private var countdownActive = false\n",
    "    private var countdownActive = false\n"
    "    private var desiredActive = false\n"
    "    private var serviceStartPending = false\n"
    "    private var stopRequested = false\n"
    "    private val serviceWatcher = object : Runnable {\n"
    "        override fun run() {\n"
    "            val actual = JarvisService.running\n"
    "            if (!serviceStartPending) {\n"
    "                if (stopRequested) {\n"
    "                    if (!actual) stopRequested = false\n"
    "                } else if (desiredActive && !actual) {\n"
    "                    desiredActive = false\n"
    "                    statePrefs.edit().putBoolean(\"was_running\", false).apply()\n"
    "                    if (::status.isInitialized) status.text = \"ENLACE INTERRUMPIDO · CORE EN ESPERA\"\n"
    "                } else if (!desiredActive && actual) {\n"
    "                    desiredActive = true\n"
    "                }\n"
    "                refreshUi()\n"
    "            }\n"
    "            handler.postDelayed(this, 900)\n"
    "        }\n"
    "    }\n",
    1
)

# Replace only the old home-screen composition. Service setup, update checks and permissions remain intact.
start = "        val root = LinearLayout(this).apply {"
end = "        setContentView(root)\n"
if start not in main or end not in main:
    raise SystemExit("No se encontró el bloque original del menú principal.")
start_at = main.index(start)
end_at = main.index(end, start_at) + len(end)
cockpit = r'''        val scroll = ScrollView(this).apply {
            isFillViewport = true
            isVerticalScrollBarEnabled = false
        }
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(pad, dp(22), pad, dp(28))
            background = GradientDrawable(
                GradientDrawable.Orientation.TOP_BOTTOM,
                intArrayOf(Color.parseColor("#070A10"), Color.parseColor("#111923"), Color.parseColor("#080B12"))
            )
        }

        val topLine = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        topLine.addView(TextView(this).apply {
            text = "J.A.R.V.I.S  /  SYSTEM CORE"
            textSize = 10f
            letterSpacing = 0.16f
            typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
            setTextColor(Color.parseColor("#F2A46D"))
        }, LinearLayout.LayoutParams(0, -2, 1f))
        topLine.addView(TextView(this).apply {
            text = "LOCAL  •  ES"
            textSize = 9f
            letterSpacing = 0.10f
            setTextColor(Color.parseColor("#70DFF5"))
            gravity = Gravity.CENTER
        })
        root.addView(topLine)

        val divider = View(this).apply {
            setBackgroundColor(Color.parseColor("#733E35"))
        }
        root.addView(divider, LinearLayout.LayoutParams(-1, dp(1)).apply {
            topMargin = dp(12)
            bottomMargin = dp(12)
        })

        root.addView(TextView(this).apply {
            text = "PERSONAL INTELLIGENCE SYSTEM"
            textSize = 10f
            letterSpacing = 0.20f
            gravity = Gravity.CENTER
            setTextColor(Color.parseColor("#8FA7B8"))
        })

        root.addView(ReactorView(this), LinearLayout.LayoutParams(dp(236), dp(236)).apply {
            gravity = Gravity.CENTER
            topMargin = dp(4)
            bottomMargin = dp(2)
        })

        root.addView(TextView(this).apply {
            text = "J A R V I S"
            textSize = 31f
            letterSpacing = 0.22f
            gravity = Gravity.CENTER
            typeface = Typeface.create("sans-serif-light", Typeface.NORMAL)
            setTextColor(Color.parseColor("#F1F6F8"))
        })
        root.addView(TextView(this).apply {
            text = "VOICE INTERFACE  •  OFFLINE CORE"
            textSize = 9f
            letterSpacing = 0.13f
            gravity = Gravity.CENTER
            setTextColor(Color.parseColor("#9AABB8"))
            setPadding(0, dp(4), 0, dp(14))
        })

        val statusPanel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            background = panelBackground("#151D27", "#784A3D")
            setPadding(dp(16), dp(13), dp(16), dp(13))
        }
        status = TextView(this).apply {
            text = "CORE EN ESPERA"
            textSize = 12f
            letterSpacing = 0.10f
            gravity = Gravity.CENTER
            typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
            setTextColor(Color.parseColor("#F1B27D"))
        }
        statusPanel.addView(status)
        root.addView(statusPanel, LinearLayout.LayoutParams(-1, -2).apply {
            bottomMargin = dp(12)
        })

        root.addView(infoCard("VOICE INPUT  /  ESPAÑOL", "VOSK ASR  •  PROCESAMIENTO EN EL TELÉFONO", "#69E5F7"))
        root.addView(infoCard("VOICE RESPONSE  /  AUDIO", "SÍNTESIS DE VOZ ANDROID  •  SIN CHAT ESCRITO", "#F0A16B"))

        mainButton = makeMainButton("INICIAR JARVIS")
        root.addView(mainButton, LinearLayout.LayoutParams(-1, dp(62)).apply {
            topMargin = dp(18)
            bottomMargin = dp(12)
        })

        root.addView(TextView(this).apply {
            text = "NO GEMINI  /  NO API CONVERSACIONAL REMOTA\nMicrófono y permisos bajo control de Android."
            textSize = 9f
            setLineSpacing(dp(3).toFloat(), 1f)
            letterSpacing = 0.04f
            gravity = Gravity.CENTER
            setTextColor(Color.parseColor("#748A9A"))
        })

        scroll.addView(root)
        setContentView(scroll)
'''
main = main[:start_at] + cockpit + main[end_at:]

# Explicit button semantics: start only starts; stop only stops. A failed model load cannot leave a false active state.
button_methods = r'''    private fun onMainButton() {
        if (desiredActive || JarvisService.running || serviceStartPending) {
            serviceStartPending = false
            desiredActive = false
            stopRequested = true
            statePrefs.edit().putBoolean("was_running", false).apply()
            try {
                stopService(Intent(this, JarvisService::class.java))
                status.text = "DESACTIVANDO CORE..."
                refreshUi()
                handler.postDelayed({
                    stopRequested = false
                    desiredActive = JarvisService.running
                    if (!desiredActive) status.text = "CORE EN ESPERA · LISTO PARA INICIAR"
                    refreshUi()
                }, 1200)
            } catch (e: Exception) {
                stopRequested = false
                status.text = "NO SE PUDO DETENER EL SERVICIO"
                Toast.makeText(this, "No se pudo detener JARVIS: " + (e.message ?: "error"), Toast.LENGTH_LONG).show()
                refreshUi()
            }
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
        val serviceIntent = Intent(this, JarvisService::class.java)
        try {
            stopRequested = false
            desiredActive = true
            serviceStartPending = true
            statePrefs.edit().putBoolean("was_running", true).apply()
            status.text = "INICIALIZANDO MOTOR DE VOZ..."
            refreshUi()
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(serviceIntent)
            } else {
                startService(serviceIntent)
            }
            fun verifyStart(attempt: Int) {
                if (!serviceStartPending) return
                if (JarvisService.running) {
                    serviceStartPending = false
                    desiredActive = true
                    status.text = "CORE ACTIVO · ESCUCHA LOCAL"
                    refreshUi()
                    return
                }
                if (attempt >= 15) {
                    serviceStartPending = false
                    desiredActive = false
                    statePrefs.edit().putBoolean("was_running", false).apply()
                    status.text = "NO SE PUDO INICIAR · REVISA EL MOTOR DE VOZ"
                    Toast.makeText(this, "JARVIS no pudo iniciar. El menú sigue abierto; revisa el modelo y los permisos.", Toast.LENGTH_LONG).show()
                    refreshUi()
                    return
                }
                status.text = "INICIALIZANDO CORE... " + (attempt + 1) + "/15"
                handler.postDelayed({ verifyStart(attempt + 1) }, 1000)
            }
            handler.postDelayed({ verifyStart(0) }, 1000)
        } catch (e: Exception) {
            serviceStartPending = false
            desiredActive = false
            statePrefs.edit().putBoolean("was_running", false).apply()
            status.text = "ERROR AL INICIAR EL SERVICIO"
            Toast.makeText(this, "Android no pudo iniciar JARVIS: " + (e.message ?: "error del sistema"), Toast.LENGTH_LONG).show()
            refreshUi()
        }
    }

'''
main, count = re.subn(
    r'(?ms)^    private fun onMainButton\(\) \{.*?^    private fun handleVersionChange\(\) \{',
    lambda _: button_methods + "    private fun handleVersionChange() {",
    main,
    count=1
)
if count != 1:
    raise SystemExit("No se pudo sustituir el control de inicio/detención.")

# Replace the compact placeholder menu with styled status, native panels and a live drawn reactor.
new_tail = r'''    private fun refreshUi() {
        if (countdownActive || !::status.isInitialized || !::mainButton.isInitialized) return
        val active = desiredActive || JarvisService.running || serviceStartPending
        if (serviceStartPending) {
            status.text = "INICIALIZANDO CORE · MOTOR DE VOZ"
            status.setTextColor(Color.parseColor("#F4B27B"))
            mainButton.text = "CANCELAR INICIO"
        } else if (active) {
            status.text = "● CORE ACTIVO · ESCUCHA LOCAL"
            status.setTextColor(Color.parseColor("#69E5F7"))
            mainButton.text = "DETENER JARVIS"
        } else {
            if (status.text.isNullOrBlank() || status.text.toString().contains("ACTIVO")) {
                status.text = "CORE EN ESPERA · LISTO PARA INICIAR"
            }
            status.setTextColor(Color.parseColor("#F0A16B"))
            mainButton.text = "INICIAR JARVIS"
        }
        mainButton.background = GradientDrawable(
            GradientDrawable.Orientation.LEFT_RIGHT,
            if (active) intArrayOf(Color.parseColor("#421D20"), Color.parseColor("#8D302A"))
            else intArrayOf(Color.parseColor("#A9472D"), Color.parseColor("#E4773D"))
        ).apply {
            cornerRadius = dp(17).toFloat()
            setStroke(dp(1), if (active) Color.parseColor("#E8755D") else Color.parseColor("#FFC18A"))
        }
        mainButton.setTextColor(Color.parseColor("#FFF3E9"))
    }

    private fun makeMainButton(label: String) = Button(this).apply {
        text = label
        isAllCaps = false
        textSize = 15f
        letterSpacing = 0.05f
        typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
        setTextColor(Color.parseColor("#FFF3E9"))
        background = GradientDrawable(
            GradientDrawable.Orientation.LEFT_RIGHT,
            intArrayOf(Color.parseColor("#A9472D"), Color.parseColor("#E4773D"))
        ).apply {
            cornerRadius = dp(17).toFloat()
            setStroke(dp(1), Color.parseColor("#FFC18A"))
        }
        setPadding(pad, pad / 2, pad, pad / 2)
        setOnClickListener { onMainButton() }
    }

    private fun dp(value: Int): Int = (resources.displayMetrics.density * value).toInt()

    private fun panelBackground(fill: String, edge: String) = GradientDrawable().apply {
        setColor(Color.parseColor(fill))
        cornerRadius = dp(15).toFloat()
        setStroke(dp(1), Color.parseColor(edge))
    }

    private fun infoCard(title: String, detail: String, accent: String): LinearLayout {
        return LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = panelBackground("#121A23", "#303E49")
            setPadding(dp(14), dp(11), dp(14), dp(11))
            addView(TextView(this@MainActivity).apply {
                text = title
                textSize = 10f
                letterSpacing = 0.12f
                typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
                setTextColor(Color.parseColor(accent))
            })
            addView(TextView(this@MainActivity).apply {
                text = detail
                textSize = 10f
                letterSpacing = 0.02f
                setPadding(0, dp(4), 0, 0)
                setTextColor(Color.parseColor("#B5C4CE"))
            })
        }.also { card ->
            card.layoutParams = LinearLayout.LayoutParams(-1, -2).apply {
                bottomMargin = dp(8)
            }
        }
    }

    private class ReactorView(context: Context) : View(context) {
        private val paint = Paint(Paint.ANTI_ALIAS_FLAG)

        override fun onDraw(canvas: Canvas) {
            super.onDraw(canvas)
            val side = minOf(width, height).toFloat()
            val cx = width / 2f
            val cy = height / 2f
            val r = side * 0.43f
            val bounds = RectF(cx - r, cy - r, cx + r, cy + r)
            val phase = (SystemClock.uptimeMillis() / 34L % 360L).toFloat()

            paint.style = Paint.Style.STROKE
            paint.strokeWidth = 1.6f
            paint.color = Color.parseColor("#344A5A")
            canvas.drawCircle(cx, cy, r, paint)
            paint.strokeWidth = 3.0f
            paint.color = Color.parseColor("#C45B3E")
            canvas.drawArc(bounds, phase, 74f, false, paint)
            paint.color = Color.parseColor("#64DDF5")
            canvas.drawArc(bounds, phase + 180f, 88f, false, paint)

            paint.strokeWidth = 1.2f
            paint.color = Color.parseColor("#557184")
            for (i in 0 until 12) {
                val angle = Math.toRadians((i * 30.0) + phase.toDouble() * 0.18)
                val inner = r * 0.78f
                val outer = r * 0.91f
                canvas.drawLine(
                    cx + (Math.cos(angle) * inner).toFloat(),
                    cy + (Math.sin(angle) * inner).toFloat(),
                    cx + (Math.cos(angle) * outer).toFloat(),
                    cy + (Math.sin(angle) * outer).toFloat(),
                    paint
                )
            }

            paint.style = Paint.Style.STROKE
            paint.strokeWidth = 2.4f
            paint.color = Color.parseColor("#3AAFCB")
            canvas.drawCircle(cx, cy, r * 0.61f, paint)
            paint.strokeWidth = 1.4f
            paint.color = Color.parseColor("#A85A43")
            canvas.drawCircle(cx, cy, r * 0.49f, paint)

            paint.style = Paint.Style.FILL
            paint.color = Color.parseColor("#182D3A")
            canvas.drawCircle(cx, cy, r * 0.40f, paint)
            paint.color = Color.parseColor("#1F8CA6")
            canvas.drawCircle(cx, cy, r * 0.29f, paint)
            paint.color = Color.parseColor("#8CEBFF")
            canvas.drawCircle(cx, cy, r * 0.19f, paint)
            paint.color = Color.parseColor("#E7FCFF")
            canvas.drawCircle(cx, cy, r * 0.075f, paint)

            paint.style = Paint.Style.STROKE
            paint.strokeWidth = 1.0f
            paint.color = Color.parseColor("#7DA6B9")
            canvas.drawCircle(cx, cy, r * 0.34f, paint)
            postInvalidateDelayed(48L)
        }
    }
'''
main, count = re.subn(
    r'(?ms)^    private fun refreshUi\(\) \{.*?(?=^    private fun requestBackgroundReliability\(\))',
    lambda _: new_tail,
    main,
    count=1
)
if count != 1:
    raise SystemExit("No se pudo instalar la nueva interfaz del reactor.")
main_path.write_text(main, encoding="utf-8")


manifest = manifest_path.read_text(encoding="utf-8")
manifest = re.sub(
    r'\s*<activity[^>]*android:name="\.VoiceSetupActivity"[^>]*/>',
    "",
    manifest
)
manifest_path.write_text(manifest, encoding="utf-8")

# Explicitly verify that ASR/TTS remains and biometric files are gone.
if "AudioRecord" not in service or "Recognizer" not in service or "speak(" not in service:
    raise SystemExit("La compilación debe conservar el micrófono ASR y la respuesta hablada TTS.")
if (root / "app/src/main/java/com/jarvis/personal/OwnerVoiceVerifier.kt").exists():
    raise SystemExit("No se eliminó OwnerVoiceVerifier.kt.")

print("Jarvis queda voz-a-voz: reconoce el contenido hablado en local, responde con TTS y no realiza verificación biométrica.")
