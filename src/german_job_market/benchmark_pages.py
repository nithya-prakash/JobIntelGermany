# ruff: noqa: E501
"""Local, offline HTML helpers for human annotation and judging.

The pages embed restricted ad text, so they are written only under the git-ignored
``data/processed/eval_v2/`` directory. They compute nothing: no extractor output or hints.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from german_job_market.skills import SkillTaxonomy

_CSS = (
    "body{font:15px system-ui;max-width:900px;margin:1em auto;padding:0 1em}"
    ".t{white-space:pre-wrap;border:1px solid #888;padding:.7em;max-height:45vh;overflow:auto}"
    "select{margin:2px}button{margin:4px;padding:6px 12px}"
)

_ANNOTATE_JS = """
const D=JSON.parse(document.getElementById('d').textContent);let i=0;
const K='gjmi-annotate-v1',S=JSON.parse(localStorage.getItem(K)||'{}');
function save(){localStorage.setItem(K,JSON.stringify(S))}
function show(){const j=D.jobs[i],st=S[j.job_id]||{reviewed:false,skills:{}};
document.getElementById('h').textContent=`Posting ${i+1}/${D.jobs.length} (${j.job_id}) - reviewed: `+
Object.values(S).filter(x=>x.reviewed).length;
document.getElementById('t').textContent=j.title+'\\n\\n'+j.description;
const box=document.getElementById('s');box.innerHTML='';
for(const s of D.skills){const r=document.createElement('div');
r.append(s.label+' ('+s.id+'): ');const sel=document.createElement('select');
for(const v of ['','required','mentioned']){const o=document.createElement('option');o.value=o.text=v;sel.append(o)}
sel.value=st.skills[s.id]||'';sel.onchange=()=>{const c=S[j.job_id]||{reviewed:false,skills:{}};
if(sel.value)c.skills[s.id]=sel.value;else delete c.skills[s.id];S[j.job_id]=c;save()};
r.append(sel);box.append(r)}}
function go(d){const j=D.jobs[i];const c=S[j.job_id]||{reviewed:false,skills:{}};c.reviewed=true;S[j.job_id]=c;save();
i=Math.max(0,Math.min(D.jobs.length-1,i+d));show()}
function exp(){let o='job_id,skill,label\\n';for(const [id,v] of Object.entries(S)){if(!v.reviewed)continue;
const e=Object.entries(v.skills);if(!e.length)o+=id+',,\\n';for(const [k,l] of e)o+=id+','+k+','+l+'\\n'}
const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([o],{type:'text/csv'}));
a.download='annotations.csv';a.click()}
show();
"""

_JUDGE_JS = """
const D=JSON.parse(document.getElementById('d').textContent);let qi=0,ii=0;
const K='gjmi-judge-v1',G=JSON.parse(localStorage.getItem(K)||'{}');
function save(){localStorage.setItem(K,JSON.stringify(G))}
function show(){const q=D.queries[qi],it=q.items[ii];
document.getElementById('h').textContent=`Query ${qi+1}/${D.queries.length} (${q.query_id}), job ${ii+1}/${q.items.length}`;
document.getElementById('q').textContent='Candidate skills: '+q.skills.join(', ');
document.getElementById('t').textContent=it.title+' | '+(it.company||'')+'\\n\\n'+it.description;
document.getElementById('g').value=(G[q.query_id+'|'+it.job_id]??'')}
function setg(v){const q=D.queries[qi],it=q.items[ii];if(v!=='')G[q.query_id+'|'+it.job_id]=Number(v);
else delete G[q.query_id+'|'+it.job_id];save()}
function go(d){ii+=d;if(ii<0){qi=Math.max(0,qi-1);ii=D.queries[qi].items.length-1}
else if(ii>=D.queries[qi].items.length){if(qi<D.queries.length-1){qi++;ii=0}else ii--}show()}
function exp(){const j=document.getElementById('j').value.trim();let o='';
for(const q of D.queries)for(const it of q.items){const g=G[q.query_id+'|'+it.job_id];
o+=JSON.stringify({query_id:q.query_id,job_id:it.job_id,grade:g===undefined?null:g,judge:j||null})+'\\n'}
const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([o],{type:'application/json'}));
a.download='pool_sheet.jsonl';a.click()}
show();
"""


def _page(title: str, payload: dict[str, Any], body: str, script: str) -> str:
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return (
        f"<!doctype html><meta charset=utf-8><title>{title}</title><style>{_CSS}</style>"
        f"<h3 id=h></h3>{body}<script id=d type=application/json>{data}</script>"
        f"<script>{script}</script>"
    )


def write_annotate_page(
    pack_path: Path, job_ids: set[str] | None, taxonomy: SkillTaxonomy, out_path: Path
) -> int:
    jobs = [
        json.loads(line)
        for line in pack_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    jobs = [
        {"job_id": j["job_id"], "title": j["title"] or "", "description": j["description"] or ""}
        for j in jobs
        if job_ids is None or j["job_id"] in job_ids
    ]
    skills = [{"id": s.id, "label": s.label} for s in taxonomy.skills]
    body = (
        "<div class=t id=t></div><div id=s></div>"
        "<button onclick='go(-1)'>Prev</button><button onclick='go(1)'>Save &amp; next</button>"
        "<button onclick='exp()'>Export CSV</button>"
        "<p>Mark only skills the posting uses as a tool, method or competency. Leave others blank.</p>"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        _page("Skill annotation", {"jobs": jobs, "skills": skills}, body, _ANNOTATE_JS),
        encoding="utf-8",
    )
    return len(jobs)


def write_judge_page(
    queries: list[dict[str, Any]],
    sheet: list[dict[str, Any]],
    pack_path: Path,
    out_path: Path,
) -> int:
    pack = {
        r["job_id"]: r
        for r in (
            json.loads(line)
            for line in pack_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    items: dict[str, list[dict[str, Any]]] = {}
    for row in sheet:
        job = pack[row["job_id"]]
        items.setdefault(row["query_id"], []).append(
            {
                "job_id": job["job_id"],
                "title": job["title"] or "",
                "company": job["company"] or "",
                "description": job["description"] or "",
            }
        )
    payload = {
        "queries": [
            {
                "query_id": q["query_id"],
                "skills": q["candidate_skill_ids"],
                "items": items[q["query_id"]],
            }
            for q in queries
            if q["query_id"] in items
        ]
    }
    body = (
        "<p id=q></p><div class=t id=t></div>"
        "<p>Relevance to this candidate: 0 irrelevant, 1 weak, 2 good, 3 excellent "
        "<select id=g onchange='setg(this.value)'><option value=''></option>"
        "<option>0</option><option>1</option><option>2</option><option>3</option></select></p>"
        "<button onclick='go(-1)'>Prev</button><button onclick='go(1)'>Next</button>"
        "Judge name: <input id=j><button onclick='exp()'>Export pool_sheet.jsonl</button>"
        "<p>Save the export over data/evaluation/matching/pool_sheet.jsonl.</p>"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_page("Relevance judging", payload, body, _JUDGE_JS), encoding="utf-8")
    return sum(len(q["items"]) for q in payload["queries"])
