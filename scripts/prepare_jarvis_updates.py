from pathlib import Path
import sys

root = Path(sys.argv[1])

# A monotonic versionCode lets the app compare its installed version with a GitHub Release.
gradle_candidates = [root / "app/build.gradle.kts", root / "app/build.gradle"]
gradle_path = next((path for path in gradle_candidates if path.exists()), None)
if gradle_path is None:
    raise SystemExit("No se encontró el archivo Gradle de la app.")
gradle_text = gradle_path.read_text(encoding="utf-8")

if gradle_path.name.endswith(".kts"):
    gradle_text += r"""

val jarvisAutoUpdateVersionCode = project.findProperty("jarvisVersionCode")?.toString()?.toIntOrNull() ?: 1
val jarvisAutoStoreFile = project.findProperty("jarvisStoreFile")?.toString().orEmpty()
val jarvisAutoStorePassword = project.findProperty("jarvisStorePassword")?.toString().orEmpty()
val jarvisAutoKeyAlias = project.findProperty("jarvisKeyAlias")?.toString().orEmpty()
val jarvisAutoKeyPassword = project.findProperty("jarvisKeyPassword")?.toString().orEmpty()
android {
    defaultConfig {
        versionCode = jarvisAutoUpdateVersionCode
        versionName = "1.0." + jarvisAutoUpdateVersionCode
    }
    if (jarvisAutoStoreFile.isNotBlank() && jarvisAutoStorePassword.isNotBlank() &&
        jarvisAutoKeyAlias.isNotBlank() && jarvisAutoKeyPassword.isNotBlank()) {
        signingConfigs {
            create("jarvisRelease") {
                storeFile = file(jarvisAutoStoreFile)
                storePassword = jarvisAutoStorePassword
                keyAlias = jarvisAutoKeyAlias
                keyPassword = jarvisAutoKeyPassword
            }
        }
        buildTypes {
            getByName("release") {
                signingConfig = signingConfigs.getByName("jarvisRelease")
            }
        }
    }
}
"""
else:
    gradle_text += r"""

def jarvisAutoUpdateVersionCode = project.findProperty("jarvisVersionCode")?.toString()?.toInteger() ?: 1
def jarvisAutoStoreFile = project.findProperty("jarvisStoreFile")?.toString()
def jarvisAutoStorePassword = project.findProperty("jarvisStorePassword")?.toString()
def jarvisAutoKeyAlias = project.findProperty("jarvisKeyAlias")?.toString()
def jarvisAutoKeyPassword = project.findProperty("jarvisKeyPassword")?.toString()
android {
    defaultConfig {
        versionCode jarvisAutoUpdateVersionCode
        versionName "1.0." + jarvisAutoUpdateVersionCode
    }
    if (jarvisAutoStoreFile && jarvisAutoStorePassword && jarvisAutoKeyAlias && jarvisAutoKeyPassword) {
        signingConfigs {
            jarvisRelease {
                storeFile file(jarvisAutoStoreFile)
                storePassword jarvisAutoStorePassword
                keyAlias jarvisAutoKeyAlias
                keyPassword jarvisAutoKeyPassword
            }
        }
        buildTypes {
            release {
                signingConfig signingConfigs.jarvisRelease
            }
        }
    }
}
"""
gradle_path.write_text(gradle_text, encoding="utf-8")

main_path = root / "app/src/main/java/com/jarvis/personal/MainActivity.kt"
m = main_path.read_text(encoding="utf-8")
package_line = "package com.jarvis.personal\n"
if package_line not in m:
    raise SystemExit("No se encontró el paquete esperado en MainActivity.kt.")

required_imports = [
    "import android.app.AlertDialog",
    "import android.app.DownloadManager",
    "import android.content.BroadcastReceiver",
    "import android.content.Context",
    "import android.content.IntentFilter",
    "import android.net.Uri",
    "import android.os.Build",
    "import android.provider.Settings",
    "import org.json.JSONObject",
    "import java.net.HttpURLConnection",
    "import java.net.URL",
]
for required_import in required_imports:
    if required_import not in m:
        m = m.replace(package_line, package_line + required_import + "\n", 1)

