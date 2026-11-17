# Fase 1 — Levantamento de fontes de vagas no Paraguai

Levantamento feito em **17/11/2026**. Os números são de hoje e mudam todo dia.

**Como foi feito:**
- buscas na web e consulta direta às interfaces públicas dos ATS e ao `robots.txt` de cada site;
- poucos pedidos por site, com 2–3 s entre eles e identificação `EmpleosParaguayBot/0.1`;
- nenhum login e nenhuma tentativa de contornar bloqueios.

**Legenda:**
- **Permitido:** sim = robots.txt e termos não impedem; não = termos ou bloqueio impedem; dúvida = falta confirmar os termos.
- **Esforço:** baixo = API/JSON pública estável; médio = HTML ou JSON interno, ou exige adaptador por empresa; alto = login, imagens/OCR ou convênio.
- **Vagas PY hoje:** vagas distintas localizadas no Paraguai ou remotas abertas explicitamente ao Paraguai.

> Um erro meu durante o levantamento: fiz 2 pedidos ao RSS da Nestlé (`/services/rss/...`) antes de ler o robots.txt dela,
> que proíbe `/services/`. Esse caminho **não** será usado. A coleta da Nestlé, se aprovada, usará só a busca HTML, que é permitida.

---

## A) ATS e sites de carreira de empresas

| Fonte | ATS | URL | Acesso | Login? | Como filtrar PY | Vagas PY hoje | Permitido | Esforço |
|---|---|---|---|---|---|---|---|---|
| **Bluelight Consulting** | Lever | `api.lever.co/v0/postings/bluelightconsulting?mode=json` | API pública JSON | não | `categories.location` / `allLocations` contém "Paraguay" | **8** distintas (24 anúncios: as mesmas 8 em Asunción, CDE e Encarnación; todas remotas) | sim | baixo |
| **South** (staffing EUA → LATAM) | Recruiterflow | `recruiterflow.com/south/jobs` | JSON embutido no HTML (`location: [[cidade, [vagas]]]`) | não | chave de cidade "Asunción, Paraguay" / "Ciudad del Este, Paraguay" | **13** distintas (7 Asunción, 11 CDE, com sobreposição; quase todas remotas) | sim (robots libera tudo) | baixo |
| **Nestlé** (Integrated Business Services LATAM, Asunción) | SAP SuccessFactors | `jobdetails.nestle.com/search/?q=&locationsearch=Asuncion` | HTML (o RSS existe, mas `/services/` é proibido no robots) | não | `locationsearch=Asuncion` + título "(Asunción, PY, …)" | **22** | sim (só a busca HTML) | médio |
| **Infobip** (escritório Asunción) | Workday | `infobip.wd3.myworkdayjobs.com/InfobipCareers` | JSON (endpoint `wday/cxs/...` que o próprio site usa) | não | `searchText`, depois `locationsText = "Asuncion (Paraguay)"` | **11** | sim (robots libera `/InfobipCareers/`); endpoint não documentado | médio |
| **Coderio** | Lever | `api.lever.co/v0/postings/coderio?mode=json` | API pública JSON | não | `allLocations` contém "Asunción" | **1** (remota LATAM) | sim | baixo |
| **Citi** (Asunción) | Radancy/TalentBrew (Workday por trás) | `jobs.citi.com/location/asuncion-paraguay-jobs/287/3437598-3474570/3` | HTML (`/search-jobs/` proibido no robots; páginas de local permitidas) | não | página de localização Asunción | **0** hoje | sim (páginas de local) | médio |
| **Sistema ONU** (PNUD, OIT, UNICEF, ACNUR, PNUMA…) | vários | `unjobnet.org/countries/Paraguay/Asuncion` | HTML agregador (robots só bloqueia `/jd/`, `/go/`, `/salaryscale/`) | não | página do país/cidade | **~3** | dúvida (termos não lidos) | médio |
| **Redi** e outras no HiringRoom (ATS latino) | HiringRoom | `redi.hiringroom.com/jobs` | HTML | não | localidade "Asunción" | não verificado (1 vaga vista via busca) | dúvida | médio |
| **Millicom / Tigo** | não identificado | vagas aparecem em agregadores (Built In, Clera, career.com) | — | — | — | não verificado | — | — |
| **BairesDev**, **Oktana** | próprio / não identificado | Oktana não está no Lever nem no Greenhouse (slug testado = 404); BairesDev publica no Computrabajo | — | — | — | não verificado | — | — |
| **WWF Paraguay** | próprio | não aparece no UNjobnet | — | — | — | não verificado | — | — |

