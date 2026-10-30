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
    "    override fun onResume() {\n        super.onResume()\n        refreshUi()\n    }\n\n",
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
