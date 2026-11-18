"""
Coletor de vagas reais (piloto Paraguai) -> dados/vagas-reais.js (usado por index.html).

    python3 coletor_vagas.py            # coleta de verdade (acessa as fontes) e grava dados/vagas-reais.js
    python3 coletor_vagas.py --resumo   # só mostra o resumo do último arquivo gerado

Regras de educação com os sites:
  - User-Agent identificável; 3 s entre pedidos ao mesmo site;
  - robots.txt de cada site é lido e respeitado;
  - 403/429 = a fonte para na hora (não insiste); erro de rede/5xx = até 2 novas tentativas com espera crescente;
  - erro numa fonte não derruba as outras (vai para o log).

Cada fonte tem a mesma interface: fetch_jobs(cliente) -> list[RawJob] (dicionários com os campos de RAW_CAMPOS).
"""

import html
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import urllib.parse
import urllib.robotparser
from datetime import datetime
from urllib.parse import urlparse

PASTA = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(PASTA, "dados", "vagas-reais.js")
LOG = os.path.join(PASTA, "coleta-vagas.log")
UA = "EmpleosParaguayBot/0.1 (+https://github.com/lucasvalladares)"
INTERVALO = 3.0
RAW_CAMPOS = ("fonte", "empresa", "titulo", "cidades", "remoto", "link", "publicado", "vence", "modalidade")


def log(msg):
    linha = "%s %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(linha)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(linha + "\n")


class Parada(Exception):
    pass


class Cliente:
    def __init__(self):
        self.ultimo, self.robots, self.pedidos = {}, {}, 0

    def _permitido(self, url):
        p = urlparse(url)
        base = "%s://%s" % (p.scheme, p.netloc)
        if base not in self.robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                req = urllib.request.Request(base + "/robots.txt", headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=20) as r:
                    rp.parse(r.read().decode("utf-8", "replace").splitlines())
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    raise Parada("robots.txt recusado (HTTP %d) em %s" % (e.code, base))
                rp.parse([])   # sem robots.txt = sem restrições
            except Exception:
                rp.parse([])
            self.robots[base] = rp
            self.pedidos += 1
        return self.robots[base].can_fetch(UA, url)

    def pedir(self, url, dados=None, json_resposta=False):
        if not self._permitido(url):
            raise Parada("proibido pelo robots.txt: " + url)
        host = urlparse(url).netloc
        for tentativa in range(3):
            espera = self.ultimo.get(host, 0) + INTERVALO - time.time()
            if espera > 0:
                time.sleep(espera)
            cab = {"User-Agent": UA, "Accept-Language": "es-PY,es;q=0.9"}
            if dados is not None:
                cab["Content-Type"] = "application/json"
            if json_resposta:
                cab["Accept"] = "application/json"
            req = urllib.request.Request(url, data=json.dumps(dados).encode() if dados is not None else None, headers=cab)
            self.pedidos += 1
            try:
                with urllib.request.urlopen(req, timeout=25) as r:
                    texto = r.read().decode("utf-8", "replace")
                return json.loads(texto) if json_resposta else texto
            except urllib.error.HTTPError as e:
                if e.code in (403, 429):
                    raise Parada("HTTP %d em %s" % (e.code, url))
                if e.code < 500 or tentativa == 2:
                    raise
            except (urllib.error.URLError, TimeoutError):
                if tentativa == 2:
                    raise
            finally:
                self.ultimo[host] = time.time()
            time.sleep(5 * (tentativa + 1))   # nova tentativa com espera crescente


def raw(**kw):
    return {c: kw.get(c) for c in RAW_CAMPOS}


PY = re.compile(r"paraguay|asunci[oó]n|ciudad del este|encarnaci[oó]n", re.I)

# ---------------------------------------------------------------- fontes

LEVER = {"bluelightconsulting": "Bluelight Consulting", "coderio": "Coderio"}


def fetch_lever(cli):
    vagas = []
    for slug, nome in LEVER.items():
        for p in cli.pedir("https://api.lever.co/v0/postings/%s?mode=json" % slug, json_resposta=True):
            locs = p["categories"].get("allLocations") or [p["categories"].get("location") or ""]
            py = [l for l in locs if PY.search(l or "")]
            if py:
                vagas.append(raw(fonte="Lever", empresa=nome, titulo=p["text"].strip(), cidades=py,
                                 remoto=(p.get("workplaceType") == "remote"), link=p["hostedUrl"],
                                 publicado=datetime.fromtimestamp(p["createdAt"] / 1000).strftime("%Y-%m-%d"),
                                 modalidade=p.get("workplaceType")))
    return vagas


