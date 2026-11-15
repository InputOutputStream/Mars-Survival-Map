#!/usr/bin/env python3
"""Construit le site Jezero RÉEL pour l'interface web, à partir des données téléchargées :

  1. data/jezero/dem.npy + dem.json   (fetch_dtm_window.py : MNT HiRISE DTEEC_023524_1985_023379_1985, mètres, nord en haut)
  2. data/meda_jezero.json            (analyse_meda.py : températures/pressions MEDA réelles par sol)

Sorties dans web/data/site/ : dem/slope/rough/cost/tmult .bin, PNG, routes (énergie), sites plats, plan EVA, provenance.json.

Ce que les données réelles apportent au plan EVA : température moyenne et amplitude diurne MESURÉES par MEDA (au lieu des valeurs par
défaut du modèle). Le modèle reste une sinusoïde (hypothèse) ; seuls ses paramètres viennent des mesures. Seuls les sols couvrant
>= 12 heures locales distinctes sont retenus (un sol de 30 min, comme le sol 1, donnerait une amplitude fausse).

Sous-échantillonnage : le MNT fait ~1 m/pixel. Pour que Dijkstra reste utilisable dans le navigateur, on moyenne par blocs jusqu'à
max-dim pixels. ATTENTION : pente et rugosité dépendent de l'échelle ; elles sont calculées à la résolution finale (documentée
dans provenance.json), ce qui lisse les petites rugosités (déjà invisibles à 1 m).
Usage : python scripts/build_jezero.py [--max-dim 1000] [--out web/data/site]
"""
import argparse, json, math, sys
from datetime import date
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mars_survival import site as sitemod, cli  # noqa: E402


def block_mean(a: np.ndarray, f: int) -> np.ndarray:
    if f == 1:
        return a
    h, w = (a.shape[0] // f) * f, (a.shape[1] // f) * f
    b = a[:h, :w].reshape(h // f, f, w // f, f)
    with np.errstate(invalid="ignore"):
        cnt = np.sum(~np.isnan(b), axis=(1, 3))
        s = np.nansum(b, axis=(1, 3))
    return np.where(cnt > 0, s / np.maximum(cnt, 1), np.nan).astype(np.float32)


def meda_temperature_params(meda: dict, min_hours: int = 12) -> dict:
    means, amps, used = [], [], []
    for sol, d in meda["sols"].items():
        t = d.get("air_temp_K")
        if not t:
            continue
        hm = t["hourly_mean"]
        if len(hm) < min_hours:
            continue
        v = list(hm.values())
        means.append(sum(v) / len(v)); amps.append(max(v) - min(v)); used.append(int(sol))
    if not used:
        raise SystemExit("aucun sol MEDA couvrant >= 12 heures locales : téléchargez d'autres sols (fetch_meda.py --every 30)")
    return {"mean_k": sum(means) / len(means), "diurnal_k": sum(amps) / len(amps), "sols_used": sorted(used)}


def build(dem_path, meta_path, meda_path, out: Path, max_dim: int = 1000, test_fixture: bool = False) -> dict:
    dem = np.load(dem_path).astype(np.float32)
    meta = json.load(open(meta_path))
    meda = json.load(open(meda_path))
    f = max(1, math.ceil(max(dem.shape) / max_dim))
    dem_ds = block_mean(dem, f)
    px = meta["px_m"] * f
    tp = meda_temperature_params(meda)
    st = sitemod.Site(dem_ds, px, name=("TEST FIXTURE (synthetic)" if test_fixture else "Jezero crater — HiRISE DTM"),
                      center_lat=meta["center_lat"], center_lon=meta["center_lon"], synthetic=test_fixture)
    cli.run_site(ROOT, st, None, tp["mean_k"], tp["diurnal_k"], out)
    prov = {
        "built": str(date.today()), "synthetic": test_fixture,
        "dem": {"source_url": meta["source_url"], "native_px_m": meta["px_m"], "window_shape_native": meta["shape"],
                "downsample_factor": f, "final_px_m": px,
                "product": "HiRISE DTEEC_023524_1985_023379_1985_U01 (PDS3 .IMG, float32 metres above Mars 2000 datum)"},
        "meda": {"source": meda.get("source"), "url": meda.get("url"), "units": meda.get("units"),
                 "aggregation": meda.get("aggregation"), **tp},
        "eva_model_note": "temperature = sinusoid (hypothesis) with mean/amplitude from MEDA; see eva.py",
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "provenance.json").write_text(json.dumps(prov, indent=1))
    return prov


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", default=str(ROOT / "data/jezero/dem.npy")); ap.add_argument("--meta", default=str(ROOT / "data/jezero/dem.json"))
    ap.add_argument("--meda", default=str(ROOT / "data/meda_jezero.json")); ap.add_argument("--out", default=str(ROOT / "web/data/site"))
    ap.add_argument("--max-dim", type=int, default=1000)
    a = ap.parse_args()
    p = build(a.dem, a.meta, a.meda, Path(a.out), a.max_dim)
    print(json.dumps(p["meda"], indent=1)); print("provenance ->", Path(a.out) / "provenance.json")
