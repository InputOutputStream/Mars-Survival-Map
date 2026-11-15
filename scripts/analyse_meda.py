#!/usr/bin/env python3
"""Statistiques journalières réelles MEDA (Jezero) à partir des CSV calibrés téléchargés par fetch_meda.py.

Colonnes (observées le 2026-11-06 dans les fichiers du sol 100) :
  ATS : SCLK, LMST, LTST, ATS_LOCAL_TEMP1..5        -> température de l'air, 5 capteurs
  PS  : SCLK, LMST, LTST, BAROCAP{1,2,3}_PRESSURE (+_UNCERTAINTY, souvent vide), THERMOCAP*_TEMP, ...
Unités CONFIRMÉES dans les étiquettes PDS4 (.xml, sol 1) : ATS_LOCAL_TEMP* en kelvin ; BAROCAP*_PRESSURE en pascal ;
THERMOCAP*_TEMP en kelvin. Les données de pression sont la version 2.0 (retraitées pour la dérive des barocaps, 2021-10-29).
Agrégation : MÉDIANE des canaux disponibles à chaque instant (5 capteurs de température, 3 barocaps de pression), car les canaux
peuvent différer nettement (ex. sol 1 : capteur ATS 2 ~272 K contre ~253 K pour les autres ; sol 100 : BAROCAP1 770,7 Pa contre
761,4/761,6 Pa pour les barocaps 2 et 3) ; l'écart entre canaux n'est pas encore expliqué : à documenter avec le SIS MEDA ENV RDR.
Usage : python scripts/analyse_meda.py data/meda --out web/data/meda_jezero.json
"""
import argparse, csv, json, re
from pathlib import Path
from statistics import mean, median


def read(path, prefix):
    cols, rows = None, []
    with open(path, newline="") as f:
        rd = csv.DictReader(f)
        for r in rd:
            vals = []
            for k, v in r.items():
                if k.startswith(prefix) and not k.endswith("UNCERTAINTY") and v.strip():
                    try: vals.append(float(v))
                    except ValueError: pass
            if vals:
                rows.append((r["LMST"], median(vals)))
    return rows


def lmst_hour(s):
    m = re.search(r"M(\d\d):(\d\d):(\d\d)", s)
    return int(m[1]) + int(m[2]) / 60 + int(m[3]) / 3600


def sol_stats(rows):
    v = [x for _, x in rows]
    byh = {}
    for t, x in rows:
        byh.setdefault(int(lmst_hour(t)), []).append(x)
    return {"n": len(v), "min": min(v), "max": max(v), "mean": mean(v),
            "hourly_mean": {h: round(mean(x), 3) for h, x in sorted(byh.items())}}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("dir"); ap.add_argument("--out", default="meda_jezero.json")
    a = ap.parse_args(); res = {}
    for f in sorted(Path(a.dir).glob("sol_*_ATS.csv")):
        sol = int(f.name[4:8]); res.setdefault(sol, {})["air_temp_K"] = sol_stats(read(f, "ATS_LOCAL_TEMP"))
    for f in sorted(Path(a.dir).glob("sol_*_PS.csv")):
        sol = int(f.name[4:8]); res.setdefault(sol, {})["pressure_Pa"] = sol_stats(read(f, "BAROCAP"))
    json.dump({"source": "NASA PDS Atmospheres, Mars 2020 MEDA calibrated ENV (CAL_ATS, CAL_PS), Jezero crater",
               "url": "https://atmos.nmsu.edu/PDS/data/PDS4/Mars2020/mars2020_meda/data_calibrated_env/",
               "units": {"air_temp": "kelvin", "pressure": "pascal"}, "aggregation": "median over available channels per record", "sols": res}, open(a.out, "w"), indent=1)
    print(len(res), "sols ->", a.out)