def fetch_recruiterflow(cli):
    h = cli.pedir("https://recruiterflow.com/south/jobs")
    i = h.find('"location": [[')
    j = h.index("[", i)
    prof = 0
    for k in range(j, len(h)):
        prof += h[k] == "["
        prof -= h[k] == "]"
        if prof == 0:
            break
    por_id = {}
    for cidade, vs in json.loads(h[j:k + 1]):
        if "Paraguay" not in cidade:
            continue
        for v in vs:
            e = por_id.setdefault(v["job_id"], raw(fonte="Recruiterflow", empresa="South", titulo=v["job_name"], cidades=[],
                                                   remoto=(v.get("remote_type") == "Remote"),
                                                   link="https://recruiterflow.com/" + v["apply_link"],
                                                   publicado=(v.get("last_opened") or "")[:10], modalidade=v.get("remote_type")))
            e["cidades"].append(cidade)
    return list(por_id.values())


def fetch_workday_infobip(cli):
    base = "https://infobip.wd3.myworkdayjobs.com"
    vagas, offset = [], 0
    while True:
        d = cli.pedir(base + "/wday/cxs/infobip/InfobipCareers/jobs", dados={"appliedFacets": {}, "limit": 20, "offset": offset,
                                                                           "searchText": "Asuncion"}, json_resposta=True)
        for j in d.get("jobPostings", []):
            # "2 Locations" = vaga em várias cidades (a busca foi por Asunción)
            if PY.search(j.get("locationsText", "")) or re.match(r"\d+ Locations?$", j.get("locationsText", "")):
                vagas.append(raw(fonte="Workday", empresa="Infobip", titulo=j["title"], cidades=["Asunción"], remoto=False,
                                 link=base + "/InfobipCareers" + j["externalPath"], modalidade="Presencial"))
        offset += 20
        if offset >= (d.get("total") or 0):
            return vagas


def fetch_nestle(cli):
    vagas, vistos = [], set()
    for inicio in range(0, 200, 10):
        h = cli.pedir("https://jobdetails.nestle.com/search/?q=&locationsearch=Asuncion&startrow=%d" % inicio)
        novas = 0
        for caminho, titulo in re.findall(r'<a href="(/job/[^"]+)" class="jobTitle-link[^"]*">([^<]+)</a>', h):
            if caminho in vistos or not re.search(r"/job/Asunci", urllib.parse.unquote(caminho)):   # a cidade vem no endereço
                continue
            vistos.add(caminho)
            novas += 1
            t = html.unescape(titulo).strip()
            vagas.append(raw(fonte="SuccessFactors", empresa="Nestlé", titulo=re.sub(r"\s*\(Asunci[oó]n.*\)$", "", t),
                             cidades=["Asunción"], remoto=False, link="https://jobdetails.nestle.com" + caminho))
        if not re.search(r"startrow=%d" % (inicio + 10), h):   # não há próxima página
            return vagas
    return vagas


def fetch_abc(cli):
    vagas, url = [], "https://empleos.abc.com.py/api/ofertas/?page=1"
    while url:
        d = cli.pedir(url, json_resposta=True)
        for v in d.get("results", []):
            if v.get("estado") != "Abierta":
                continue
            emp = "Empresa confidencial" if v.get("ocultar_empresa") else v["empresa"]["nombre"]
            vagas.append(raw(fonte="ABC Empleos", empresa=emp, titulo=v["nombre_puesto"].strip(),
                             cidades=[c["nombre"] for c in v.get("ciudades") or []],
                             remoto=(v.get("modalidad") or "").lower().startswith("remot"),
                             link="https://empleos.abc.com.py/ofertas/" + v["slug"], publicado=v.get("fecha_publicacion"),
                             vence=v.get("fecha_expiracion"), modalidade=v.get("modalidad")))
        url = d.get("next")
    return vagas


def _payload_next(h):
    """Junta os pedaços de dados que páginas Next.js embutem (self.__next_f.push)."""
    return "".join(json.loads('"%s"' % p) for p in re.findall(r'self\.__next_f\.push\(\[1,"((?:\\.|[^"\\])*)"\]\)', h))


