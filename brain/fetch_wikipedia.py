"""Descarga extractos como datos de conocimiento, nunca pesos o modelos de IA."""
from __future__ import annotations
import argparse,json,time,urllib.parse,urllib.request
from pathlib import Path
TOPICS=[
"Matemáticas","Aritmética","Álgebra","Geometría","Trigonometría","Cálculo","Estadística","Probabilidad","Lógica","Filosofía",
"Física","Mecánica clásica","Termodinámica","Electricidad","Magnetismo","Óptica","Química","Química orgánica","Tabla periódica",
"Biología","Célula","ADN","Genética","Evolución","Ecología","Anatomía humana","Sistema nervioso","Sistema circulatorio","Sistema respiratorio",
"Nutrición","Astronomía","Sistema solar","Sol","Tierra","Luna","Marte","Júpiter","Saturno","Vía Láctea","Agujero negro",
"Historia","Historia de Colombia","Historia de América","Geografía","Geografía de Colombia","América del Sur","Océano Pacífico","Amazonas",
"Informática","Programación","Algoritmo","Python","Java","Kotlin","JavaScript","HTML","CSS","Base de datos","Internet","Ciberseguridad",
"Inteligencia artificial","Aprendizaje automático","Red neuronal artificial","Transformador (modelo de aprendizaje profundo)","Procesamiento de lenguaje natural","Criptografía",
"Economía","Microeconomía","Macroeconomía","Inflación","Presupuesto","Energía renovable","Cambio climático","Agricultura","Medicina","Salud pública",
"Psicología","Aprendizaje","Comunicación","Literatura","Arte","Música","Arquitectura","Ingeniería","Robótica","Derecho","Constitución de Colombia",
"Democracia","Ciencias sociales","Sociología","Antropología","Lingüística","Español","Inglés","Reino Unido","Colombia","Bogotá","Atlántico (Colombia)",
"Química inorgánica","Bioquímica","Nanotecnología","Mecánica cuántica","Relatividad general","Meteorología","Oceanografía","Geología","Botánica","Zoología",
"Farmacología","Epidemiología","Cardiología","Neurología","Fisiología","Ingeniería eléctrica","Ingeniería civil","Ingeniería mecánica",
"Sistemas operativos","Linux","Android (sistema operativo)","Red de computadoras","Internet de las cosas","Computación cuántica","Energía solar","Energía eólica",
"Administración","Contabilidad","Comercio","Emprendimiento","Derechos humanos","Derecho laboral","Departamento del Atlántico","Malambo","Barranquilla","Cartagena de Indias",
"Historia del arte","Fotografía","Educación","Método científico","Ética","Sostenibilidad","Reciclaje","Biodiversidad","Ecosistema","Desarrollo sostenible"
]
def fetch(title):
    path="/api/rest_v1/page/summary/"+urllib.parse.quote(title.replace(" ","_"),safe="()_,")
    req=urllib.request.Request("https://es.wikipedia.org"+path,headers={"User-Agent":"JARVIS-owned-brain/0.1 (personal education assistant)"})
    try:
        with urllib.request.urlopen(req,timeout=20) as response: data=json.loads(response.read().decode("utf-8"))
        extract=data.get("extract","").strip(); url=data.get("content_urls",{}).get("desktop",{}).get("page","")
        if len(extract)<100:return None
        return {"title":data.get("title",title),"extract":extract,"url":url,"license":"CC BY-SA; attribution required"}
    except Exception as error:
        print(f"skip {title}: {error}"); return None
def main():
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,default=Path(__file__).parent/"corpus"/"wikipedia_es.txt")
    p.add_argument("--limit",type=int,default=len(TOPICS));p.add_argument("--delay",type=float,default=.12);a=p.parse_args()
    a.output.parent.mkdir(parents=True,exist_ok=True);records=[]
    for index,title in enumerate(TOPICS[:a.limit],1):
        row=fetch(title)
        if row: records.append(row);print(f"[{index}/{min(a.limit,len(TOPICS))}] {row['title']}")
        time.sleep(max(0,a.delay))
    a.output.write_text("\n\n".join(f"TEMA: {r['title']}\n{r['extract']}\nFuente: {r['url']}\nLicencia: {r['license']}" for r in records),encoding="utf-8")
    (a.output.parent/"wikipedia_sources.json").write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Extractos guardados: {len(records)}")
if __name__=="__main__":main()
