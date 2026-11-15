#!/usr/bin/env python3
"""Generates docs/ANALYSIS_REPORT.md from web/sources.json (single source of truth, also displayed by web/sources.html)."""
import json
from pathlib import Path
R = Path(__file__).resolve().parents[1]
j = json.load(open(R / "web/sources.json"))
T = {"data": "Data sources", "physics": "Physics sources", "assumption": "Team assumptions", "software": "Software and fonts"}
out = ["# Mars Survival Map: sources and assumptions", "", f"Updated {j['updated']}. Generated from `web/sources.json`; edit that file, not this one.", ""]
for g, title in T.items():
    out += [f"## {title}", ""]
    for e in (x for x in j["entries"] if x["group"] == g):
        out.append(f"### {e['id']} {e['name']}")
        if e.get("publisher"): out.append(f"*{e['publisher']}*  ")
        if e.get("url"): out.append(f"- Link: {e['url']}")
        if e.get("file"): out.append(f"- Exact file: {e['file']}")
        if e.get("taken"): out.append(f"- {'Value' if g == 'assumption' else 'Data taken'}: {e['taken']}")
        if e.get("use"): out.append(f"- {'Why it is a guess' if g == 'assumption' else 'Used for'}: {e['use']}")
        out += [f"- Status: {e['status']}", ""]
(R / "docs/ANALYSIS_REPORT.md").write_text("\n".join(out))
print("docs/ANALYSIS_REPORT.md", len(j["entries"]), "entries")