def fetch_jobs_py(cli):
    p = _payload_next(cli.pedir("https://jobs.com.py/es/empleos"))
    setores = sorted(set(re.findall(r'\{"slug":"([a-z0-9-]+)","name":"[^"]+","subsectors":\[[^\]]*\],"count":(\d+)\}', p)))
    vagas, vistos = [], set()
    for slug, n in setores:
        if int(n) == 0:
            continue
        pc = _payload_next(cli.pedir("https://jobs.com.py/es/empleos/" + slug))
        for m in re.finditer(r'\{"id":"\d+","slug":"[^"]+","title":.*?"publishedAt":"[^"]*"', pc):
            try:
                j = json.loads(m.group(0) + "}")
            except ValueError:
                continue
            if j["slug"] in vistos:
                continue
            vistos.add(j["slug"])
            vagas.append(raw(fonte="Jobs Paraguay", empresa=j.get("company") or "Jobs Paraguay (cliente)", titulo=j["title"],
                             cidades=[c for c in [j.get("city"), j.get("department")] if c][:1],
                             remoto=(j.get("modality") or "").lower().startswith("remot"),
                             link="https://jobs.com.py/es/empleos/%s/%s" % (j["sector"], j["slug"]),
                             publicado=j.get("publishedAt"), modalidade=j.get("modality")))
    return vagas


FONTES = [("Lever", fetch_lever), ("Recruiterflow", fetch_recruiterflow), ("Workday (Infobip)", fetch_workday_infobip),
          ("Nestlé", fetch_nestle), ("ABC Empleos", fetch_abc), ("Jobs Paraguay", fetch_jobs_py)]

# ---------------------------------------------------------------- cidades e ocupações


def sem(s):
    s = re.sub(r"(\w)\s*/\s*(?:a|o|as|os|es)\b|(\w)\s*\((?:a|o|as|os)\)", r"\1\2", s or "", flags=re.I)   # "Ejecutivo/a" -> "Ejecutivo"
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower().strip()


PRINCIPAIS = {"asuncion": (-25.300, -57.600), "ciudad-del-este": (-25.515, -54.640), "encarnacion": (-27.340, -55.880),
              "pedro-juan-caballero": (-22.552, -55.748), "concepcion": (-23.405, -57.425)}
# coordenadas aproximadas (centro da cidade); departamentos apontam para a cidade principal deles
LUGARES = {
    "asuncion": ("Asunción", -25.2637, -57.5759), "san lorenzo": ("San Lorenzo", -25.3397, -57.5089),
    "luque": ("Luque", -25.27, -57.4872), "fernando de la mora": ("Fernando de la Mora", -25.32, -57.54),
    "lambare": ("Lambaré", -25.3468, -57.6065), "mariano roque alonso": ("Mariano Roque Alonso", -25.2079, -57.532),
    "capiata": ("Capiatá", -25.3552, -57.4454), "limpio": ("Limpio", -25.1661, -57.4856), "nemby": ("Ñemby", -25.3949, -57.5357),
    "villa elisa": ("Villa Elisa", -25.3676, -57.5927), "itaugua": ("Itauguá", -25.3926, -57.3546), "aregua": ("Areguá", -25.3125, -57.3847),
    "san antonio": ("San Antonio", -25.4213, -57.547), "central": ("Central", -25.3, -57.6),
    "ciudad del este": ("Ciudad del Este", -25.5097, -54.6111), "hernandarias": ("Hernandarias", -25.4056, -54.6383),
    "presidente franco": ("Presidente Franco", -25.5333, -54.6167), "minga guazu": ("Minga Guazú", -25.4833, -54.8),
    "alto parana": ("Alto Paraná", -25.515, -54.64), "encarnacion": ("Encarnación", -27.3306, -55.8667),
    "itapua": ("Itapúa", -27.34, -55.88), "pedro juan caballero": ("Pedro Juan Caballero", -22.5472, -55.7333),
    "amambay": ("Amambay", -22.552, -55.748), "concepcion": ("Concepción", -23.4064, -57.4344),
    "coronel oviedo": ("Coronel Oviedo", -25.4478, -56.44), "caaguazu": ("Caaguazú", -25.4667, -56.0167),
    "villarrica": ("Villarrica", -25.75, -56.4333), "caacupe": ("Caacupé", -25.3861, -57.1408),
    "paraguari": ("Paraguarí", -25.62, -57.15), "san juan bautista": ("San Juan Bautista", -26.6694, -57.1456),
    "pilar": ("Pilar", -26.8667, -58.3), "salto del guaira": ("Salto del Guairá", -24.0633, -54.3069),
    "santa rita": ("Santa Rita", -25.7917, -55.0861), "filadelfia": ("Filadelfia", -22.35, -60.0333),
    "san pedro": ("San Pedro", -24.0917, -57.0778), "katuete": ("Katueté", -24.25, -54.75), "curuguaty": ("Curuguaty", -24.4706, -55.6919),
    "ayolas": ("Ayolas", -27.3986, -56.9006), "san estanislao": ("Santaní", -24.655, -56.4361), "santani": ("Santaní", -24.655, -56.4361),
    "loma plata": ("Loma Plata", -22.3833, -59.85), "san ignacio": ("San Ignacio", -26.8869, -57.0272),
    "hohenau": ("Hohenau", -27.0789, -55.6478), "obligado": ("Obligado", -27.05, -55.6333), "bella vista": ("Bella Vista", -27.05, -55.5833),
    "cambyreta": ("Cambyretá", -27.3333, -55.75), "valenzuela": ("Valenzuela", -25.55, -56.97),
    "villa hayes": ("Villa Hayes", -25.0939, -57.5236), "villeta": ("Villeta", -25.5097, -57.5567),
    "ypacarai": ("Ypacaraí", -25.4089, -57.2889), "guarambare": ("Guarambaré", -25.4917, -57.4556), "ypane": ("Ypané", -25.45, -57.53), "fram": ("Fram", -26.9833, -56.0), "maria auxiliadora": ("María Auxiliadora", -26.5333, -55.25),
}


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    return 6371 * 2 * math.asin(math.sqrt(math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2))