**ATS em que não encontrei vagas no Paraguai:**
- Greenhouse: buscas `site:` não trouxeram Paraguai; a Infobip não usa Greenhouse.
- SmartRecruiters: Infobip com 0.
- Ashby, Workable, Teamtailor, Recruitee, Breezy, BambooHR, Eightfold, Phenom, Oracle Recruiting, Gupy, InHire, Quickin.

As buscas na web com `site:` funcionam mal para esses domínios. Na Fase 2, o melhor jeito de descobrir mais empresas é ter uma lista de multinacionais com operação no Paraguai e testar o slug de cada uma nas APIs públicas (Lever, Greenhouse, Ashby, SmartRecruiters, Workable, Recruitee). Cada teste custa 1 pedido.

## B) Portais oficiais e câmaras setoriais

| Fonte | URL | Acesso | Login? | Vagas PY hoje | Permitido | Esforço |
|---|---|---|---|---|---|---|
| **EmpleaPy / Bolsa MTESS** | `bolsa.mtess.gov.py` (lista em `vacancia_list.php`) | HTML **atrás de login com cédula** | **sim** | ~986 em 1º/08/2026, [segundo a Última Hora](https://www.ultimahora.com/hay-986-vacancias-en-el-portal-empleapy) | **não** sem convênio (coletar com login de cidadão não é aceitável) | alto (pedir convênio ou dados abertos ao MTESS) |
| **Capaser** (câmara de BPO) | `capaser.org.py/bolsa-de-empleos/` | **imagens (flyers)** | não | **18** flyers | sim, com limites rígidos do robots: 1 pedido a cada 60 s, máx. 6 por hora, só entre 00h e 09h (Buenos Aires) | médio-alto (OCR grátis com Tesseract; LLM seria pago) |

## C) Portais de emprego locais

| Fonte | URL | Acesso | Login? | Vagas PY hoje | Permitido | Esforço |
|---|---|---|---|---|---|---|
| **ABC Empleos** (Grupo Azeta) | `empleos.abc.com.py` | `sitemap-jobs.xml` (63 URLs, atualizado hoje) + app JS com API interna `/api` | não | **63** | **dúvida**: robots libera tudo, mas os termos estão num PDF que não consegui ler aqui; recomendo pedir autorização | médio |
| **TopTrabajos** | `toptrabajos.com/py/empleos` | HTML (robots bloqueia `/api/` e `/ofertas-de-trabajo/`) | não | ~33 | **não**: os termos proíbem "reproducir, duplicar, copiar… cualquier parte del Servicio" sem permissão escrita e o "rastreo automatizado no autorizado" | — (só com parceria) |
| **Computrabajo Paraguay** | `py.computrabajo.com` | bloqueia acesso automático: **403 até no robots.txt** | — | muitas (inclui BairesDev, call centers) | **não** | — |
| **GetOnBrd** (tech LATAM) | `getonbrd.com/api/v0` | API pública oficial | não | **0** para "paraguay"/"asuncion" | sim (robots: `search=yes`) | baixo, mas pouco volume |
| **Clasipar** (classificados) | `clasipar.paraguay.com` | HTML (robots libera; bloqueia Bing) | não | não verificado | dúvida | médio |
| Mipleo, CazVid, iAgora, Jobgether | — | agregadores que republicam vagas de terceiros | — | — | fora do escopo: não são a fonte original | — |
| LinkedIn, Indeed | — | — | — | — | **fora**, por decisão do projeto | — |

---

## Ranking: as 10 melhores fontes por vagas PY ÷ esforço

Pesos: baixo = 1, médio = 2, alto = 3. Só entram fontes que não estão bloqueadas.

| # | Fonte | Vagas PY | Esforço | Índice | Observação |
|---|---|---|---|---|---|
| 1 | ABC Empleos* | 63 | médio | 31,5 | *só depois de confirmar os termos ou ter autorização do Grupo Azeta |
| 2 | South (Recruiterflow) | 13 | baixo | 13,0 | quase todas remotas |
| 3 | Nestlé (SuccessFactors, HTML) | 22 | médio | 11,0 | maior empregador entre os ATS achados |
| 4 | Bluelight (Lever) | 8 | baixo | 8,0 | remotas, repetidas por cidade |
| 5 | Capaser (flyers + OCR) | 18 | médio-alto | ~7,2 | ritmo máximo de 6 pedidos/hora |
| 6 | Infobip (Workday) | 11 | médio | 5,5 | o adaptador Workday serve para outras empresas |
| 7 | Sistema ONU (UNjobnet) | ~3 | médio | 1,5 | |
| 8 | Coderio (Lever) | 1 | baixo | 1,0 | o adaptador Lever já existe |
| 9 | GetOnBrd | 0 | baixo | 0 | API oficial; vale manter para vagas remotas |
| 10 | Citi (Radancy) | 0 | médio | 0 | tinha vagas em outros momentos |

**Fora do ranking, mas com o maior potencial:**
- **EmpleaPy/MTESS**, com ~1.000 vagas: depende de um pedido formal ao MTESS por convênio ou dados abertos.
- **TopTrabajos**: depende de parceria.

## Conclusões e recomendação para a Fase 2

1. **Somando tudo o que é permitido hoje, são cerca de 140 vagas no Paraguai, ou ~80 sem o ABC.** Os ATS de multinacionais trazem pouco volume, e quase metade das vagas deles é remota LATAM. O grosso das vagas locais está em portais (ABC, EmpleaPy, Computrabajo) e em flyers (Capaser, stories).
2. **Primeiros coletores sugeridos**, todos com interface `fetch_jobs(source)`:
   - **Lever genérico:** Bluelight, Coderio e as próximas empresas descobertas.
   - **Recruiterflow:** South.
   - **Workday genérico:** Infobip, e depois testar outros tenants.
   - **SuccessFactors HTML:** Nestlé.
   - **UNjobnet.**
3. **Pedidos de autorização, a enviar por e-mail; posso redigir:**
   - Grupo Azeta, para o ABC Empleos;
   - MTESS, para o EmpleaPy (convênio ou dados abertos);
   - TopTrabajos, para uma parceria;
   - Capaser, para pedir os flyers em texto, o que evitaria o OCR.
4. **Descobrir mais empresas.** Montar uma lista de ~100 empregadores com operação no Paraguai e testar o slug de cada um nas APIs públicas dos ATS:
   - bancos: Itaú, ueno, Continental, Sudameris, BASA;
   - telecom: Tigo, Personal, Claro;
   - agro: Cargill, ADM, Bunge, Bayer, LDC;
   - consumo: AB InBev/Cervepar, Coca-Cola Paresa, Unilever;
   - BPO: Konecta, Teleperformance;
   - tecnologia: BairesDev, Oktana, Roshka.

   Isso custa 1 pedido por empresa e por ATS.

**Aguardo a sua aprovação**, inclusive sobre quais pedidos de autorização enviar, antes de começar a Fase 2.

---
Fontes das notícias citadas: [Última Hora: 986 vagas no EmpleaPy](https://www.ultimahora.com/hay-986-vacancias-en-el-portal-empleapy) ·
[Última Hora: vagas da Capaser](https://www.ultimahora.com/ofrecen-mas-de-200-vacantes-en-tercerizacion-de-servicios) ·
[ABC: lançamento do ABC Empleos](https://www.abc.com.py/abc-color/2026/04/13/abc-empleos-una-plataforma-integral-para-buscar-trabajo-en-paraguay/) ·
[UNjobnet: Asunción](https://www.unjobnet.org/countries/Paraguay/Asuncion)

---

## D) Consultorias de recrutamento paraguaias (adendo de 17/11/2026)

| Fonte | URL | Acesso | Vagas PY hoje | Permitido | Esforço |
|---|---|---|---|---|---|
| **Jobs Paraguay** (rede Jobs) | `jobs.com.py/es/empleos` (categorias: administração, comercial, construção, industrial, logística, marketing, RH, varejo…) | as vagas são carregadas por um widget (provavelmente Zoho Recruit); o HTML não traz a lista | contagens por categoria na página (37, 15, 8…), não verificadas | sim (robots: `Allow: /`); termos em PDF de 2016 não lidos | médio |
| **Capital Humano** | `capitalhumano.postulate.com.py/UI/Externo/VacanciasList.aspx` | lista carregada por JavaScript (ASP.NET) | não verificado; **4 vagas dela aparecem no ABC Empleos** | sem robots.txt (404); termos não lidos | médio |
| **ManpowerGroup Paraguay** | `manpower.com.py` (portal "Evolution") | o site **recusou** o pedido do robots.txt (403) | — | **não** (tratado como bloqueio) | — |
| **Talent Hub PY** | via ABC Empleos | — | **12 vagas no ABC Empleos** | via ABC | — |
| Adecco, Randstad | `adecco.com.py`, `randstad.com.py` | os domínios não respondem | — | — | — |

**Atualização do ABC Empleos:** a lista vem da API do próprio site (`empleos.abc.com.py/api/ofertas/`), num único pedido.
Hoje são **63 vagas abertas**, com empresa, área, cidades, modalidade e datas de publicação e vencimento.
O ABC também concentra vagas de consultorias (Talent Hub PY: 12; Capital Humano: 4; Azeta Mandatos: 10).
A pedido do usuário, as vagas entram na lista de revisão. A questão dos termos de uso continua em aberto antes de publicar.