update_button_marker = "        root.addView(brainDownloadButton)"
if update_button_marker not in m:
    raise SystemExit("No se encontró el botón del cerebro local para añadir el acceso de actualización.")
m = m.replace(
    update_button_marker,
    update_button_marker + '\n        root.addView(button("Buscar actualizaciones de Jarvis") { checkForUpdates(true) })',
    1
)

import re

auto_check_pattern = re.compile(
    r'(?ms)(^    override fun onCreate\([^)]*\)\s*\{.*?)(^    \}\s*(?=\n\n    (?:private|override|protected|fun)\s))'
)
m, auto_check_count = auto_check_pattern.subn(
    lambda match: match.group(1) + '        android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({ checkForUpdates(false) }, 2500)\n' + match.group(2),
    m,
    count=1
)
if auto_check_count != 1:
    raise SystemExit("No se pudo añadir la comprobación automática al final de MainActivity.onCreate.")

update_methods = r'''    private fun checkForUpdates(manual: Boolean) {
        val updatePrefs = getSharedPreferences("jarvis_updates", Context.MODE_PRIVATE)
        val now = System.currentTimeMillis()
        if (!manual && now - updatePrefs.getLong("last_check_ms", 0L) < 6L * 60L * 60L * 1000L) return
        updatePrefs.edit().putLong("last_check_ms", now).apply()

        Thread {
            var connection: HttpURLConnection? = null
            try {
                connection = (URL("https://api.github.com/repos/franyelmartinez618-cloud/Jarvis_apk/releases/latest")
                    .openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = 8000
                    readTimeout = 10000
                    setRequestProperty("Accept", "application/vnd.github+json")
                    setRequestProperty("User-Agent", "JarvisAndroid-Updater")
                }
                val code = connection.responseCode
                if (code !in 200..299) throw IllegalStateException("GitHub devolvió HTTP " + code)
                val release = JSONObject(connection.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() })
                val latestCode = release.optString("tag_name").removePrefix("v").toIntOrNull()
                    ?: throw IllegalStateException("La versión publicada no tiene un número válido")
                val assets = release.optJSONArray("assets")
                var apkUrl = ""
                if (assets != null) {
                    for (index in 0 until assets.length()) {
                        val asset = assets.optJSONObject(index) ?: continue
                        if (asset.optString("name") == "jarvis.apk") {
                            apkUrl = asset.optString("browser_download_url")
                            break
                        }
                    }
                }
                if (!apkUrl.startsWith("https://github.com/franyelmartinez618-cloud/Jarvis_apk/releases/download/")) {
                    throw IllegalStateException("La versión publicada no contiene un APK oficial válido")
                }
                val currentCode = packageManager.getPackageInfo(packageName, 0).versionCode
                runOnUiThread {
                    if (isFinishing) return@runOnUiThread
                    if (latestCode > currentCode) {
                        AlertDialog.Builder(this)
                            .setTitle("Hay una actualización de Jarvis")
                            .setMessage("Versión instalada: " + currentCode + "\nNueva versión: " + latestCode + "\n\nAndroid te pedirá confirmar la instalación.")
                            .setPositiveButton("Descargar e instalar") { _, _ -> downloadJarvisUpdate(apkUrl) }
                            .setNegativeButton("Ahora no", null)
                            .show()
                    } else if (manual) {
                        Toast.makeText(this, "Jarvis ya está actualizado.", Toast.LENGTH_LONG).show()
                    }
                }
            } catch (e: Exception) {
                android.util.Log.w("JarvisUpdater", "No se pudo consultar la actualización", e)
                if (manual) runOnUiThread {
                    Toast.makeText(this, "No pude consultar actualizaciones. Comprueba internet y que haya una versión publicada.", Toast.LENGTH_LONG).show()
                }
            } finally {
                connection?.disconnect()
            }
        }.start()
    }

    private fun downloadJarvisUpdate(apkUrl: String) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !packageManager.canRequestPackageInstalls()) {
            AlertDialog.Builder(this)
                .setTitle("Permitir actualizar Jarvis")
                .setMessage("Android necesita que autorices a Jarvis a iniciar la instalación. Activa «Permitir desde esta fuente» y vuelve a pulsar Buscar actualizaciones.")
                .setPositiveButton("Abrir ajustes") { _, _ ->
                    try {
                        startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + packageName)))
                    } catch (e: Exception) {
                        Toast.makeText(this, "Abre Ajustes de Android y permite instalar apps desde Jarvis.", Toast.LENGTH_LONG).show()
                    }
                }
                .setNegativeButton("Cancelar", null)
                .show()
            return
        }

        try {
            val manager = getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
            val downloadId = longArrayOf(-1L)
            val receiver = object : BroadcastReceiver() {
                override fun onReceive(context: Context?, intent: Intent?) {
                    if (intent?.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1L) != downloadId[0]) return
                    try { unregisterReceiver(this) } catch (_: Exception) {}
                    val apkUri = manager.getUriForDownloadedFile(downloadId[0])
                    if (apkUri == null) {
                        Toast.makeText(this@MainActivity, "La descarga falló. Vuelve a intentarlo.", Toast.LENGTH_LONG).show()
                        return
                    }
                    try {
                        val installer = Intent(Intent.ACTION_VIEW).apply {
                            setDataAndType(apkUri, "application/vnd.android.package-archive")
                            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        }
                        startActivity(installer)
                    } catch (e: Exception) {
                        Toast.makeText(this@MainActivity, "No pude abrir el instalador de Android.", Toast.LENGTH_LONG).show()
                    }
                }
            }
            val filter = IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE)
            if (Build.VERSION.SDK_INT >= 33) {
                registerReceiver(receiver, filter, Context.RECEIVER_NOT_EXPORTED)
            } else {
                registerReceiver(receiver, filter)
            }
            val request = DownloadManager.Request(Uri.parse(apkUrl)).apply {
                setTitle("Actualización de Jarvis")
                setDescription("Descargando la versión nueva")
                setMimeType("application/vnd.android.package-archive")
                setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                setAllowedOverMetered(true)
                setAllowedOverRoaming(false)
            }
            downloadId[0] = manager.enqueue(request)
            Toast.makeText(this, "Descarga iniciada. Android abrirá el instalador al terminar.", Toast.LENGTH_LONG).show()
        } catch (e: Exception) {
            android.util.Log.e("JarvisUpdater", "No se pudo iniciar la descarga", e)
            Toast.makeText(this, "No pude iniciar la descarga de la actualización.", Toast.LENGTH_LONG).show()
        }
    }
'''
if "private fun checkForUpdates(" not in m:
    cut = m.rfind("\n}")
    if cut < 0:
        raise SystemExit("MainActivity.kt no tiene cierre de clase.")
    m = m[:cut] + "\n\n" + update_methods + "\n" + m[cut:]
main_path.write_text(m, encoding="utf-8")

manifest = root / "app/src/main/AndroidManifest.xml"
xml = manifest.read_text(encoding="utf-8")
if "android.permission.INTERNET" not in xml:
    xml = xml.replace(
        '<manifest ',
        '<manifest ',
        1
    )
    xml = xml.replace(
        '    <uses-permission android:name="android.permission.RECORD_AUDIO" />',
        '    <uses-permission android:name="android.permission.INTERNET" />\n    <uses-permission android:name="android.permission.RECORD_AUDIO" />',
        1
    )
if "android.permission.REQUEST_INSTALL_PACKAGES" not in xml:
    marker = '    <uses-permission android:name="android.permission.INTERNET" />'
    if marker not in xml:
        raise SystemExit("No se encontró INTERNET en AndroidManifest.xml.")
    xml = xml.replace(
        marker,
        marker + '\n    <uses-permission android:name="android.permission.REQUEST_INSTALL_PACKAGES" />',
        1
    )
manifest.write_text(xml, encoding="utf-8")

print("Preparado: verificador de versión, descarga de APK, instalador Android y firma estable opcional.")