def lugar(textos):
    """Primeira cidade reconhecida -> (id_grupo, nome, lat, lng). Até 35 km de uma das 5 principais, entra no grupo dela."""
    for t in textos or []:
        s = sem(re.sub(r",?\s*paraguay.*$", "", t or "", flags=re.I))
        s = re.sub(r"\s*\(.*\)$", "", s)
        for chave in sorted(LUGARES, key=len, reverse=True):
            if s == chave or s.startswith(chave + ",") or s.startswith(chave + " "):
                nome, lat, lng = LUGARES[chave]
                perto = min(PRINCIPAIS, key=lambda c: km(PRINCIPAIS[c], (lat, lng)))
                grupo = perto if km(PRINCIPAIS[perto], (lat, lng)) <= 35 else re.sub(r"[^a-z0-9]+", "-", sem(nome)).strip("-")
                return grupo, nome, lat, lng
    return None


# palavra-chave (sem acento, minúsculas) -> ocupação da lista dados/ocupaciones.js. A primeira que casar vence.
REGRAS = [
    (r"devops|\bsre\b|site reliability", "DevOps / SRE"), (r"data engineer|ingenier\w* de datos", "Ingeniero/a de datos"),
    (r"data scien|cientific\w* de datos", "Científico/a de datos"), (r"machine learning|\bml\b|\bai\b|inteligencia artificial", "Especialista en IA / Machine Learning"),
    (r"\bqa\b|tester|quality assurance", "QA / Tester de software"), (r"front[- ]?end", "Desarrollador/a frontend"),
    (r"back[- ]?end", "Desarrollador/a backend"), (r"full[- ]?stack", "Desarrollador/a full stack"),
    (r"mobile|android|\bios\b|react native", "Desarrollador/a mobile (iOS / Android)"),
    (r"\breact\b|angular|\bvue\b", "Desarrollador/a frontend"), (r"encargad\w* de ti\b|\bti\b|\bit\b intern", "Soporte técnico IT"),
    (r"salesforce|software engineer|developer|desarrollador|programador|elixir|\.net|java\b|python", "Programador/a"),
    (r"network|redes|telecom|infraestructura|voice|platform operations", "Administrador/a de redes e infraestructura"),
    (r"ciberseguridad|cybersecurity|security|\bsoc\b", "Especialista en ciberseguridad"),
    (r"\bbi\b|business intelligence|power bi", "Analista de BI (Business Intelligence)"), (r"data analyst|analista de datos", "Analista de datos"),
    (r"ux|ui designer|product designer", "Diseñador/a UX/UI"), (r"product manager|product owner", "Product manager / Product owner"),
    (r"project manager|coordinador\w* de proyecto|jefe de proyecto", "Project manager de TI"),
    (r"solution\w* engineer|preventa|pre-?sales", "Analista de sistemas"),
    (r"talent acquisition|recruit|reclut|seleccion|recursos humanos|\brrhh\b|people|human\w* resources|\bhr\b|nomina|payroll|compensac", "Recursos humanos"),
    (r"community manager|social media|redes sociales", "Community manager"), (r"content creator|video editor|creador\w* de contenido", "Diseñador/a gráfico/a"),
    (r"marketing|growth|seo|performance digital", "Marketing"), (r"dise[nñ]ador|graphic", "Diseñador/a gráfico/a"),
    (r"cajer", "Cajero/a"), (r"cobranz|cobrador|collections", "Gestor/a de cobranzas"),
    (r"call center|contact center|telemarketing|televent", "Agente de call center"),
    (r"atencion al cliente|customer service|customer support|servicio al cliente|customer experience|\bcx\b", "Atención al cliente"),
    (r"account executive|ejecutiv\w* (comercial|de ventas|de cuentas)|business development|\bsdr\b|sales development|asesor\w* (comercial|de ventas|de inversiones|financier)|key account", "Ejecutivo/a de ventas"),
    (r"ejecutivo (comercial|de negocios)|asesor (comercial|de inversiones)", "Ejecutivo/a de ventas"),
    (r"asesor de servicios", "Atención al cliente"), (r"vendedor|ventas|sales", "Vendedor/a"), (r"promotor", "Promotor/a"), (r"repositor", "Repositor/a"),
    (r"contador|contable|accounting|cuentas por (cobrar|pagar)|accounts (payable|receivable)|conciliacion|o2c|p2p|r2r", "Auxiliar contable"),
    (r"tesorer|treasury", "Analista de tesorería y recaudaciones"), (r"auditor", "Auditor/a"), (r"compliance|cumplimiento", "Oficial de cumplimiento (compliance)"),
    (r"fraude|fraud", "Analista de prevención de fraudes"), (r"riesgo|risk", "Analista de riesgo operacional"),
    (r"credito|credit", "Analista de créditos"), (r"financ|finanzas", "Analista financiero/a"), (r"planificador", "Analista de procesos / mejora continua"), (r"procesos|mejora continua|process", "Analista de procesos / mejora continua"),
    (r"calidad|quality", "Analista de control de calidad"), (r"comercio exterior|comex|freight|aduan", "Analista de comercio exterior"),
    (r"logistic|deposito|almacen|warehouse|supply chain|abastecimiento|compras|procurement", "Auxiliar de logística"),
    (r"chofer|conductor|driver", "Chofer"), (r"delivery|repartidor|motociclista", "Delivery / Repartidor/a"),
    (r"recepcionista|recepcion", "Recepcionista"), (r"secretari", "Secretario/a"),
    (r"asistente administrativ|auxiliar administrativ|administrativ|back office|backoffice", "Administrativo/a"),
    (r"abogad|legal|juridic", "Abogado/a"), (r"enfermer", "Enfermero/a"), (r"farmac", "Auxiliar de farmacia"), (r"medic", "Médico/a"),
    (r"docente|profesor|teacher", "Docente"), (r"cociner|chef", "Cocinero/a"), (r"mozo|camarer|mesero", "Mozo/a"), (r"barista", "Barista"),
    (r"guardia|seguridad fisica|vigilante|anfitrion de seguridad", "Guardia de seguridad"),
    (r"limpieza|mantenimiento|conserjeria|servicios generales", "Personal de limpieza"), (r"pintor", "Pintor/a"),
    (r"aprendi[zc]|operador", "Operario/a de producción"), (r"documentacion|asistente", "Administrativo/a"), (r"encargad|sub-?encargad", "Supervisor/a"),
    (r"electricista", "Electricista"), (r"mecanic", "Mecánico/a automotriz"), (r"soldador", "Soldador/a"), (r"operari", "Operario/a de producción"),
    (r"tecnico", "Técnico/a electrónico/a"), (r"ingenier\w* civil|obra", "Ingeniero/a civil"), (r"arquitect", "Arquitecto/a"),
    (r"agronom", "Ingeniero/a agrónomo/a"), (r"veterinar", "Veterinario/a"), (r"inmobiliari", "Agente inmobiliario/a"),
    (r"soporte|help ?desk|mesa de ayuda|it support", "Soporte técnico IT"), (r"gerente|manager|director|head of|jefe", "Gerente"),
    (r"supervisor|lider|lead\b|coordinador", "Supervisor/a"), (r"analista|analyst|specialist|especialista", "Administrativo/a"),
]
OUTRAS = "Otras ocupaciones"


