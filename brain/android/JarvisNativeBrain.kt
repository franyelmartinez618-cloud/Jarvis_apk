package com.jarvis.personal

import android.content.Context
import java.io.ByteArrayInputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.text.Normalizer
import java.util.Locale
import kotlin.math.exp
import kotlin.math.sqrt

/**
 * First-party JARVIS language core.
 *
 * It loads only checkpoints created by brain/train.py + brain/export_android.py.
 * There is deliberately no bundled third-party language model or hosted LLM.
 * When no trained checkpoint exists, it uses a small transparent local knowledge
 * index and reports that neural training is still pending.
 */
internal class JarvisNativeBrain(context: Context) {
    private val neural: NativeTransformer? = try {
        context.assets.open("jarvis-brain.bin").use { NativeTransformer(it.readBytes()) }
    } catch (_: Exception) {
        null
    }

    fun status(): String = if (neural == null) {
        "Motor propio inicializado · núcleo local activo · checkpoint neuronal pendiente de entrenamiento"
    } else {
        "Motor neuronal propio JARVIS cargado desde su checkpoint"
    }

    fun reply(input: String, history: List<Pair<String, String>>): String {
        val clean = input.trim()
        if (clean.isEmpty()) return "Te escucho. ¿Qué necesitas?"
        if (neural != null) {
            val prompt = buildString {
                history.takeLast(6).forEach { (role, message) ->
                    append(if (role == "user") "Usuario: " else "JARVIS: ")
                    append(message)
                    append('\n')
                }
                append("Usuario: ").append(clean).append('\n')
                append("JARVIS:")
            }
            val generated = runCatching { neural.generate(prompt, 180) }.getOrNull()?.trim().orEmpty()
            val safe = generated.substringBefore("\nUsuario:").substringBefore("\nJARVIS:").trim()
            if (safe.length >= 2) return safe.take(1600)
        }
        return retrieveLocalKnowledge(clean)
    }

    private data class Note(val terms: Set<String>, val answer: String)

    private val notes = listOf(
        Note(setOf("quien", "eres", "jarvis", "identidad"), "Soy JARVIS, el asistente personal de este teléfono. Mi motor conversacional propio está siendo construido y entrenado desde inicialización aleatoria; no utilizo Qwen ni otro modelo de lenguaje de terceros."),
        Note(setOf("como", "funcionas", "motor", "cerebro", "modelo", "entrenamiento"), "Mi arquitectura neuronal propia está implementada en este proyecto. El código y los pesos iniciales son nuestros. Todavía falta reunir un corpus amplio y lícito, entrenar el checkpoint y evaluarlo antes de afirmar que tengo conocimiento general."),
        Note(setOf("qwen", "llama", "gemma", "chatgpt", "terceros", "externo"), "El motor de conversación de JARVIS no descarga ni ejecuta Qwen, Llama, Gemma, ChatGPT ni otro modelo lingüístico externo. El reconocimiento de voz se mantiene separado del razonamiento: solo convierte audio en texto."),
        Note(setOf("que", "puedes", "hacer", "capacidades", "funciones", "ayuda"), "Puedo ejecutar las funciones Android que están implementadas: abrir aplicaciones instaladas, abrir cámara, controlar linterna, configurar alarmas y temporizadores, abrir mapas o búsquedas web y ajustar algunos controles del teléfono. Las funciones sensibles o protegidas dependen de permisos de Android y confirmación."),
        Note(setOf("abrir", "aplicacion", "app", "telefono"), "Puedo buscar y abrir aplicaciones que Android muestre en el lanzador. Di, por ejemplo: «abre WhatsApp» o «abre YouTube»."),
        Note(setOf("alarma", "despertador", "hora"), "Puedo abrir el reloj de Android con una alarma preparada. Debes revisar la hora y guardar la alarma en la aplicación del reloj."),
        Note(setOf("temporizador", "timer", "cuenta", "regresiva"), "Puedo preparar un temporizador en la aplicación de reloj de Android. Dime cuánto debe durar, por ejemplo: «pon un temporizador de cinco minutos»."),
        Note(setOf("linterna", "flash", "camara", "foto"), "Puedo abrir la cámara y controlar la linterna cuando Android haya concedido el permiso de cámara."),
        Note(setOf("buscar", "internet", "web", "google", "mapas", "maps"), "Puedo abrir una búsqueda web o una ubicación en mapas. La búsqueda se realiza en el navegador; todavía no significa que el motor neuronal haya leído y comprendido automáticamente cada página."),
        Note(setOf("contactos", "llamar", "telefono", "sms", "whatsapp", "mensaje"), "Las llamadas y los mensajes requieren permisos y una confirmación antes de ejecutar la acción. No debo afirmar que he llamado o enviado algo si Android no confirma el resultado."),
        Note(setOf("permiso", "permisos", "acceso", "accesibilidad"), "Android controla los permisos. JARVIS puede solicitar permisos normales cuando corresponda y abrir Ajustes para accesos especiales como Accesibilidad, mostrar sobre otras aplicaciones o modificar ajustes del sistema. No puede concederse esos permisos a sí mismo."),
        Note(setOf("privacidad", "datos", "local", "conexion", "nube"), "El procesamiento conversacional previsto es local en el teléfono. Las búsquedas web abren el navegador y, por tanto, necesitan conexión. No afirmo que una búsqueda externa sea procesamiento offline."),
        Note(setOf("voz", "hablar", "escuchar", "microfono"), "El micrófono necesita permiso. El reconocedor de voz transcribe lo que dices; es una pieza separada del motor de razonamiento propio. La voz que responde depende del motor de síntesis instalado en Android."),
        Note(setOf("entrenar", "datos", "corpus", "conocimiento", "informacion"), "Para aprender necesito documentos propios o con licencia que permita entrenamiento. El proyecto ya tiene tokenizador byte-level, arquitectura Transformer causal, entrenamiento desde cero y exportación a un formato que el runtime Android puede leer. No existe todavía un checkpoint general entrenado.")
    )

