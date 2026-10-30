from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

root = Path(sys.argv[1])
workspace = Path(__file__).resolve().parents[1]
web_source = workspace / "web"
assets = root / "app/src/main/assets/jarvis"
if not (web_source / "index.html").is_file():
    raise SystemExit("No existe web/index.html")
if assets.exists():
    shutil.rmtree(assets)
shutil.copytree(web_source, assets)

ANDROID = "{http://schemas.android.com/apk/res/android}"
ET.register_namespace("android", "http://schemas.android.com/apk/res/android")
ET.register_namespace("tools", "http://schemas.android.com/tools")

manifest_path = root / "app/src/main/AndroidManifest.xml"
tree = ET.parse(manifest_path)
manifest = tree.getroot()

# This build is text-first. No microphone permission or voice-triggered services are registered.
remove_permissions = {
    "android.permission.RECORD_AUDIO",
    "android.permission.FOREGROUND_SERVICE",
    "android.permission.FOREGROUND_SERVICE_MICROPHONE",
    "android.permission.REQUEST_INSTALL_PACKAGES",
    "android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS",
    "android.permission.RECEIVE_BOOT_COMPLETED",
    "android.permission.READ_CONTACTS",
    "android.permission.READ_PHONE_STATE",
    "android.permission.CALL_PHONE",
    "android.permission.SEND_SMS",
    "android.permission.POST_NOTIFICATIONS",
    "android.permission.SYSTEM_ALERT_WINDOW",
}
for child in list(manifest):
    if child.tag == "uses-permission" and child.get(ANDROID + "name") in remove_permissions:
        manifest.remove(child)
    if child.tag == "uses-feature" and child.get(ANDROID + "name") == "android.hardware.microphone":
        manifest.remove(child)

application = manifest.find("application")
if application is None:
    raise SystemExit("AndroidManifest.xml no contiene application")

# The text-first app has no microphone, boot receiver or background speech service.
# Keep only the explicitly enabled accessibility service among the old service declarations.
for child in list(application):
    name = child.get(ANDROID + "name", "")
    if child.tag == "service" and "JarvisAccessibilityService" not in name:
        application.remove(child)
    elif child.tag == "receiver":
        application.remove(child)
    elif child.tag == "activity" and "VoiceSetupActivity" in name:
        application.remove(child)

# Ensure network access for the hosted web shell. It is not an AI endpoint.
if not any(
    child.tag == "uses-permission" and child.get(ANDROID + "name") == "android.permission.INTERNET"
    for child in list(manifest)
):
    manifest.insert(0, ET.Element("uses-permission", {ANDROID + "name": "android.permission.INTERNET"}))

# Keep the optional accessibility service available for explicit user actions only.
has_accessibility = any(
    child.tag == "service" and "JarvisAccessibilityService" in child.get(ANDROID + "name", "")
    for child in list(application)
)
if not has_accessibility:
    service = ET.SubElement(application, "service", {
        ANDROID + "name": ".JarvisAccessibilityService",
        ANDROID + "label": "Control de pantalla de Jarvis",
        ANDROID + "permission": "android.permission.BIND_ACCESSIBILITY_SERVICE",
        ANDROID + "exported": "true",
    })
    intent_filter = ET.SubElement(service, "intent-filter")
    ET.SubElement(intent_filter, "action", {ANDROID + "name": "android.accessibilityservice.AccessibilityService"})
    ET.SubElement(service, "meta-data", {
        ANDROID + "name": "android.accessibilityservice",
        ANDROID + "resource": "@xml/jarvis_accessibility_service",
    })

tree.write(manifest_path, encoding="utf-8", xml_declaration=True)

