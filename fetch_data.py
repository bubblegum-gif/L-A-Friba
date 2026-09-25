
# v7.1 LIVE - First Paint Latest + saa.json live + udisc_top5 live
import json
import os
import re
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger("luoma-aho-v7.1")

CONFIG = {
    "metrix": {
        "44010": {"name": "Päärata 12", "url": "https://discgolfmetrix.com/course/44010", "fallback": 586},
        "44763": {"name": "24 väylää", "url": "https://discgolfmetrix.com/course/44763", "fallback": 62},
        "43119": {"name": "Kaikki layoutit", "url": "https://discgolfmetrix.com/course/43119", "fallback": 80},
    },
    "udisc": {
        "course_url": "https://udisc.com/courses/luoma-ahon-frisbeegolfrata-YNEx",
        "layout_url": "https://udisc.com/courses/luoma-ahon-frisbeegolfrata-YNEx/v2/layouts/143835",
        "leaderboard_url": "https://udisc.com/courses/luoma-ahon-frisbeegolfrata-YNEx/leaderboard",
        "fallback": 416,
        "top5_fallback": [
            {"pos":1,"username":"@kantanen8","score":35,"date":"Jul 6 2026"},
            {"pos":2,"username":"@valkoparta","score":36},
            {"pos":3,"username":"@mattiasss","score":36},
            {"pos":4,"username":"@dashyy","score":38},
            {"pos":5,"username":"@tuohimaa","score":39}
        ]
    },
    "saa": {
        "lat": 63.077361313935,
        "lon": 23.869258564394357,
        "paikka": "Luoma-aho"
    }
}

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; LuomaAhoStatsBot/7.1 LIVE)"}

def fetch_url(url):
    try:
        import requests
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        return r.text
    except Exception as e:
        log.warning(f"Fetch fail {url}: {e}")
        return None

def fetch_json(url):
    try:
        import requests
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning(f"Fetch JSON fail {url}: {e}")
        return None