    private fun retrieveLocalKnowledge(input: String): String {
        val normalized = normalize(input)
        val words = normalized.split(Regex("\\s+")).filter { it.length >= 3 }.toSet()
        if (words.isEmpty()) return "No logré identificar la pregunta. ¿Puedes expresarla de otra manera?"
        val best = notes.map { note ->
            val overlap = words.intersect(note.terms).size
            val phraseBoost = if (note.terms.any { normalized.contains(it) }) 1 else 0
            note to (overlap * 2 + phraseBoost)
        }.maxByOrNull { it.second }
        if (best != null && best.second >= 2) return best.first.answer
        return "Todavía no tengo conocimiento entrenado suficiente para responder eso con fiabilidad. Mi motor propio está preparado, pero necesita un corpus amplio y un checkpoint entrenado. Puedo abrir una búsqueda web si me pides que busque ese tema."
    }

    private fun normalize(value: String): String =
        Normalizer.normalize(value.lowercase(Locale.ROOT), Normalizer.Form.NFD)
            .replace(Regex("\\p{Mn}+"), "")
            .replace(Regex("[^a-z0-9 ]"), " ")
            .replace(Regex("\\s+"), " ")
            .trim()
}

private class NativeTransformer(bytes: ByteArray) {
    private val context: Int
    private val width: Int
    private val layers: List<Layer>
    private val tokenEmbedding: FloatArray
    private val positionEmbedding: FloatArray
    private val finalNormWeight: FloatArray
    private val finalNormBias: FloatArray
    private val vocab: Int

    private data class Layer(
        val n1w: FloatArray, val n1b: FloatArray,
        val qkvw: FloatArray, val projw: FloatArray,
        val n2w: FloatArray, val n2b: FloatArray,
        val fc1w: FloatArray, val fc1b: FloatArray,
        val fc2w: FloatArray, val fc2b: FloatArray
    )

    init {
        val input = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        val magic = ByteArray(8).also { input.get(it) }
        require(String(magic, Charsets.US_ASCII) == "JARVIS01") { "Invalid JARVIS checkpoint" }
        vocab = input.int
        context = input.int
        width = input.int
        val count = input.int
        val heads = input.int
        require(vocab == 260 && context in 32..1024 && width in 32..512 && count in 1..12 && width % heads == 0)
        tokenEmbedding = readFloats(input, vocab * width)
        positionEmbedding = readFloats(input, context * width)
        layers = (0 until count).map {
            Layer(
                readFloats(input, width), readFloats(input, width),
                readFloats(input, 3 * width * width), readFloats(input, width * width),
                readFloats(input, width), readFloats(input, width),
                readFloats(input, 4 * width * width), readFloats(input, 4 * width),
                readFloats(input, width * 4 * width), readFloats(input, width)
            )
        }
        finalNormWeight = readFloats(input, width)
        finalNormBias = readFloats(input, width)
        require(input.remaining() == 0) { "JARVIS checkpoint has trailing or missing data" }
    }

    fun generate(prompt: String, maxTokens: Int): String {
        val ids = prompt.toByteArray(Charsets.UTF_8).map { it.toInt() and 0xff }.toMutableList()
        val initialSize = ids.size
        repeat(maxTokens.coerceIn(1, 256)) {
            val token = next(ids)
            if (token == 257 || token == 258) return@repeat
            ids.add(token)
        }
        val generated = ids.drop(initialSize).filter { it in 0..255 }.map { it.toByte() }.toByteArray()
        return String(generated, Charsets.UTF_8)
    }

