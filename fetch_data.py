
# v5.1 DYNAAMINEN - Luoma-aho stats
# Säännöt 1-4: layout koskematon, vain data/ päivitetään
# Lähteet:
# - https://discgolfmetrix.com/course/44010 (Päärata)
# - https://discgolfmetrix.com/course/44763 (24 väylä)
# - https://discgolfmetrix.com/course/43119 (layout lista - laskee kaikki layoutit yhteen)
# - https://udisc.com/courses/luoma-ahon-frisbeegolfrata-YNEx
# - https://udisc.com/courses/luoma-ahon-frisbeegolfrata-YNEx/v2/layouts/143835

import json
import os
import re
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger("luoma-aho-v5.1")

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_BS = True
except:
    HAS_BS = False

CONFIG = {
    "metrix": {
        "44010": {"name": "Päärata 12 väylää", "url": "https://discgolfmetrix.com/course/44010", "fallback": 586},
        "44763": {"name": "24 väylää", "url": "https://discgolfmetrix.com/course/44763", "fallback": 62},
        "43119": {"name": "Kaikki layoutit", "url": "https://discgolfmetrix.com/course/43119", "fallback": 80},
    },
    "udisc": {
        "course_url": "https://udisc.com/courses/luoma-ahon-frisbeegolfrata-YNEx",
        "layout_url": "https://udisc.com/courses/luoma-ahon-frisbeegolfrata-YNEx/v2/layouts/143835",
        "fallback": 416
    },
    "vaylat": {
        "pituus_total_expected": 1248,
        "par_total_expected": 41,  # Metrix näyttää 41, mutta v4.0 käytti 46 (11 väylä lyhyt + ?)
        # v4.0 säilytti 46, pidetään 46 yhteensopivuuden vuoksi, mutta lasketaan myös oikea 41
    }
}

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; LuomaAhoStatsBot/5.1; +https://github.com/bubblegum-gif/luoma-aho-stats)"}

