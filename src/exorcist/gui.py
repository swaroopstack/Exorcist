"""Local browser GUI: `exorcist gui` serves a dashboard on 127.0.0.1.

Stdlib only (no new deps, frozen-exe safe). The page calls back into
the same scan/clean core as the CLI. Binds localhost only; nothing
leaves the machine.
"""
from __future__ import annotations

import html
import json
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_PORT = 18751


def _json(handler: BaseHTTPRequestHandler, payload, status: int = 200) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _text(handler: BaseHTTPRequestHandler, body: str, ctype: str = "text/html") -> None:
    raw = body.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", ctype + "; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Exorcist - exorcise dead apps, safely</title>
<style>
body{font-family:Segoe UI,system-ui,sans-serif;max-width:1000px;margin:24px auto;padding:0 16px;color:#222}
h1{font-size:24px}.sub{color:#666;margin-top:-12px}
.warn{background:#fff8e1;border:1px solid #f0d060;padding:10px 14px;border-radius:8px}
.btns{margin:16px 0;display:flex;gap:8px;flex-wrap:wrap}
button{padding:8px 16px;font-size:14px;border-radius:6px;border:1px solid #888;background:#f4f4f4;cursor:pointer}
button.primary{background:#2e7d32;color:#fff;border-color:#2e7d32}
button:disabled{opacity:.5;cursor:wait}
table{border-collapse:collapse;width:100%;margin-top:12px;font-size:14px}
th,td{border:1px solid #ddd;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#f0f0f0}.risk-Safe{background:#e8f5e9}.risk-Check{background:#fff8e1}.risk-Skip{background:#fce4ec}
.mono{font-family:Consolas,monospace;font-size:12px;word-break:break-all}
#status{margin:12px 0;color:#555}
.row{display:flex;gap:8px;align-items:center;margin:8px 0;flex-wrap:wrap}
input[type=text]{padding:6px 8px;font-size:14px}
</style></head><body>
<h1>Exorcist</h1>
<p class="sub">Free up your Windows drive. Safely. Nothing is ever permanently deleted.</p>
<div class="warn"><b>Nothing is ever deleted permanently.</b> Recycle Bin (or quarantine) only, per-item confirm.</div>
<div class="btns">
<button onclick="runScan()">Scan orphans + junk</button>
<button onclick="runLarge()">Large files</button>
<button onclick="runDupes()">Duplicates</button>
<button onclick="runLeftovers()">App leftovers</button>
</div>
<div class="row" id="leftrow" style="display:none">
<input type="text" id="appname" placeholder="App name, e.g. Perplexity">
<button onclick="runLeftovers()">Show leftovers</button>
</div>
<div id="status"></div>
<div id="out"></div>
<div class="btns" id="cleanrow" style="display:none">
<button class="primary" onclick="cleanChecked(false)">Recycle checked (dry-run first)</button>
<button class="primary" onclick="cleanChecked(true)">Recycle checked for real</button>
</div>
<script>
let current=[];
function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
function setBusy(b,m){document.querySelectorAll("button").forEach(x=>x.disabled=b);document.getElementById("status").textContent=m||""}
function showTable(rows){
  current=rows;
  if(!rows.length){document.getElementById("out").innerHTML="<p>No candidates found.</p>";document.getElementById("cleanrow").style.display="none";return}
  let h="<table><tr><th></th><th>Risk</th><th>Size</th><th>What is it?</th><th>Path</th></tr>";
  rows.forEach((r,i)=>{
    let cls=r.risk.startsWith("Safe")?"risk-Safe":(r.risk.startsWith("Check")?"risk-Check":"risk-Skip");
    let chk=(r.risk.startsWith("Safe")||r.risk.startsWith("Check"))?"checked":"";
    h+=`<tr class="${cls}"><td><input type="checkbox" data-i="${i}" ${chk}></td><td>${esc(r.risk)}</td><td>${esc(r.size)}</td><td>${esc(r.what||"")}</td><td class="mono">${esc(r.path)}</td></tr>`;
  });
  document.getElementById("out").innerHTML=h+"</table>";
  document.getElementById("cleanrow").style.display="flex";
}
async function get(url){
  setBusy(true,"Working...");
  try{let r=await fetch(url);let j=await r.json();if(j.error)throw new Error(j.error);return j}
  finally{setBusy(false,"")}
}
async function runScan(){let j=await get("/api/scan?min_mb=50");showTable(j.findings);document.getElementById("status").textContent=j.findings.length+" candidates."}
async function runLarge(){let j=await get("/api/large-files?min_mb=100");showTable(j.files.map(f=>({risk:"Check First",size:f.size,what:f.category,path:f.path})));document.getElementById("status").textContent=j.files.length+" large files."}
async function runDupes(){
  let j=await get("/api/dupes?min_mb=50");
  let rows=[];
  j.groups.forEach(g=>{g.recycle.forEach(p=>rows.push({risk:"Check First",size:g.reclaim_each,what:"Duplicate of "+g.keeper,path:p}))});
  showTable(rows);document.getElementById("status").textContent=j.groups.length+" duplicate groups, "+j.reclaimable+" reclaimable.";
}
async function runLeftovers(){
  let box=document.getElementById("leftrow");box.style.display="flex";
  let app=document.getElementById("appname").value.trim();if(!app)return;
  let j=await get("/api/leftovers?app="+encodeURIComponent(app));
  showTable(j.traces.map(t=>({risk:t.checked?"Check First":"Skipped",size:t.size,what:t.what,path:t.path})));
}
async function cleanChecked(real){
  let boxes=[...document.querySelectorAll("input[type=checkbox]:checked")];
  if(!boxes.length){alert("Nothing checked.");return}
  let big=current.filter((r,i)=>boxes.some(b=>+b.dataset.i===i)&&parseFloat(r.size)>500);
  if(real && !confirm("Move "+boxes.length+" item(s) to Recycle Bin?"))return;
  if(real&&big.length&&!confirm(big.length+" item(s) are over 500MB. Really continue?"))return;
  setBusy(true,"Recycling...");
  try{
    let paths=boxes.map(b=>current[+b.dataset.i].path);
    let r=await fetch("/api/clean",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({paths,dry_run:!real})});
    let j=await r.json();
    document.getElementById("status").textContent=j.results.filter(x=>x.ok).length+" of "+j.results.length+" processed. Refresh a scan to update.";
    alert(j.results.map(x=>(x.ok?"OK  ":"FAIL ")+x.path).join("\\n").slice(0,2000));
  }finally{setBusy(false,"")}
}
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "ExorcistGUI/0.4"

    def log_message(self, *args):  # quiet
        pass

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(url.query)
        try:
            if url.path == "/":
                _text(self, PAGE)
            elif url.path == "/api/scan":
                from .cli import collect
                from .reporter import fmt_size

                findings = collect(min_mb=float(q.get("min_mb", ["50"])[0]))
                _json(self, {"findings": [
                    {"path": f.path, "size": fmt_size(f.size_bytes), "risk": f.risk,
                     "kind": f.kind, "what": f.what or f.reason} for f in findings]})
            elif url.path == "/api/large-files":
                from .largefiles import user_scan_roots, walk_large_files
                from .reporter import fmt_size

                files = walk_large_files(user_scan_roots(),
                                         int(float(q.get("min_mb", ["100"])[0]) * 1024 * 1024),
                                         max_depth=0 if q.get("full") else 3)[:100]
                _json(self, {"files": [
                    {"path": f.path, "size": fmt_size(f.size_bytes),
                     "category": f.source or f.category,
                     "age_days": round(f.age_days, 1)} for f in files]})
            elif url.path == "/api/dupes":
                from .dupes import find_duplicates
                from .largefiles import user_scan_roots, walk_large_files
                from .reporter import fmt_size

                files = walk_large_files(user_scan_roots(),
                                         int(float(q.get("min_mb", ["50"])[0]) * 1024 * 1024),
                                         max_depth=4)
                groups, _ = find_duplicates([f.path for f in files])
                _json(self, {"groups": [
                    {"keeper": g.keeper, "recycle": [p for p in g.paths if p != g.keeper],
                     "reclaim_each": fmt_size(g.size_bytes)} for g in groups[:30]],
                    "reclaimable": fmt_size(sum(g.reclaimable_bytes for g in groups))})
            elif url.path == "/api/leftovers":
                from .leftovers import find_app_traces
                from .reporter import fmt_size

                app = q.get("app", [""])[0]
                traces = find_app_traces(app) if app else []
                _json(self, {"traces": [
                    {"path": t.path, "size": fmt_size(t.size_bytes),
                     "what": t.what, "checked": t.checked, "match": t.match} for t in traces]})
            else:
                _json(self, {"error": "unknown route"}, status=404)
        except Exception as exc:  # noqa: BLE001
            _json(self, {"error": str(exc)}, status=500)

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        if url.path != "/api/clean":
            _json(self, {"error": "unknown route"}, status=404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, OSError):
            _json(self, {"error": "bad JSON"}, status=400)
            return
        try:
            from .cleaner import safe_delete

            results = []
            for path in data.get("paths", [])[:100]:
                ok, msg = safe_delete(path, dry_run=bool(data.get("dry_run", True)), kind="gui")
                results.append({"path": path, "ok": ok, "message": msg})
            _json(self, {"results": results})
        except Exception as exc:  # noqa: BLE001
            _json(self, {"error": str(exc)}, status=500)


def run_server(port: int = DEFAULT_PORT, open_browser: bool = True) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    if open_browser:
        threading.Timer(0.5, webbrowser.open,
                        args=(f"http://127.0.0.1:{server.server_port}/",)).start()
    return server


def cmd_gui(args) -> int:
    from .cleaner import setup_logging

    setup_logging(args.verbose)
    port = args.port
    try:
        server = run_server(port)
    except OSError:
        server = run_server(0)  # port busy -> any free port
    print(f"Exorcist GUI at http://127.0.0.1:{server.server_port}/  (localhost only, Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0