    private fun next(all: List<Int>): Int {
        val ids = all.takeLast(context)
        val length = ids.size
        var x = Array(length) { t ->
            FloatArray(width) { c ->
                tokenEmbedding[ids[t] * width + c] + positionEmbedding[t * width + c]
            }
        }
        layers.forEach { layer ->
            val norm1 = layerNorm(x, layer.n1w, layer.n1b)
            val qkv = linear(norm1, layer.qkvw, null, width * 3)
            val attended = attention(qkv, length, width, 4)
            val projected = linear(attended, layer.projw, null, width)
            x = add(x, projected)
            val norm2 = layerNorm(x, layer.n2w, layer.n2b)
            val hidden = linear(norm2, layer.fc1w, layer.fc1b, width * 4).map { row ->
                FloatArray(row.size) { i -> gelu(row[i]) }
            }.toTypedArray()
            x = add(x, linear(hidden, layer.fc2w, layer.fc2b, width))
        }
        val last = x[length - 1]
        val mean = last.average().toFloat()
        var variance = 0f
        for (v in last) { val d = v - mean; variance += d * d }
        variance /= width
        val scale = 1.0f / sqrt(variance + 1e-5f)
        val logits = FloatArray(vocab)
        for (token in 0 until vocab) {
            var score = 0f
            for (i in 0 until width) {
                val normalized = (last[i] - mean) * scale * finalNormWeight[i] + finalNormBias[i]
                score += normalized * tokenEmbedding[token * width + i]
            }
            logits[token] = score
        }
        var best = 0
        for (i in 1 until logits.size) if (logits[i] > logits[best]) best = i
        return best
    }

    private fun attention(qkv: Array<FloatArray>, length: Int, dim: Int, heads: Int): Array<FloatArray> {
        require(dim % heads == 0)
        val headDim = dim / heads
        val out = Array(length) { FloatArray(dim) }
        val scale = 1.0 / sqrt(headDim.toDouble())
        for (t in 0 until length) {
            for (h in 0 until heads) {
                val scores = DoubleArray(t + 1)
                var maxScore = Double.NEGATIVE_INFINITY
                for (s in 0..t) {
                    var dot = 0.0
                    for (d in 0 until headDim) {
                        val qi = qkv[t][h * headDim + d].toDouble()
                        val ki = qkv[s][dim + h * headDim + d].toDouble()
                        dot += qi * ki
                    }
                    scores[s] = dot * scale
                    if (scores[s] > maxScore) maxScore = scores[s]
                }
                var sum = 0.0
                for (s in scores.indices) { scores[s] = exp(scores[s] - maxScore); sum += scores[s] }
                for (d in 0 until headDim) {
                    var value = 0.0
                    for (s in 0..t) {
                        val weight = scores[s] / sum
                        value += weight * qkv[s][2 * dim + h * headDim + d]
                    }
                    out[t][h * headDim + d] = value.toFloat()
                }
            }
        }
        return out
    }

    private fun layerNorm(x: Array<FloatArray>, weight: FloatArray, bias: FloatArray): Array<FloatArray> =
        Array(x.size) { t ->
            val mean = x[t].average().toFloat()
            var variance = 0f
            for (v in x[t]) { val d = v - mean; variance += d * d }
            variance /= width
            val scale = 1f / sqrt(variance + 1e-5f)
            FloatArray(width) { i -> (x[t][i] - mean) * scale * weight[i] + bias[i] }
        }

    private fun linear(x: Array<FloatArray>, weight: FloatArray, bias: FloatArray?, output: Int): Array<FloatArray> =
        Array(x.size) { t ->
            FloatArray(output) { o ->
                var sum = bias?.get(o) ?: 0f
                val offset = o * x[t].size
                for (i in x[t].indices) sum += weight[offset + i] * x[t][i]
                sum
            }
        }

    private fun add(a: Array<FloatArray>, b: Array<FloatArray>): Array<FloatArray> =
        Array(a.size) { t -> FloatArray(a[t].size) { i -> a[t][i] + b[t][i] } }

    private fun gelu(value: Float): Float {
        val x = value.toDouble()
        val sign = if (x < 0) -1.0 else 1.0
        val z = kotlin.math.abs(x) / sqrt(2.0)
        val t = 1.0 / (1.0 + 0.3275911 * z)
        val erf = sign * (1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * exp(-z * z))
        return (0.5 * x * (1.0 + erf)).toFloat()
    }

    private fun readFloats(input: ByteBuffer, count: Int): FloatArray =
        FloatArray(count) { input.float }
}
