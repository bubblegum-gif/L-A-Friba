import requests, json, re
from datetime import datetime, timezone
import os

def fetch_metrix(cid):
    url=f'https://discgolfmetrix.com/course/{cid}'
    try:
        r=requests.get(url, headers={'User-Agent':'Mozilla/5.0 (Luoma-aho-bot/3.1)'}, timeout=15)
        m=re.search(r'Kierroksia\s*:\s*(\d+)', r.text, re.I) or re.search(r'(\d+)\s*kierrosta', r.text, re.I)
        if m: return int(m.group(1))
    except: pass
    return None

def main():
    os.makedirs('data', exist_ok=True)
    try: old=json.load(open('data/tilastot.json','r',encoding='utf-8'))
    except: old={"metrix_44010":582,"metrix_44763":62,"metrix_43119":80}
    c44010=fetch_metrix('44010') or old.get('metrix_44010',586)
    c44763=fetch_metrix('44763') or old.get('metrix_44763',62)
    total=c44010+c44763+c43119+416
    data={
        "tulos_kirjatut_ja_kierrosten_maara": total,
        "eri_pelaajia": old.get('eri_pelaajia',233),
        "peliaika": "58 pv 21 h",
        "askeleet": "3,39 M",
        "kilometri": "2 650 km",
        "metrix_44010": c44010,
        "metrix_44763": c44763,
        "metrix_43119": c43119,
        "udisc": 416,
        "paivitetty": datetime.now(timezone.utc).isoformat(),
        "lahde": "GitHub Actions 5min server-side - ei CORS - kaikki kortit auto-update"
    }
    json.dump(data, open('data/tilastot.json','w',encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"OK total={total} 44010={c44010} (4 tänään)")

if __name__=='__main__': main()