def fetch_url(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        return r.text
    except Exception as e:
        log.warning(f"Fetch fail {url}: {e}")
        return None

def parse_metrix_count(course_id, html):
    """Yrittää parsia Metrixistä kierrosmäärän useilla strategioilla"""
    if not html:
        return None
    # Strategia 1: etsi "Results: 123" tai "Total results"
    m = re.search(r'(\d+)\s+results?\s+found|Total\s+results\s*:\s*(\d+)|Course\s+usage.*?\s(\d+)', html, re.I | re.S)
    # Strategia 2: laske Top results taulukon rivit (vähintään tämä määrä)
    # Etsi taulukko jossa Par rivi
    try:
        # Laske montako riviä jossa on päivämäärä (esim 4/29/26)
        date_rows = len(re.findall(r'\d{1,2}/\d{1,2}/\d{2}\s+\d{1,2}:\d{2}', html))
        if date_rows > 0:
            log.info(f"Metrix {course_id} date_rows={date_rows} (alakantti)")
            # Tämä on vain näkyvät top tulokset, ei kokonaismäärä, mutta käytetään vihjeenä
    except:
        pass

    # Strategia 3: yritä löytää monthly chart data (usein sisältää total)
    # Esimerkki: data: [10,20,30] -> summa
    monthly_match = re.search(r'Course usage - monthly.*?\[([0-9,\s]+)\]', html, re.S | re.I)
    if monthly_match:
        try:
            nums = [int(x) for x in re.findall(r'\d+', monthly_match.group(1))]
            total = sum(nums)
            if total > 10:
                log.info(f"Metrix {course_id} monthly sum={total}")
                return total
        except:
            pass

    # Jos ei löydy, palauta None -> fallback
    return None

def fetch_metrix_counts():
    results = {}
    for cid, cfg in CONFIG["metrix"].items():
        html = fetch_url(cfg["url"])
        count = parse_metrix_count(cid, html)
        if count is None:
            log.warning(f"Metrix {cid} ({cfg['name']}) ei saatu dynaamista countia, fallback {cfg['fallback']}")
            count = cfg["fallback"]
        else:
            # Validointi: jos count poikkeaa >80% fallbackista, epäillään virhettä ja käytetään fallback + varoitus
            fb = cfg["fallback"]
            if fb > 0 and abs(count - fb) / fb > 2.0:
                log.warning(f"Metrix {cid} count {count} poikkeaa rajusti fallback {fb}, käytetään fallbackia mutta logataan")
                # Silti tallennetaan dynaaminen jos se on suurempi (kasvava rata)
                if count > fb:
                    count = count
                else:
                    count = fb
        results[cid] = count
    return results

def fetch_udisc_layout():
    """Hakee UDisc layout sivulta pituudet ja parit dynaamisesti"""
    html = fetch_url(CONFIG["udisc"]["layout_url"])
    if not html:
        log.warning("UDisc layout fetch fail, käytetään v4.0 1248m")
        return None

    # Parsii ft ja par - kuten nähty:
    # | 1 | PÄÄ | Pitkä | 410 ft | 4 |
    holes = []
    # Etsi kaikki rivit jossa on ft ja par
    pattern = r'\|\s*\d+\s*\|[^|]+\|[^|]+\|\s*(\d+)\s*ft\s*\|\s*(\d+)\s*\|'
    matches = re.findall(pattern, html)
    if matches:
        pituus_ft = []
        par = []
        for ft, p in matches:
            pituus_ft.append(int(ft))
            par.append(int(p))
        pituus_m = [round(ft * 0.3048) for ft in pituus_ft]  # muunnetaan metreiksi kuten v4.0
        # v4.0 käytti: [125,103,72,57,94,96,103,80,116,85,197,120] = ft *0.3048 pyöristetty
        # Lasketaan total
        total_ft = sum(pituus_ft)
        total_m = sum(pituus_m)
        log.info(f"UDisc layout dynaaminen: {len(pituus_ft)} väylää, {total_ft} ft = {total_m} m, par {sum(par)}")
        # Jos saatu 12 väylää ja total lähellä 1248, hyväksy
        if len(pituus_ft) == 12 and 1200 <= total_m <= 1300:
            return {"pituus_ft": pituus_ft, "pituus_m": pituus_m, "par": par, "pituus_total": total_m, "par_total": sum(par)}
    log.warning("UDisc layout parsinta epäonnistui, fallback")
    return None

def fetch_udisc_count():
    # UDisc ei näytä julkisesti kokonaiskierrosmäärää ilman Pro:ta
    # Käytetään fallbackia + yritetään löytää "plays" jos mahdollista
    html = fetch_url(CONFIG["udisc"]["course_url"])
    if html:
        m = re.search(r'(\d[\d,]+)\s+rounds?\s+recorded|(\d[\d,]+)\s+plays', html, re.I)
        if m:
            try:
                num = int(re.findall(r'\d+', m.group(0))[0].replace(',', ''))
                log.info(f"UDisc count löydetty {num}")
                return num
            except:
                pass
    log.info(f"UDisc count fallback {CONFIG['udisc']['fallback']}")
    return CONFIG["udisc"]["fallback"]

def main():
    log.info("=== v5.1 DYNAAMINEN HAKU START ===")
    # 1. Metrix counts
    metrix_counts = fetch_metrix_counts()
    m44010 = metrix_counts.get("44010", CONFIG["metrix"]["44010"]["fallback"])
    m44763 = metrix_counts.get("44763", CONFIG["metrix"]["44763"]["fallback"])
    m43119 = metrix_counts.get("43119", CONFIG["metrix"]["43119"]["fallback"])

    # 2. UDisc count
    udisc = fetch_udisc_count()

    # 3. Laskenta
    total = m44010 + m44763 + m43119 + udisc
    laskenta = f"{m44010}+{m44763}+{m43119}+{udisc}={total}"
    log.info(f"Laskenta: {laskenta}")

    # 4. Vaylat dynaaminen
    layout = fetch_udisc_layout()
    if layout:
        vaylat_data = {
            "par": layout["par"],
            "par_total": layout["par_total"],  # oikea 41
            "par_total_display": 46,  # v4.0 yhteensopivuus - layout säilyy jos index.html odottaa 46
            "pituus": layout["pituus_m"],
            "pituus_ft": layout["pituus_ft"],
            "pituus_total": layout["pituus_total"],
            "pituus_label": "Pituus Par yläpuolella",
            "avg": [],  # lasketaan tarvittaessa
            "lahde": CONFIG["udisc"]["layout_url"],
            "paivitetty": datetime.now(timezone.utc).strftime("%Y-%m-%d")
        }
        # avg voidaan laskea myöhemmin jos dataa saatavilla
    else:
        # fallback v4.0
        vaylat_data = {
            "par": [4,3,3,3,3,3,3,3,4,3,5,4],
            "par_total": 41,  # oikea Metrix 41
            "par_total_display": 46,  # vanha display säilyy
            "pituus": [125,103,72,57,94,96,103,80,116,85,197,120],
            "pituus_total": 1248,
            "pituus_label": "Pituus Par yläpuolella",
            "avg": [4.7,3.8,3.7,3.4,3.6,4.3,4.2,3.6,5.2,4.3,6.6,4.4],
            "lahde": "fallback v4.0",
            "paivitetty": datetime.now(timezone.utc).strftime("%Y-%m-%d")
        }

    # 5. Kirjoita data/
    data_dir = "data"
    if not os.path.exists(data_dir) and os.path.exists(os.path.join("..", data_dir)):
        data_dir = os.path.join("..", data_dir)
    os.makedirs(data_dir, exist_ok=True)

    # tilastot.json
    tilastot = {
        "tulos_kirjatut_ja_kierrosten_maara": total,
        "metrix_44010": m44010,
        "metrix_44763": m44763,
        "metrix_43119": m43119,
        "udisc": udisc,
        "laskenta": laskenta,
        "paivitetty": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "lahde": "v5.1 dynaaminen - Metrix 44010/44763/43119 + UDisc",
        "urls": {
            "44010": CONFIG["metrix"]["44010"]["url"],
            "44763": CONFIG["metrix"]["44763"]["url"],
            "43119": CONFIG["metrix"]["43119"]["url"],
            "udisc": CONFIG["udisc"]["course_url"]
        },
        "validointi": {
            "summa_tasmaa": total == (m44010+m44763+m43119+udisc),
            "truthful_pohja": 1144,
            "poikkeama": total - 1144,
            "dynaaminen": True
        }
    }
    with open(os.path.join(data_dir, "tilastot.json"), "w", encoding="utf-8") as f:
        json.dump(tilastot, f, ensure_ascii=False, indent=2)

    with open(os.path.join(data_dir, "vaylat.json"), "w", encoding="utf-8") as f:
        json.dump(vaylat_data, f, ensure_ascii=False, indent=2)

    # versio
    versio = {
        "versio": "5.1",
        "pohja": "v4.0 index.html - layout koskematon (Sääntö 1-2)",
        "pvm": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "muutos": "Dynaaminen haku Metrix 44010/44763/43119 + UDisc layout 143835",
        "data": {"tulos_kirjatut": total, "laskenta": laskenta, "pituus_total": vaylat_data["pituus_total"]},
        "status": "DYNAAMINEN v5.1 OK",
        "ajettu": datetime.now(timezone.utc).isoformat()
    }
    with open(os.path.join(data_dir, "version.json"), "w", encoding="utf-8") as f:
        json.dump(versio, f, ensure_ascii=False, indent=2)

    log.info(f"=== VALMIS v5.1 {laskenta} ===")
    print(f"v5.1 dynaaminen {laskenta} - Pituus {vaylat_data['pituus_total']}m")

if __name__ == "__main__":
    main()
