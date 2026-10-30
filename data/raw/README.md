# Corpus de entrenamiento de JARVIS

Coloca aquí documentos .txt, .md o .jsonl que puedas usar legalmente para entrenar y redistribuir un modelo, y registra cada archivo en SOURCES.json.

No se incorporan automáticamente páginas web ni datasets de licencias ambiguas. Para el perfil de entrenamiento grande se exige que cada fuente autorice expresamente entrenamiento y uso comercial. Se aceptan:

- CC0-1.0
- Public-Domain (con justificación de jurisdicción y fecha)
- CC-BY-4.0 (con atribución)
- Owner-Created
- Permission-Granted (con evidencia escrita)

No se aceptan automáticamente licencias no comerciales (NC), share-alike (SA), licencias desconocidas ni términos que prohíban entrenamiento. OpenStax publica sus textos actuales bajo CC BY-NC-SA y exige solicitar permiso para uso comercial o proyectos de IA; por eso no se añade como fuente predeterminada. Wikipedia requiere atribución y obligaciones ShareAlike CC BY-SA, así que tampoco se incluye por defecto.

Ejemplo de registro para un archivo propio:

    {
      "file": "manuales/mi_manual.txt",
      "source": "Manual original del propietario del proyecto",
      "url": "",
      "license": "Owner-Created",
      "training_allowed": true,
      "commercial_use": true,
      "attribution": "Texto original del propietario del proyecto"
    }

El proceso detiene el entrenamiento si falta el registro, si el archivo no está autorizado o si no hay evidencia de los permisos exigidos. No añadas contraseñas, conversaciones privadas de terceros ni datos personales sensibles.
