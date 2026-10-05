"""Local, single-user web demo for the skills-only matcher (stdlib only, localhost only)."""

from __future__ import annotations

import argparse
import html
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from german_job_market.matching import rank_jobs
from german_job_market.skills import SkillTaxonomy, extract_skill_ids, load_taxonomy

NOTICE = (
    "Skill-overlap demo on a historical 2023 Stepstone snapshot. The score is taxonomy overlap, "
    "not suitability or hiring probability. 'Not found' skills are not verified requirements. "
    "Text you paste is processed in memory and never stored."
)


def render_page(taxonomy: SkillTaxonomy, result: dict[str, Any] | None, error: str | None) -> str:
    """Render the form and optional results as one HTML page."""
    boxes = "".join(
        f'<label><input type="checkbox" name="skill" value="{html.escape(s.id)}"> '
        f"{html.escape(s.label)}</label>"
        for s in taxonomy.skills
    )
    body = ""
    if error:
        body += f'<p class="err">{html.escape(error)}</p>'
    if result:
        cand = ", ".join(s["label"] for s in result["candidate"]["skills"])
        body += f"<h2>Top matches for: {html.escape(cand)}</h2><table><tr><th>Job</th>"
        body += "<th>Score</th><th>Matched</th><th>Ad skills not in your profile</th></tr>"
        for job in result["ranked_jobs"]:
            matched = ", ".join(m["label"] for m in job["matched_skills"])
            gaps = job.get("not_found_in_candidate_profile") or []
            gap_txt = ", ".join(g.get("label", "") for g in gaps)
            body += (
                f"<tr><td>{html.escape(str(job['title']))}<br><small>"
                f"{html.escape(str(job['company'] or ''))} · "
                f"{html.escape(str(job['location'] or ''))}</small></td>"
                f"<td>{job['match_score']:.2f}</td><td>{html.escape(matched)}</td>"
                f"<td>{html.escape(gap_txt)}</td></tr>"
            )
        body += "</table>"
    return f"""<!doctype html><meta charset="utf-8"><title>Job matcher demo</title>
<style>body{{font:15px system-ui;max-width:960px;margin:2rem auto;padding:0 1rem}}
label{{display:inline-block;width:210px}}table{{border-collapse:collapse;width:100%}}
td,th{{border-bottom:1px solid #ccc;padding:6px;text-align:left;vertical-align:top}}
.err{{color:#b00}}.note{{color:#555}}</style>
<h1>German job market matcher</h1><p class="note">{html.escape(NOTICE)}</p>
<form method="post"><p><b>Tick your skills</b></p>{boxes}
<p><b>or paste CV / skills text</b><br>
<textarea name="text" rows="5" style="width:100%"></textarea></p>
<button>Match</button></form>{body}"""


def make_handler(
    taxonomy: SkillTaxonomy, jobs: Path, skills: Path, top_k: int
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, page: str) -> None:
            data = page.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            self._send(render_page(taxonomy, None, None))

        def do_POST(self) -> None:
            length = min(int(self.headers.get("Content-Length", 0)), 200_000)
            form = parse_qs(self.rfile.read(length).decode())
            ids = set(form.get("skill", []))
            ids.update(extract_skill_ids(" ".join(form.get("text", [])), taxonomy))
            ids &= set(taxonomy.by_id)
            try:
                result = rank_jobs(sorted(ids), jobs, skills, taxonomy, top_k=top_k)
                self._send(render_page(taxonomy, result, None))
            except (ValueError, FileNotFoundError) as exc:
                self._send(render_page(taxonomy, None, str(exc)))

        def log_message(self, *args: object) -> None:
            return

    return Handler


def main() -> None:
    root = Path.cwd()
    p = argparse.ArgumentParser(description="Local matcher demo (binds to 127.0.0.1 only).")
    p.add_argument("--jobs", type=Path, default=root / "data/processed/jobs.parquet")
    p.add_argument("--skills", type=Path, default=root / "data/processed/job_skills.parquet")
    p.add_argument("--taxonomy", type=Path, default=root / "configs/skill_taxonomy.toml")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--top-k", type=int, default=10)
    a = p.parse_args()
    taxonomy = load_taxonomy(a.taxonomy)
    server = HTTPServer(("127.0.0.1", a.port), make_handler(taxonomy, a.jobs, a.skills, a.top_k))
    print(json.dumps({"url": f"http://127.0.0.1:{a.port}"}))
    server.serve_forever()


if __name__ == "__main__":
    main()