def ocupacao(titulo):
    s = sem(titulo)
    for padrao, ocup in REGRAS:
        if re.search(padrao, s):
            return ocup
    return OUTRAS


# ---------------------------------------------------------------- montar


def montar(raws):
    vistos, vagas, extras, sem_lugar = set(), [], {}, []
    for r in raws:
        if re.search(r"base de talento|banco de talento|postulaci[oó]n abierta|talent pool", r["titulo"], re.I):
            continue   # cadastro de currículos, não é uma vaga
        lg = lugar(r["cidades"])
        chave = (sem(r["empresa"]), sem(re.sub(r"\s*[-–(].*$", "", r["titulo"])), "" if r["remoto"] else (lg[1] if lg else ""), r["remoto"])
        if chave in vistos:   # deduplicação: empresa + título normalizado + cidade
            continue
        vistos.add(chave)
        if not lg and not r["remoto"]:
            sem_lugar.append(r["cidades"])
        if lg and lg[0] not in PRINCIPAIS and not r["remoto"]:
            extras.setdefault(lg[0], {"id": lg[0], "nome": lg[1], "lat": lg[2], "lng": lg[3]})
        vagas.append({"id": len(vagas) + 1, "ocupacion": ocupacao(r["titulo"]), "titulo": r["titulo"], "empresa": r["empresa"],
                      "ciudad": None if r["remoto"] or not lg else lg[0], "ciudadNombre": lg[1] if lg else None,
                      "remoto": bool(r["remoto"]), "link": r["link"], "fuente": r["fonte"], "publicado": r.get("publicado"),
                      "vence": r.get("vence"), "modalidad": r.get("modalidade")})
    return vagas, list(extras.values()), sem_lugar


