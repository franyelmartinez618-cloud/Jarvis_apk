# Datos de entrenamiento de JARVIS

`seed/jarvis_core.jsonl` contiene 48 ejemplos originales redactados para este proyecto. Describen identidad, capacidades Android, permisos, confirmaciones, privacidad y arquitectura. Es una base de comportamiento e identidad, **no** un corpus de conocimiento general.

Añade fuentes externas solo cuando permitan expresamente entrenamiento. Registra URL, autor, licencia, fecha y finalidad en `sources.jsonl`. Para textos propios o con licencia compatible usa TXT, Markdown o JSONL con campo `text`.

No incluyas datos personales privados, credenciales, conversaciones ajenas ni contenido sin permiso. El pipeline no descarga corpus automáticamente. El entrenamiento no debe comenzar con datos insuficientes ni se debe confundir una pérdida baja en un corpus diminuto con inteligencia general.