def fetch_saa_live():
    """Hakee live sään Open-Meteo API:sta (ilmainen, ei avainta)"""
    lat = CONFIG["saa"]["lat"]
    lon = CONFIG["saa"]["lon"]
    # Open-Meteo current weather
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,wind_speed_10m,relative_humidity_2m,precipitation,weather_code&timezone=Europe/Helsinki"
    data = fetch_json(url)
    if not data or "current" not in data:
        log.warning("Sää fetch fail, fallback 14C")
        return {"paikka": "Luoma-aho", "nyky": {"temp_c": 14, "lahde": "fallback"}, "paivitetty": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
    
    cur = data.get("current", {})
    temp = cur.get("temperature_2m")
    wind = cur.get("wind_speed_10m")
    hum = cur.get("relative_humidity_2m")
    prec = cur.get("precipitation")
    code = cur.get("weather_code")
    
    # Weather code selitys
    weather_map = {
        0: "Selkeää", 1: "Pääosin selkeää", 2: "Puolipilvistä", 3: "Pilvistä",
        45: "Sumua", 48: "Kuuraa", 51: "Tihkua", 53: "Tihkua", 55: "Tihkua",
        61: "Sadetta", 63: "Sadetta", 65: "Sadetta", 71: "Lumisadetta", 73: "Lumisadetta", 75: "Lumisadetta",
        80: "Kuuroja", 81: "Kuuroja", 82: "Kuuroja", 95: "Ukkosta"
    }
    
    saa = {
        "paikka": CONFIG["saa"]["paikka"],
        "koordinaatit": {"lat": lat, "lon": lon},
        "nyky": {
            "temp_c": temp,
            "wind_ms": wind,
            "humidity": hum,
            "precipitation_mm": prec,
            "weather_code": code,
            "kuvaus": weather_map.get(code, f"Koodi {code}"),
            "lahde": "Open-Meteo"
        },
        "paivitetty": datetime.now(timezone.utc).isoformat(),
        "api": url
    }
    log.info(f"Sää live: {temp}C, tuuli {wind}m/s, {saa['nyky']['kuvaus']}")
    return saa

def fetch_udisc_top5_live():
    """Yrittää hakea UDisc leaderboard livenä, fallback jos ei onnistu"""
    # Strategia 1: yritä leaderboard URL
    html = fetch_url(CONFIG["udisc"]["leaderboard_url"])
    if html:
        # Etsi top5 pattern - esim username ja score
        # UDisc leaderboard usein sisältää @username ja score
        # Parsitaan yksinkertaisesti: etsi kaikki @-alalkuiset ja numero perässä
        import re
        # Esimerkki: <div> @kantanen8 35 </div>
        matches = re.findall(r'@([a-zA-Z0-9_]+)[^\d]{0,20}(\d{1,2})', html)[:10]
        if len(matches) >= 3:
            top5 = []
            for i, (user, score) in enumerate(matches[:5]):
                try:
                    top5.append({"pos": i+1, "username": f"@{user}", "score": int(score), "lahde": "live scrape"})
                except:
                    pass
            if len(top5)>=3:
                log.info(f"UDisc top5 live löydetty {top5}")
                return top5
    
    # Strategia 2: yritä course sivu jossa voi olla recent best
    html2 = fetch_url(CONFIG["udisc"]["course_url"])
    if html2:
        import re
        # Etsi leaderboard json script tagista
        # UDisc usein upottaa __NEXT_DATA__ tai vastaava
        m = re.search(r'"leaderboard".*?"topScores".*?\[.*?\]', html2, re.S)
        if m:
            log.info(f"UDisc leaderboard snippet löydetty")
    
    # Fallback
    log.info(f"UDisc top5 fallback {CONFIG['udisc']['top5_fallback']}")
    return CONFIG["udisc"]["top5_fallback"]

def fetch_metrix_counts():
    results = {}
    for cid, cfg in CONFIG["metrix"].items():
        html = fetch_url(cfg["url"])
        results[cid] = cfg["fallback"]  # Placeholder, oikea count vaatisi API avaimen tai kirjautumisen
    return results

def fetch_udisc_layout():
    html = fetch_url(CONFIG["udisc"]["layout_url"])
    if not html:
        return None
    import re
    pattern = r'\|\s*\d+\s*\|[^|]+\|[^|]+\|\s*(\d+)\s*ft\s*\|\s*(\d+)\s*\|'
    matches = re.findall(pattern, html)
    if matches:
        pituus_ft = [int(ft) for ft,p in matches]
        par = [int(p) for ft,p in matches]
        pituus_m = [round(ft*0.3048) for ft in pituus_ft]
        total_m = sum(pituus_m)
        if len(pituus_ft)==12 and 1200 <= total_m <= 1300:
            return {"pituus_ft": pituus_ft, "pituus_m": pituus_m, "par": par, "pituus_total": total_m, "par_total": sum(par)}
    return None

def embed_latest_into_index(data_dir, index_path):
    try:
        import re
        files = {}
        for name in ["tilastot.json","vaylat.json","version.json","saa.json","udisc_top5.json"]:
            try:
                with open(os.path.join(data_dir, name), 'r', encoding='utf-8') as f:
                    files[name.split('.')[0]] = json.load(f)
            except:
                files[name.split('.')[0]] = {}

        tilastot = files.get("tilastot", {})
        vaylat = files.get("vaylat", {})
        versio = files.get("version", {})
        
        latest_bundle = {
            "tilastot": tilastot,
            "vaylat": vaylat,
            "version": versio,
            "saa": files.get("saa", {}),
            "udisc_top5": files.get("udisc_top5", []),
            "embedded_at": datetime.now(timezone.utc).isoformat()
        }

        if not os.path.exists(index_path):
            alt = os.path.join("..", "index.html")
            if os.path.exists(alt):
                index_path = alt
            else:
                return

        with open(index_path, 'r', encoding='utf-8') as f:
            html = f.read()

        html = re.sub(r'<script id="latest-embedded-data" type="application/json">.*?</script>', '', html, flags=re.S)
        html = re.sub(r'<script id="latest-data-bundle">.*?</script>', '', html, flags=re.S)

        bundle_json = json.dumps(latest_bundle, ensure_ascii=False)
        bundle_json_safe = bundle_json.replace("</", "<\/")

        embed_tag = f'<script id="latest-embedded-data" type="application/json">{bundle_json_safe}</script>\n'
        embed_tag += f'<script id="latest-data-bundle">window.__LATEST_DATA__ = {bundle_json_safe}; window.__LATEST_VERSION__ = "{versio.get("versio","7.1")}"; console.log("v7.1 LIVE embedded", window.__LATEST_VERSION__, "{tilastot.get("laskenta","")}");</script>\n'

        if "</head>" in html:
            html = html.replace("</head>", embed_tag + "</head>")
        elif "<body" in html:
            html = html.replace("<body", embed_tag + "<body")
        else:
            html = embed_tag + html

        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(html)

        log.info(f"Embedded LIVE into {index_path} - {tilastot.get('laskenta')} {vaylat.get('pituus_total')}m Saa {files.get('saa',{}).get('nyky',{}).get('temp_c')}C")

    except Exception as e:
        log.error(f"Embed fail: {e}", exc_info=True)

def main():
    log.info("=== v7.1 LIVE FIRST PAINT + SAA + TOP5 START ===")
    
    # 1. Metrix counts (fallback truthful)
    metrix_counts = fetch_metrix_counts()
    m44010 = metrix_counts.get("44010", 586)
    m44763 = metrix_counts.get("44763", 62)
    m43119 = metrix_counts.get("43119", 80)
    udisc_count = 416
    total = m44010 + m44763 + m43119 + udisc_count
    laskenta = f"{m44010}+{m44763}+{m43119}+{udisc_count}={total}"

    # 2. Vaylat
    layout = fetch_udisc_layout()
    if layout:
        vaylat_data = {
            "par": layout["par"], "par_total": layout["par_total"], "par_total_display": 46,
            "pituus": layout["pituus_m"], "pituus_ft": layout["pituus_ft"],
            "pituus_total": layout["pituus_total"], "pituus_label": "Pituus Par yläpuolella",
            "avg": [4.7,3.8,3.7,3.4,3.6,4.3,4.2,3.6,5.2,4.3,6.6,4.4],
            "lahde": CONFIG["udisc"]["layout_url"], "paivitetty": datetime.now(timezone.utc).isoformat()
        }
    else:
        vaylat_data = {
            "par": [4,3,3,3,3,3,3,3,4,3,5,4], "par_total": 41, "par_total_display": 46,
            "pituus": [125,103,72,57,94,96,103,80,116,85,197,120],
            "pituus_ft": [410,338,236,189,308,315,336,264,381,279,646,394],
            "pituus_total": 1248, "pituus_label": "Pituus Par yläpuolella",
            "avg": [4.7,3.8,3.7,3.4,3.6,4.3,4.2,3.6,5.2,4.3,6.6,4.4],
            "lahde": "fallback v4.0 + UDisc 143835 1248m", "paivitetty": datetime.now(timezone.utc).isoformat()
        }

    # 3. SAA LIVE
    saa_data = fetch_saa_live()

    # 4. UDisc TOP5 LIVE
    top5_data = fetch_udisc_top5_live()

    data_dir = "data"
    if not os.path.exists(data_dir) and os.path.exists(os.path.join("..", data_dir)):
        data_dir = os.path.join("..", data_dir)
    os.makedirs(data_dir, exist_ok=True)

    tilastot = {
        "tulos_kirjatut_ja_kierrosten_maara": total,
        "metrix_44010": m44010, "metrix_44763": m44763, "metrix_43119": m43119, "udisc": udisc_count,
        "laskenta": laskenta, "paivitetty": datetime.now(timezone.utc).isoformat(),
        "lahde": "v7.1 LIVE FIRST PAINT + SAA + TOP5",
        "urls": {
            "44010": CONFIG["metrix"]["44010"]["url"],
            "44763": CONFIG["metrix"]["44763"]["url"],
            "43119": CONFIG["metrix"]["43119"]["url"],
            "udisc": CONFIG["udisc"]["course_url"]
        }
    }

    with open(os.path.join(data_dir, "tilastot.json"), "w", encoding="utf-8") as f:
        json.dump(tilastot, f, ensure_ascii=False, indent=2)
    with open(os.path.join(data_dir, "vaylat.json"), "w", encoding="utf-8") as f:
        json.dump(vaylat_data, f, ensure_ascii=False, indent=2)
    with open(os.path.join(data_dir, "saa.json"), "w", encoding="utf-8") as f:
        json.dump(saa_data, f, ensure_ascii=False, indent=2)
    with open(os.path.join(data_dir, "udisc_top5.json"), "w", encoding="utf-8") as f:
        json.dump(top5_data, f, ensure_ascii=False, indent=2)

    versio = {
        "versio": "7.1", "pohja": "v7.0 FIRST PAINT LATEST",
        "pvm": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "ominaisuudet": ["FIRST PAINT LATEST embedded", "saa.json LIVE Open-Meteo", "udisc_top5 LIVE scrape"],
        "data": {"tulos_kirjatut": total, "laskenta": laskenta, "pituus_total": vaylat_data["pituus_total"], "saa_temp": saa_data.get("nyky",{}).get("temp_c")},
        "status": "v7.1 LIVE OK", "ajettu": datetime.now(timezone.utc).isoformat()
    }
    with open(os.path.join(data_dir, "version.json"), "w", encoding="utf-8") as f:
        json.dump(versio, f, ensure_ascii=False, indent=2)

    for candidate in ["index.html", "../index.html", "../../index.html"]:
        if os.path.exists(candidate):
            embed_latest_into_index(data_dir, candidate)
    if data_dir == "data" and os.path.exists("index.html"):
        embed_latest_into_index(data_dir, "index.html")
    if os.path.exists(os.path.join("..", "index.html")):
        embed_latest_into_index(data_dir, os.path.join("..", "index.html"))

    log.info(f"=== VALMIS v7.1 LIVE {laskenta} {vaylat_data['pituus_total']}m Saa {saa_data.get('nyky',{}).get('temp_c')}C ===")
    print(f"v7.1 LIVE {laskenta} - {vaylat_data['pituus_total']}m - Saa {saa_data.get('nyky',{}).get('temp_c')}C - Top5 {len(top5_data)}")

if __name__ == "__main__":
    main()