def main():
    if "--resumo" in sys.argv:
        resumo()
        return
    cli, raws, status = Cliente(), [], []
    inicio = time.time()
    for nome, f in FONTES:
        t0, antes = time.time(), cli.pedidos
        try:
            lote = f(cli)
            raws += lote
            status.append({"fuente": nome, "vagas": len(lote), "erro": None})
            log("%-20s %3d vagas · %2d pedidos · %3.0fs" % (nome, len(lote), cli.pedidos - antes, time.time() - t0))
        except Exception as e:
            status.append({"fuente": nome, "vagas": 0, "erro": "%s: %s" % (type(e).__name__, str(e)[:150])})
            log("%-20s ERRO %s: %s" % (nome, type(e).__name__, str(e)[:150]))
    vagas, extras, sem_lugar = montar(raws)
    dados = {"geradoEm": datetime.now().strftime("%d/%m/%Y %H:%M"), "fontes": status}
    with open(SAIDA, "w", encoding="utf-8") as f:
        f.write("// VACANTES REALES coletadas por coletor_vagas.py em %s (não editar à mão).\n" % dados["geradoEm"])
        f.write("window.VAGAS_TESTE = false;\nwindow.COLETA = %s;\n" % json.dumps(dados, ensure_ascii=False))
        f.write("window.CIDADES_EXTRA = %s;\n" % json.dumps(extras, ensure_ascii=False))
        f.write("window.VAGAS = %s;\n" % json.dumps(vagas, ensure_ascii=False, indent=0))
    log("Total: %d vagas brutas -> %d após deduplicar · %d pedidos · %.0fs" % (len(raws), len(vagas), cli.pedidos, time.time() - inicio))
    if sem_lugar:
        log("Cidades não reconhecidas (vão para 'Sin ciudad'): %s" % sorted({str(x) for x in sem_lugar})[:20])
    resumo()


def resumo():
    txt = open(SAIDA, encoding="utf-8").read()
    vagas = json.loads(re.search(r"window\.VAGAS = (.*);\n", txt, re.S).group(1))
    from collections import Counter
    print("\nPor fonte:", Counter(v["fuente"] for v in vagas).most_common())
    print("Por lugar:", Counter(v["ciudad"] or ("remoto" if v["remoto"] else "sin ciudad") for v in vagas).most_common())
    print("Ocupação 'Otras':", sum(v["ocupacion"] == OUTRAS for v in vagas), "de", len(vagas))


if __name__ == "__main__":
    main()