main_activity = r'''package com.jarvis.personal

import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.view.ViewGroup
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.Toast
import java.net.URLEncoder

class MainActivity : Activity() {
    private lateinit var webView: WebView
    private var localFallbackLoaded = false
    private val remoteUrl = "https://franyelmartinez618-cloud.github.io/Jarvis_apk/"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = android.graphics.Color.rgb(7, 18, 29)
        window.navigationBarColor = android.graphics.Color.rgb(7, 18, 29)

        webView = WebView(this).apply {
            layoutParams = FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.databaseEnabled = true
            settings.cacheMode = android.webkit.WebSettings.LOAD_DEFAULT
            settings.allowFileAccess = true
            settings.allowContentAccess = false
            settings.allowFileAccessFromFileURLs = false
            settings.allowUniversalAccessFromFileURLs = false
            settings.javaScriptCanOpenWindowsAutomatically = false
            settings.setSupportMultipleWindows(false)
            webChromeClient = WebChromeClient()
            addJavascriptInterface(JarvisWebBridge(this@MainActivity), "JarvisNative")
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                    val uri = request.url
                    val host = uri.host.orEmpty()
                    if (uri.scheme == "file") return false
                    if (host == "franyelmartinez618-cloud.github.io") return false
                    if (uri.scheme == "https" || uri.scheme == "http") {
                        openExternal(uri)
                        return true
                    }
                    return true
                }

                override fun onReceivedError(
                    view: WebView,
                    request: WebResourceRequest,
                    error: WebResourceError
                ) {
                    super.onReceivedError(view, request, error)
                    if (request.isForMainFrame) loadLocalFallback()
                }

                override fun onReceivedHttpError(
                    view: WebView,
                    request: WebResourceRequest,
                    errorResponse: android.webkit.WebResourceResponse
                ) {
                    super.onReceivedHttpError(view, request, errorResponse)
                    if (request.isForMainFrame && errorResponse.statusCode >= 400) loadLocalFallback()
                }
            }
        }
        setContentView(webView)
        showFirstRunNotice()
        webView.loadUrl(remoteUrl)
    }

    private fun showFirstRunNotice() {
        val prefs = getSharedPreferences("jarvis_text_setup", Context.MODE_PRIVATE)
        if (prefs.getBoolean("intro_seen", false)) return
        prefs.edit().putBoolean("intro_seen", true).apply()
        AlertDialog.Builder(this)
            .setTitle("JARVIS · CHAT PRIVADO")
            .setMessage(
                "Esta versión ya no utiliza micrófono ni reconocimiento de voz. Puedes conversar escribiendo; el núcleo local funciona sin enviar mensajes a una IA externa.\\n\\n" +
                "Para pedirle que lea o controle otras aplicaciones, activa voluntariamente el servicio de Accesibilidad desde el menú de Jarvis. No es necesario para conversar."
            )
            .setPositiveButton("ENTENDIDO", null)
            .setNeutralButton("ACTIVAR CONTROL DE PANTALLA") { _, _ -> openAccessibilitySettings() }
            .show()
    }

    private fun loadLocalFallback() {
        if (localFallbackLoaded || isFinishing) return
        localFallbackLoaded = true
        runOnUiThread {
            Toast.makeText(this, "Sin conexión: usando la interfaz local de Jarvis.", Toast.LENGTH_LONG).show()
            webView.loadUrl("file:///android_asset/jarvis/index.html")
        }
    }

    private fun openExternal(uri: Uri) {
        runOnUiThread {
            try {
                startActivity(Intent(Intent.ACTION_VIEW, uri))
            } catch (_: Exception) {
                Toast.makeText(this, "No pude abrir ese enlace.", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun openAccessibilitySettings() {
        try {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        } catch (_: Exception) {
            Toast.makeText(this, "Abre Ajustes > Accesibilidad para activar el control de Jarvis.", Toast.LENGTH_LONG).show()
        }
    }

    override fun onBackPressed() {
        if (::webView.isInitialized && webView.canGoBack()) webView.goBack() else super.onBackPressed()
    }

    override fun onDestroy() {
        if (::webView.isInitialized) {
            webView.removeJavascriptInterface("JarvisNative")
            webView.stopLoading()
            webView.destroy()
        }
        super.onDestroy()
    }

    inner class JarvisWebBridge(private val activity: MainActivity) {
        @JavascriptInterface
        fun perform(action: String, value: String): String {
            return try {
                when (action) {
                    "version" -> packageManager.getPackageInfo(packageName, 0).versionCode.toString()
                    "accessibility_settings" -> {
                        activity.runOnUiThread { openAccessibilitySettings() }
                        "Abriendo los ajustes de Accesibilidad."
                    }
                    "read_screen" -> JarvisAccessibilityService.readScreen()
                        ?: "No tengo acceso a esta pantalla. Activa el control de pantalla en Accesibilidad."
                    "click_text" -> if (JarvisAccessibilityService.clickByText(value)) {
                        "Listo. Pulsé " + value + "."
                    } else {
                        "No encontré ese control. Activa Accesibilidad y comprueba el texto visible."
                    }
                    "type_text" -> if (JarvisAccessibilityService.typeIntoFocusedField(value)) {
                        "Texto escrito en el campo activo."
                    } else {
                        "No encontré un campo de texto activo. Activa Accesibilidad y selecciona primero el campo."
                    }
                    "back" -> if (JarvisAccessibilityService.navigate("back")) "Volviendo atrás." else "Activa Accesibilidad para controlar la pantalla."
                    "home" -> if (JarvisAccessibilityService.navigate("home")) "Volviendo al inicio." else "Activa Accesibilidad para controlar la pantalla."
                    "notifications" -> if (JarvisAccessibilityService.navigate("notifications")) "Abriendo notificaciones." else "Activa Accesibilidad para controlar la pantalla."
                    "quick_settings" -> if (JarvisAccessibilityService.navigate("quick_settings")) "Abriendo ajustes rápidos." else "Activa Accesibilidad para controlar la pantalla."
                    "scroll_down" -> if (JarvisAccessibilityService.scroll(true)) "Desplazando hacia abajo." else "No encontré una zona desplazable."
                    "scroll_up" -> if (JarvisAccessibilityService.scroll(false)) "Desplazando hacia arriba." else "No encontré una zona desplazable."
                    "open_app" -> openApp(value)
                    "web_search" -> {
                        openExternal(Uri.parse("https://www.google.com/search?q=" + URLEncoder.encode(value, "UTF-8")))
                        "Abriendo la búsqueda en el navegador."
                    }
                    "youtube_search" -> {
                        openExternal(Uri.parse("https://www.youtube.com/results?search_query=" + URLEncoder.encode(value, "UTF-8")))
                        "Abriendo la búsqueda en YouTube."
                    }
                    "dial" -> {
                        val number = value.filter { it.isDigit() || it == '+' }
                        if (number.isBlank()) "No recibí un número válido." else {
                            activity.runOnUiThread {
                                try { startActivity(Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + Uri.encode(number)))) }
                                catch (_: Exception) { Toast.makeText(activity, "No pude abrir el marcador.", Toast.LENGTH_SHORT).show() }
                            }
                            "Abriendo el marcador. Tú decides si llamas."
                        }
                    }
                    "open_url" -> {
                        val uri = Uri.parse(value)
                        if (uri.scheme == "https" || uri.scheme == "http") {
                            openExternal(uri)
                            "Abriendo el enlace."
                        } else "Solo puedo abrir enlaces HTTP o HTTPS."
                    }
                    else -> "No conozco esa acción nativa."
                }
            } catch (e: Exception) {
                android.util.Log.e("JarvisWeb", "Falló la acción " + action, e)
                "No pude ejecutar esa acción en Android."
            }
        }

        private fun openApp(query: String): String {
            val wanted = query.trim().lowercase()
            if (wanted.isBlank()) return "Dime el nombre de la aplicación."
            val launcher = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
            val activities = packageManager.queryIntentActivities(launcher, 0)
            val selected = activities.firstOrNull { info ->
                val label = info.loadLabel(packageManager).toString().lowercase()
                label == wanted || label.contains(wanted) || wanted.contains(label)
            } ?: return "No encontré una aplicación con ese nombre."
            val launch = packageManager.getLaunchIntentForPackage(selected.activityInfo.packageName)
                ?: return "Android no ofrece un acceso directo para esa aplicación."
            activity.runOnUiThread {
                try { startActivity(launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
                catch (_: Exception) { Toast.makeText(activity, "Android bloqueó la apertura de la aplicación.", Toast.LENGTH_SHORT).show() }
            }
            return "Abriendo " + selected.loadLabel(packageManager).toString() + "."
        }
    }
}
'''
main_path = root / "app/src/main/java/com/jarvis/personal/MainActivity.kt"
main_path.parent.mkdir(parents=True, exist_ok=True)
main_path.write_text(main_activity, encoding="utf-8")
print("Preparado: WebView híbrido, chat local, sin permiso ni servicio de micrófono.")
