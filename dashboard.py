# Dashboard FastAPI - Centre de controle complet du bot Vinted
import os
import json
import threading
import asyncio
import csv
import io
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Request, BackgroundTasks, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
import uvicorn
import config
import database

app = FastAPI(title="Bot Vinted Dashboard")

BOT_STATUS = {
    "bot_actif": True,
    "posting_en_cours": False,
    "scraping_en_cours": False,
    "audit_en_cours": False,
    "derniere_activite": datetime.now().isoformat(),
    "logs_recents": [],
}


def add_log(message: str, niveau: str = "info") -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    BOT_STATUS["logs_recents"].insert(0, {"time": timestamp, "msg": message, "niveau": niveau})
    BOT_STATUS["logs_recents"] = BOT_STATUS["logs_recents"][:50]
    BOT_STATUS["derniere_activite"] = datetime.now().isoformat()
    database.log_session(niveau, niveau, message)


# ─── HTML BASE ────────────────────────────────────────────────────────────────

def base_html(page_active: str, content: str, titre_page: str, badges: dict = None) -> str:
    if badges is None:
        try:
            stats = database.get_stats_dashboard()
            badges = {
                "annonces": stats.get("annonces_en_attente", 0),
                "ventes": stats.get("commandes_a_passer", 0) + stats.get("colis_a_envoyer", 0),
                "colis": stats.get("colis_a_envoyer", 0),
            }
        except Exception:
            badges = {"annonces": 0, "ventes": 0, "colis": 0}

    nav_items = [
        ("accueil", "/", "🏠", "Accueil"),
        ("annonces", "/annonces", "📋", "Annonces"),
        ("produits", "/produits", "📦", "Produits"),
        ("ventes", "/ventes", "💰", "Ventes"),
        ("colis", "/colis", "🚚", "Colis"),
        ("parametres", "/parametres", "⚙️", "Paramètres"),
        ("logs", "/logs", "📊", "Logs"),
    ]

    nav_html = ""
    for key, href, icon, label in nav_items:
        active_class = "nav-active" if page_active == key else ""
        badge = ""
        if key == "annonces" and badges.get("annonces", 0) > 0:
            badge = f'<span class="badge">{badges["annonces"]}</span>'
        elif key == "ventes" and badges.get("ventes", 0) > 0:
            badge = f'<span class="badge">{badges["ventes"]}</span>'
        elif key == "colis" and badges.get("colis", 0) > 0:
            badge = f'<span class="badge">{badges["colis"]}</span>'
        nav_html += f'<a href="{href}" class="nav-link {active_class}">{icon} {label}{badge}</a>\n'

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{titre_page} — Bot Vinted</title>
<style>
:root {{
  --bg: #0f0f1a;
  --card: #1a1a2e;
  --card2: #16213e;
  --accent: #7c3aed;
  --accent2: #a855f7;
  --accent-light: #ede9fe;
  --green: #10b981;
  --red: #ef4444;
  --orange: #f97316;
  --yellow: #eab308;
  --text: #e2e8f0;
  --text2: #94a3b8;
  --border: #2d2d4e;
  --radius: 12px;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; display: flex; }}
.sidebar {{
  width: 220px; min-height: 100vh; background: var(--card);
  border-right: 1px solid var(--border); display: flex; flex-direction: column;
  position: fixed; left: 0; top: 0; z-index: 100;
}}
.sidebar-logo {{
  padding: 20px 16px; border-bottom: 1px solid var(--border);
  font-size: 1.1rem; font-weight: 700; color: var(--accent2);
  display: flex; align-items: center; gap: 8px;
}}
.sidebar-logo span {{ font-size: 1.4rem; }}
.nav-link {{
  display: flex; align-items: center; gap: 10px; padding: 12px 16px;
  color: var(--text2); text-decoration: none; border-radius: 8px; margin: 2px 8px;
  transition: all 0.2s; font-size: 0.9rem; position: relative;
}}
.nav-link:hover {{ background: var(--card2); color: var(--text); }}
.nav-active {{ background: var(--accent) !important; color: white !important; }}
.badge {{
  background: var(--red); color: white; border-radius: 10px;
  padding: 1px 7px; font-size: 0.7rem; font-weight: 700; margin-left: auto;
}}
.main {{ margin-left: 220px; flex: 1; padding: 24px; min-height: 100vh; }}
.page-header {{ margin-bottom: 24px; }}
.page-title {{ font-size: 1.6rem; font-weight: 700; color: var(--text); }}
.page-sub {{ color: var(--text2); font-size: 0.9rem; margin-top: 4px; }}
.card {{
  background: var(--card); border-radius: var(--radius); padding: 20px;
  border: 1px solid var(--border); margin-bottom: 16px;
}}
.card-title {{ font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text2); margin-bottom: 8px; }}
.grid {{ display: grid; gap: 16px; }}
.grid-2 {{ grid-template-columns: repeat(2, 1fr); }}
.grid-3 {{ grid-template-columns: repeat(3, 1fr); }}
.grid-4 {{ grid-template-columns: repeat(4, 1fr); }}
.grid-6 {{ grid-template-columns: repeat(6, 1fr); }}
.kpi-value {{ font-size: 2rem; font-weight: 700; }}
.kpi-label {{ font-size: 0.8rem; color: var(--text2); margin-top: 4px; }}
.kpi-icon {{ font-size: 1.8rem; margin-bottom: 8px; }}
.green {{ color: var(--green); }}
.red {{ color: var(--red); }}
.orange {{ color: var(--orange); }}
.purple {{ color: var(--accent2); }}
.yellow {{ color: var(--yellow); }}
.btn {{
  display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px;
  border-radius: 8px; border: none; cursor: pointer; font-size: 0.85rem;
  font-weight: 600; transition: all 0.2s; text-decoration: none;
}}
.btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
.btn-primary {{ background: var(--accent); color: white; }}
.btn-primary:hover {{ background: var(--accent2); }}
.btn-success {{ background: var(--green); color: white; }}
.btn-success:hover {{ background: #059669; }}
.btn-danger {{ background: var(--red); color: white; }}
.btn-danger:hover {{ background: #dc2626; }}
.btn-warning {{ background: var(--orange); color: white; }}
.btn-warning:hover {{ background: #ea580c; }}
.btn-ghost {{ background: transparent; color: var(--text2); border: 1px solid var(--border); }}
.btn-ghost:hover {{ background: var(--card2); color: var(--text); }}
.btn-sm {{ padding: 5px 10px; font-size: 0.78rem; }}
.btn-lg {{ padding: 12px 24px; font-size: 1rem; }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ text-align: left; padding: 10px 12px; font-size: 0.75rem; text-transform: uppercase; color: var(--text2); border-bottom: 1px solid var(--border); }}
td {{ padding: 10px 12px; border-bottom: 1px solid var(--border); font-size: 0.85rem; vertical-align: middle; }}
tr:last-child td {{ border-bottom: none; }}
tr:hover td {{ background: rgba(255,255,255,0.02); }}
.status-pill {{
  display: inline-flex; padding: 3px 10px; border-radius: 20px;
  font-size: 0.72rem; font-weight: 600; text-transform: uppercase;
}}
.pill-green {{ background: rgba(16,185,129,0.2); color: var(--green); }}
.pill-red {{ background: rgba(239,68,68,0.2); color: var(--red); }}
.pill-orange {{ background: rgba(249,115,22,0.2); color: var(--orange); }}
.pill-purple {{ background: rgba(124,58,237,0.2); color: var(--accent2); }}
.pill-gray {{ background: rgba(148,163,184,0.15); color: var(--text2); }}
.toggle-wrap {{ display: flex; align-items: center; gap: 12px; }}
.toggle {{ position: relative; width: 44px; height: 24px; }}
.toggle input {{ display: none; }}
.toggle-slider {{
  position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  background: var(--border); border-radius: 12px; cursor: pointer;
  transition: 0.3s;
}}
.toggle-slider:before {{
  content: ""; position: absolute; width: 18px; height: 18px;
  left: 3px; top: 3px; background: white; border-radius: 50%; transition: 0.3s;
}}
.toggle input:checked + .toggle-slider {{ background: var(--green); }}
.toggle input:checked + .toggle-slider:before {{ transform: translateX(20px); }}
.input-field {{
  background: var(--card2); border: 1px solid var(--border); color: var(--text);
  padding: 8px 12px; border-radius: 8px; width: 100%; font-size: 0.85rem;
  outline: none; transition: border-color 0.2s;
}}
.input-field:focus {{ border-color: var(--accent); }}
.input-group {{ margin-bottom: 12px; }}
.input-label {{ font-size: 0.78rem; color: var(--text2); margin-bottom: 4px; display: block; }}
textarea.input-field {{ resize: vertical; min-height: 80px; }}
.section-title {{ font-size: 1rem; font-weight: 600; color: var(--accent2); margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }}
.flex {{ display: flex; }}
.flex-between {{ display: flex; justify-content: space-between; align-items: center; }}
.flex-center {{ display: flex; align-items: center; }}
.gap-8 {{ gap: 8px; }}
.gap-12 {{ gap: 12px; }}
.mb-16 {{ margin-bottom: 16px; }}
.mb-24 {{ margin-bottom: 24px; }}
.mt-16 {{ margin-top: 16px; }}
.terminal {{
  background: #0a0a0a; border: 1px solid #333; border-radius: 8px;
  padding: 16px; font-family: 'Courier New', monospace; font-size: 0.78rem;
  max-height: 300px; overflow-y: auto; line-height: 1.6;
}}
.log-info {{ color: #4ade80; }}
.log-error {{ color: #f87171; }}
.log-warning {{ color: #fb923c; }}
.log-debug {{ color: #6b7280; }}
.log-time {{ color: #6b7280; margin-right: 8px; }}
.toast-container {{ position: fixed; bottom: 24px; right: 24px; z-index: 9999; display: flex; flex-direction: column; gap: 8px; }}
.toast {{
  padding: 12px 20px; border-radius: 8px; color: white; font-size: 0.85rem;
  font-weight: 600; max-width: 350px; animation: slideIn 0.3s ease;
  box-shadow: 0 4px 20px rgba(0,0,0,0.4);
}}
.toast-success {{ background: var(--green); }}
.toast-error {{ background: var(--red); }}
.toast-info {{ background: var(--accent); }}
@keyframes slideIn {{ from {{ transform: translateX(100%); opacity: 0; }} to {{ transform: translateX(0); opacity: 1; }} }}
.spinner {{ width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; animation: spin 0.6s linear infinite; display: inline-block; }}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}
.modal-overlay {{
  display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.7);
  z-index: 1000; align-items: center; justify-content: center;
}}
.modal-overlay.active {{ display: flex; }}
.modal {{
  background: var(--card); border-radius: var(--radius); padding: 24px;
  max-width: 520px; width: 90%; border: 1px solid var(--border);
}}
.modal-title {{ font-size: 1.1rem; font-weight: 700; margin-bottom: 16px; }}
.tabs {{ display: flex; gap: 4px; border-bottom: 1px solid var(--border); margin-bottom: 20px; }}
.tab {{
  padding: 8px 16px; cursor: pointer; border-bottom: 2px solid transparent;
  color: var(--text2); font-size: 0.85rem; transition: all 0.2s; user-select: none;
}}
.tab:hover {{ color: var(--text); }}
.tab.active {{ color: var(--accent2); border-bottom-color: var(--accent2); font-weight: 600; }}
.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}
.product-img {{ width: 48px; height: 48px; border-radius: 6px; object-fit: cover; background: var(--card2); }}
.status-dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 6px; }}
.dot-green {{ background: var(--green); }}
.dot-red {{ background: var(--red); }}
.dot-orange {{ background: var(--orange); }}
.pagination {{ display: flex; gap: 4px; align-items: center; }}
.page-btn {{
  padding: 6px 12px; border-radius: 6px; border: 1px solid var(--border);
  background: var(--card2); color: var(--text2); cursor: pointer; font-size: 0.8rem;
}}
.page-btn.active {{ background: var(--accent); color: white; border-color: var(--accent); }}
.page-btn:hover:not(.active) {{ background: var(--card); color: var(--text); }}
.bot-status-bar {{
  display: flex; align-items: center; gap: 16px; padding: 12px 20px;
  border-radius: var(--radius); margin-bottom: 20px; border: 1px solid var(--border);
}}
.status-indicator {{
  width: 12px; height: 12px; border-radius: 50%;
  animation: pulse 2s infinite;
}}
.indicator-green {{ background: var(--green); box-shadow: 0 0 8px var(--green); }}
.indicator-red {{ background: var(--red); }}
@keyframes pulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} }}
.conn-indicator {{ display: flex; align-items: center; gap: 6px; font-size: 0.8rem; }}
svg-bar {{ display: block; }}
@media (max-width: 768px) {{
  .sidebar {{ width: 60px; }}
  .nav-link span:not(.badge) {{ display: none; }}
  .sidebar-logo .logo-text {{ display: none; }}
  .main {{ margin-left: 60px; padding: 12px; }}
  .grid-4, .grid-6 {{ grid-template-columns: repeat(2, 1fr); }}
  .grid-3 {{ grid-template-columns: repeat(2, 1fr); }}
}}
</style>
</head>
<body>
<div class="sidebar">
  <div class="sidebar-logo"><span>💜</span><span class="logo-text">Bot Vinted</span></div>
  {nav_html}
  <div style="margin-top:auto;padding:12px 16px;font-size:0.7rem;color:var(--text2);border-top:1px solid var(--border)">
    v1.0 Production
  </div>
</div>
<div class="main">
  <div class="page-header">
    <div class="page-title">{titre_page}</div>
    <div class="page-sub" id="last-update">Derniere mise a jour: {datetime.now().strftime("%H:%M:%S")}</div>
  </div>
  {content}
</div>
<div class="toast-container" id="toastContainer"></div>

<script>
function showToast(msg, type='info') {{
  const c = document.getElementById('toastContainer');
  const t = document.createElement('div');
  t.className = `toast toast-${{type}}`;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.remove(), 3500);
}}

function confirmAction(msg, cb) {{
  if (confirm(msg)) cb();
}}

async function apiCall(url, method='POST', body=null) {{
  try {{
    const opts = {{ method, headers: {{'Content-Type': 'application/json'}} }};
    if (body) opts.body = JSON.stringify(body);
    const r = await fetch(url, opts);
    const data = await r.json();
    return data;
  }} catch(e) {{
    showToast('Erreur reseau: ' + e.message, 'error');
    return null;
  }}
}}

async function updateBadges() {{
  try {{
    const s = await fetch('/api/stats').then(r => r.json());
    const att = s.annonces_en_attente || 0;
    const col = (s.colis_a_envoyer || 0) + (s.commandes_a_passer || 0);
    document.querySelectorAll('[data-badge="annonces"]').forEach(el => {{
      el.textContent = att > 0 ? att : '';
      el.style.display = att > 0 ? 'inline' : 'none';
    }});
    document.querySelectorAll('[data-badge="colis"]').forEach(el => {{
      el.textContent = col > 0 ? col : '';
      el.style.display = col > 0 ? 'inline' : 'none';
    }});
  }} catch(e) {{}}
}}

async function toggleBot(val) {{
  const r = await apiCall('/api/bot/toggle', 'POST', {{actif: val}});
  if (r && r.ok) showToast(val ? 'Bot active' : 'Bot en pause', val ? 'success' : 'info');
}}

async function togglePosting(val) {{
  const r = await apiCall('/api/bot/posting/toggle', 'POST', {{actif: val}});
  if (r && r.ok) showToast(val ? 'Posting active' : 'Posting desactive', 'info');
}}

setInterval(updateBadges, 30000);
</script>
</body>
</html>"""


# ─── PAGE ACCUEIL ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def page_accueil():
    try:
        stats = database.get_stats_dashboard()
        bot_actif = stats.get("bot_actif", False)
        status_class = "indicator-green" if bot_actif else "indicator-red"
        status_txt = "BOT ACTIF" if bot_actif else "BOT EN PAUSE"
        status_color = "var(--green)" if bot_actif else "var(--red)"

        # Graphique revenus SVG
        revenus = stats.get("revenus_par_jour", [])
        max_val = max((r["total"] for r in revenus), default=1) or 1
        svg_bars = ""
        if revenus:
            bar_w = max(2, 580 // max(len(revenus), 1))
            for i, r in enumerate(revenus[-30:]):
                h = max(2, int((r["total"] / max_val) * 120))
                x = i * (bar_w + 2)
                svg_bars += f'<rect x="{x}" y="{140 - h}" width="{bar_w}" height="{h}" fill="#7c3aed" rx="2" opacity="0.8"><title>{r["jour"]}: {r["total"]:.2f}EUR</title></rect>'

        logs_html = ""
        for log in database.get_logs_recents(10):
            cls = "log-info" if log["statut"] == "succes" else "log-error" if log["statut"] == "erreur" else "log-debug"
            logs_html += f'<div><span class="log-time">{log["date_debut"][:16]}</span><span class="{cls}">[{log["type_action"]}] {log["details"][:80]}</span></div>\n'

        content = f"""
<div class="bot-status-bar" style="background:var(--card)">
  <div class="status-indicator {status_class}"></div>
  <span style="font-weight:700;color:{status_color};font-size:1rem">{status_txt}</span>
  <label class="toggle" style="margin-left:8px">
    <input type="checkbox" {"checked" if bot_actif else ""} onchange="toggleBot(this.checked)">
    <span class="toggle-slider"></span>
  </label>
  <span style="color:var(--text2);font-size:0.8rem;margin-left:auto">Derniere activite: {stats.get("derniere_activite","")[:16]}</span>
</div>

<div class="grid grid-6 mb-16">
  <div class="card"><div class="kpi-icon">💰</div><div class="kpi-value green">{stats["ventes_jour"]}</div><div class="kpi-label">Ventes aujourd'hui</div></div>
  <div class="card"><div class="kpi-icon">📈</div><div class="kpi-value green">{stats["ca_jour"]:.2f}€</div><div class="kpi-label">CA aujourd'hui</div></div>
  <div class="card"><div class="kpi-icon">📋</div><div class="kpi-value purple">{stats["annonces_en_ligne"]}</div><div class="kpi-label">Annonces en ligne</div></div>
  <div class="card"><div class="kpi-icon">🚚</div><div class="kpi-value orange">{stats["colis_a_envoyer"]}</div><div class="kpi-label">Colis a envoyer</div></div>
  <div class="card"><div class="kpi-icon">⏳</div><div class="kpi-value yellow">{stats["annonces_en_attente"]}</div><div class="kpi-label">En attente valid.</div></div>
  <div class="card"><div class="kpi-icon">🏆</div><div class="kpi-value green">{stats["ca_mois"]:.2f}€</div><div class="kpi-label">CA ce mois</div></div>
</div>

<div class="grid grid-2 mb-16">
  <div class="card">
    <div class="section-title">Revenus 30 derniers jours</div>
    <svg width="100%" height="160" viewBox="0 0 600 160" preserveAspectRatio="none">
      <rect width="600" height="160" fill="transparent"/>
      {svg_bars}
    </svg>
  </div>
  <div class="card">
    <div class="section-title">Actions rapides</div>
    <div class="grid grid-2 gap-8">
      <button class="btn btn-primary btn-lg" id="btnScraping" onclick="lancerScraping()">🔍 Lancer scraping</button>
      <button class="btn btn-success btn-lg" id="btnPosting" onclick="lancerPosting()">📤 Lancer posting</button>
      <button class="btn btn-warning btn-lg" onclick="envoyerRecap()">📦 Recap colis</button>
      <button class="btn btn-ghost btn-lg" onclick="lancerAudit()">🔎 Audit stock</button>
    </div>
    <div class="mt-16">
      <div class="section-title">Statut connexions</div>
      <div id="conn-status">
        <div class="conn-indicator"><span class="status-dot dot-green"></span>Telegram — <span id="tg-status">Verification...</span></div>
        <div class="conn-indicator mt-8"><span class="status-dot" id="claude-dot"></span>Claude API — <span id="claude-status">...</span></div>
        <div class="conn-indicator mt-8"><span class="status-dot dot-orange"></span>Vinted OAuth</div>
      </div>
    </div>
  </div>
</div>

<div class="grid grid-2">
  <div class="card">
    <div class="section-title">Dernieres ventes</div>
    <table>
      <tr><th>Produit</th><th>Montant</th><th>Date</th></tr>
      {"".join(f'<tr><td>{v.get("titre_vinted","N/A")[:30]}</td><td class="green">{v.get("montant",0):.2f}€</td><td style="color:var(--text2)">{v.get("date_vente","")[:10]}</td></tr>' for v in stats.get("dernieres_ventes",[])[:5]) or '<tr><td colspan="3" style="color:var(--text2)">Aucune vente pour l instant</td></tr>'}
    </table>
  </div>
  <div class="card">
    <div class="section-title">Terminal live</div>
    <div class="terminal" id="terminal">
      {logs_html or '<span class="log-debug">En attente d activite...</span>'}
    </div>
  </div>
</div>

<script>
async function lancerScraping() {{
  const btn = document.getElementById('btnScraping');
  btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> En cours...';
  const r = await apiCall('/api/bot/scraping/lancer');
  if (r) showToast('Scraping lance en arriere-plan!', 'success');
  setTimeout(() => {{ btn.disabled=false; btn.innerHTML='🔍 Lancer scraping'; }}, 3000);
}}
async function lancerPosting() {{
  const btn = document.getElementById('btnPosting');
  btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> En cours...';
  const r = await apiCall('/api/bot/posting/lancer');
  if (r) showToast('Posting lance en arriere-plan!', 'success');
  setTimeout(() => {{ btn.disabled=false; btn.innerHTML='📤 Lancer posting'; }}, 3000);
}}
async function envoyerRecap() {{
  const r = await apiCall('/api/bot/recap-colis');
  if (r) showToast('Recap colis envoye sur Telegram!', 'success');
}}
async function lancerAudit() {{
  const r = await apiCall('/api/bot/audit-stock');
  if (r) showToast('Audit stock lance!', 'info');
}}
async function verifierConnexions() {{
  try {{
    const r = await fetch('/api/status').then(x => x.json());
    document.getElementById('tg-status').textContent = r.telegram ? 'Connecte' : 'Erreur';
    const cd = document.getElementById('claude-dot');
    document.getElementById('claude-status').textContent = r.claude ? 'Connecte' : 'Cle invalide';
    cd.className = 'status-dot ' + (r.claude ? 'dot-green' : 'dot-red');
  }} catch(e) {{}}
}}
verifierConnexions();
setInterval(async () => {{
  const r = await fetch('/api/logs?filtre=all').then(x=>x.json()).catch(()=>null);
  if (!r) return;
  const t = document.getElementById('terminal');
  t.innerHTML = r.items.slice(0,10).map(l => {{
    const cls = l.statut==='erreur'?'log-error':l.statut==='succes'?'log-info':'log-debug';
    return `<div><span class="log-time">${{l.date_debut?.slice(0,16)||''}}</span><span class="${{cls}}">[{{'${{l.type_action}}'}}] ${{l.details?.slice(0,80)||''}}</span></div>`;
  }}).join('');
  document.getElementById('last-update').textContent = 'Derniere mise a jour: ' + new Date().toLocaleTimeString('fr-FR');
}}, 30000);
</script>"""

        return HTMLResponse(base_html("accueil", content, "Vue d'ensemble"))
    except Exception as e:
        return HTMLResponse(f"<p>Erreur: {e}</p>", status_code=500)


# ─── PAGE ANNONCES ────────────────────────────────────────────────────────────

@app.get("/annonces", response_class=HTMLResponse)
async def page_annonces(statut: str = "en_attente", page: int = 1, search: str = ""):
    try:
        data = database.get_toutes_annonces(statut if statut != "toutes" else None, page, 20, search)
        stats = database.get_stats_dashboard()
        annonces = data["items"]

        rows = ""
        for a in annonces:
            photo = f'<img src="{a.get("photo_url","")}" class="product-img" onerror="this.style.display=\'none\'">' if a.get("photo_url") else '<div class="product-img" style="background:var(--card2)"></div>'
            pill_map = {"en_attente": "pill-yellow", "approuvee": "pill-purple", "en_ligne": "pill-green", "vendue": "pill-gray", "refusee": "pill-red"}
            pill = pill_map.get(a.get("statut", ""), "pill-gray")
            actions = ""
            if a.get("statut") == "en_attente":
                actions = f"""
                  <button class="btn btn-success btn-sm" onclick="approuver({a['id']})">✓ Approuver</button>
                  <button class="btn btn-ghost btn-sm" onclick="ouvrirModif({a['id']}, '{a['titre_vinted'].replace("'","&#39;")}', {a['prix_vente']})">✎ Modifier</button>
                  <button class="btn btn-danger btn-sm" onclick="refuser({a['id']})">✗ Refuser</button>"""
            elif a.get("statut") == "approuvee":
                actions = f'<button class="btn btn-primary btn-sm" onclick="posterAnnonce({a["id"]})">📤 Poster</button>'
            elif a.get("statut") == "en_ligne":
                actions = f'<button class="btn btn-warning btn-sm" onclick="republier({a["id"]})">↺ Republier</button> <button class="btn btn-danger btn-sm" onclick="supprimerAnnonce({a["id"]})">🗑</button>'

            rows += f"""<tr>
              <td>{photo}</td>
              <td><div style="font-weight:600">{a.get('titre_vinted','')[:45]}</div><div style="color:var(--text2);font-size:0.75rem">{a.get('description','')[:60]}...</div></td>
              <td style="font-weight:700;color:var(--green)">{a.get('prix_vente',0):.2f}€</td>
              <td>{a.get('prix_achat',0):.2f}€</td>
              <td><span class="status-pill {pill}">{a.get('statut','')}</span></td>
              <td style="color:var(--text2);font-size:0.75rem">{a.get('date_creation','')[:10]}</td>
              <td class="flex gap-8">{actions}</td>
            </tr>"""

        tab_items = [
            ("en_attente", "En attente", str(stats.get("annonces_en_attente",0))),
            ("approuvee", "Approuvees", str(stats.get("annonces_approuvees",0))),
            ("en_ligne", "En ligne", str(stats.get("annonces_en_ligne",0))),
            ("toutes", "Toutes", ""),
        ]
        tabs_html = "".join(
            f'<a href="/annonces?statut={k}" class="tab {"active" if statut==k else ""}">{label} {"<span class=\"badge\" style=\"position:static;margin-left:4px\">"+cnt+"</span>" if cnt else ""}</a>'
            for k, label, cnt in tab_items
        )

        pagination = ""
        for p in range(1, data["pages"] + 1):
            pagination += f'<a href="/annonces?statut={statut}&page={p}" class="page-btn {"active" if p==page else ""}">{p}</a>'

        content = f"""
<div class="card mb-16">
  <div class="flex-between mb-16">
    <div class="tabs" style="border:none;margin:0">{tabs_html}</div>
    <div class="flex gap-8">
      <input class="input-field" style="width:200px" placeholder="Rechercher..." value="{search}" onchange="window.location='/annonces?statut={statut}&search='+this.value">
      <button class="btn btn-success" onclick="approuverToutes()">✓ Tout approuver</button>
      <button class="btn btn-primary" onclick="envoyerTelegram()">📱 Envoyer Telegram</button>
    </div>
  </div>
  <table>
    <tr><th>Photo</th><th>Titre / Description</th><th>Prix vente</th><th>Prix achat</th><th>Statut</th><th>Date</th><th>Actions</th></tr>
    {rows or '<tr><td colspan="7" style="text-align:center;color:var(--text2);padding:24px">Aucune annonce</td></tr>'}
  </table>
  <div class="flex-between mt-16">
    <span style="color:var(--text2);font-size:0.8rem">{data["total"]} annonces au total</span>
    <div class="pagination">{pagination}</div>
  </div>
</div>

<div id="modalModif" class="modal-overlay">
  <div class="modal">
    <div class="modal-title">Modifier l'annonce</div>
    <input type="hidden" id="modifId">
    <div class="input-group"><label class="input-label">Titre</label><input class="input-field" id="modifTitre"></div>
    <div class="input-group"><label class="input-label">Prix (€)</label><input class="input-field" type="number" step="0.01" id="modifPrix"></div>
    <div class="input-group"><label class="input-label">Description</label><textarea class="input-field" id="modifDesc" rows="4"></textarea></div>
    <div class="flex gap-8 mt-16">
      <button class="btn btn-primary" onclick="sauvegarderModif()">💾 Sauvegarder</button>
      <button class="btn btn-ghost" onclick="fermerModal()">Annuler</button>
    </div>
  </div>
</div>

<script>
async function approuver(id) {{
  const r = await apiCall(`/api/annonces/${{id}}/approuver`);
  if (r?.ok) {{ showToast('Annonce approuvee!','success'); setTimeout(()=>location.reload(),500); }}
  else showToast(r?.error||'Erreur','error');
}}
async function refuser(id) {{
  confirmAction('Refuser cette annonce?', async () => {{
    const r = await apiCall(`/api/annonces/${{id}}/refuser`);
    if (r?.ok) {{ showToast('Annonce refusee','info'); setTimeout(()=>location.reload(),500); }}
  }});
}}
async function approuverToutes() {{
  const r = await apiCall('/api/annonces/approuver-toutes');
  if (r?.ok) {{ showToast(`${{r.nb}} annonces approuvees!`,'success'); setTimeout(()=>location.reload(),800); }}
}}
async function envoyerTelegram() {{
  const r = await apiCall('/api/annonces/envoyer-telegram');
  if (r) showToast('Annonces envoyees sur Telegram!','success');
}}
async function posterAnnonce(id) {{
  const r = await apiCall(`/api/annonces/${{id}}/poster`);
  if (r?.ok) {{ showToast('Annonce postee!','success'); setTimeout(()=>location.reload(),800); }}
  else showToast(r?.error||'Erreur posting','error');
}}
async function republier(id) {{
  const r = await apiCall(`/api/annonces/${{id}}/approuver`);
  if (r?.ok) {{ showToast('Annonce remise en file','info'); setTimeout(()=>location.reload(),500); }}
}}
async function supprimerAnnonce(id) {{
  confirmAction('Supprimer cette annonce definitivement?', async () => {{
    const r = await apiCall(`/api/annonces/${{id}}/supprimer`);
    if (r?.ok) {{ showToast('Supprimee','info'); setTimeout(()=>location.reload(),500); }}
  }});
}}
function ouvrirModif(id, titre, prix) {{
  document.getElementById('modifId').value = id;
  document.getElementById('modifTitre').value = titre;
  document.getElementById('modifPrix').value = prix;
  document.getElementById('modalModif').classList.add('active');
}}
function fermerModal() {{
  document.getElementById('modalModif').classList.remove('active');
}}
async function sauvegarderModif() {{
  const id = document.getElementById('modifId').value;
  const titre = document.getElementById('modifTitre').value;
  const prix = parseFloat(document.getElementById('modifPrix').value);
  const desc = document.getElementById('modifDesc').value;
  const r = await apiCall(`/api/annonces/${{id}}/modifier`, 'POST', {{titre, prix, description: desc}});
  if (r?.ok) {{ showToast('Annonce modifiee!','success'); fermerModal(); setTimeout(()=>location.reload(),500); }}
  else showToast(r?.error||'Erreur','error');
}}
</script>"""

        return HTMLResponse(base_html("annonces", content, "Annonces"))
    except Exception as e:
        return HTMLResponse(f"<p>Erreur: {e}</p>", status_code=500)


# ─── PAGE PRODUITS ────────────────────────────────────────────────────────────

@app.get("/produits", response_class=HTMLResponse)
async def page_produits(page: int = 1):
    try:
        data = database.get_tous_produits(page, 20)
        produits = data["items"]

        rows = ""
        for p in produits:
            from generateur import calculer_prix_vente
            prix_vente = calculer_prix_vente(p.get("prix_achat", 0))
            photo = f'<img src="{p.get("photo_url","")}" class="product-img" onerror="this.style.display=\'none\'">' if p.get("photo_url") else '<div class="product-img" style="background:var(--card2)"></div>'
            dispo = '<span class="status-pill pill-green">Dispo</span>' if p.get("disponible") else '<span class="status-pill pill-red">Indispo</span>'
            rows += f"""<tr>
              <td>{photo}</td>
              <td style="font-weight:600">{p.get('titre','')[:50]}</td>
              <td>{p.get('prix_achat',0):.2f}€</td>
              <td style="color:var(--green);font-weight:600">{prix_vente:.2f}€</td>
              <td style="color:var(--text2)">{p.get('categorie','')}</td>
              <td>{dispo}</td>
              <td class="flex gap-8">
                <button class="btn btn-primary btn-sm" onclick="genererAnnonce({p['id']})">✨ Annonce</button>
                <button class="btn btn-warning btn-sm" onclick="marquerIndispo({p['id']})">⊘ Indispo</button>
                <button class="btn btn-danger btn-sm" onclick="supprimerProduit({p['id']})">🗑</button>
              </td>
            </tr>"""

        pagination = "".join(
            f'<a href="/produits?page={p2}" class="page-btn {"active" if p2==page else ""}">{p2}</a>'
            for p2 in range(1, data["pages"]+1)
        )

        content = f"""
<div class="card mb-16">
  <div class="section-title">Ajouter un produit manuellement</div>
  <div class="grid grid-4 gap-8">
    <div class="input-group"><input class="input-field" id="newTitre" placeholder="Titre du produit"></div>
    <div class="input-group"><input class="input-field" type="number" step="0.01" id="newPrix" placeholder="Prix achat (€)"></div>
    <div class="input-group"><input class="input-field" id="newUrl" placeholder="URL Aliexpress"></div>
    <div class="input-group"><input class="input-field" id="newCat" placeholder="Categorie"></div>
  </div>
  <div class="flex gap-8 mt-8">
    <button class="btn btn-primary" onclick="ajouterProduit()">➕ Ajouter produit</button>
    <button class="btn btn-success" onclick="lancerScraping()">🔍 Lancer scraping maintenant</button>
    <input class="input-field" style="width:280px" id="motsClesScraping" placeholder="Mots-cles (virgule separateur)">
  </div>
</div>
<div class="card">
  <div class="flex-between mb-16">
    <span style="color:var(--text2)">{data['total']} produits en base</span>
  </div>
  <table>
    <tr><th>Photo</th><th>Titre</th><th>Prix achat</th><th>Prix vente</th><th>Categorie</th><th>Statut</th><th>Actions</th></tr>
    {rows or '<tr><td colspan="7" style="text-align:center;color:var(--text2);padding:24px">Aucun produit. Lancer le scraping!</td></tr>'}
  </table>
  <div class="flex-between mt-16">
    <span style="color:var(--text2);font-size:0.8rem">{data['total']} produits</span>
    <div class="pagination">{pagination}</div>
  </div>
</div>
<script>
async function ajouterProduit() {{
  const titre = document.getElementById('newTitre').value;
  const prix = parseFloat(document.getElementById('newPrix').value);
  const url = document.getElementById('newUrl').value;
  const cat = document.getElementById('newCat').value;
  if (!titre||!prix) {{ showToast('Titre et prix requis','error'); return; }}
  const r = await apiCall('/api/produits/ajouter','POST',{{titre,prix,url,categorie:cat}});
  if (r?.ok) {{ showToast('Produit ajoute!','success'); setTimeout(()=>location.reload(),500); }}
  else showToast(r?.error||'Erreur','error');
}}
async function genererAnnonce(id) {{
  const r = await apiCall(`/api/produits/${{id}}/generer-annonce`);
  if (r?.ok) {{ showToast('Annonce generee!','success'); setTimeout(()=>window.location='/annonces',800); }}
  else showToast(r?.error||'Erreur','error');
}}
async function marquerIndispo(id) {{
  confirmAction('Marquer ce produit comme indisponible?', async () => {{
    const r = await apiCall(`/api/produits/${{id}}/indisponible`);
    if (r?.ok) {{ showToast('Produit marque indisponible','info'); setTimeout(()=>location.reload(),500); }}
  }});
}}
async function supprimerProduit(id) {{
  confirmAction('Supprimer ce produit definitivement?', async () => {{
    const r = await apiCall(`/api/produits/${{id}}/supprimer`);
    if (r?.ok) {{ showToast('Produit supprime','info'); setTimeout(()=>location.reload(),500); }}
  }});
}}
async function lancerScraping() {{
  const mots = document.getElementById('motsClesScraping').value;
  const r = await apiCall('/api/bot/scraping/lancer','POST',{{mots_cles:mots}});
  if (r) showToast('Scraping lance!','success');
}}
</script>"""

        return HTMLResponse(base_html("produits", content, "Produits"))
    except Exception as e:
        return HTMLResponse(f"<p>Erreur: {e}</p>", status_code=500)


# ─── PAGE VENTES ──────────────────────────────────────────────────────────────

@app.get("/ventes", response_class=HTMLResponse)
async def page_ventes(filtre: str = "toutes", page: int = 1):
    try:
        data = database.get_toutes_ventes(filtre, page, 20)
        stats = database.get_stats_dashboard()
        ventes = data["items"]

        rows = ""
        for v in ventes:
            statut_cmd = "Commandee" if v.get("commande_ali_passee") else "A commander"
            statut_env = "Envoyee" if v.get("colis_envoye") else ("Prete a envoyer" if v.get("commande_ali_passee") else "En attente")
            pill = "pill-green" if v.get("colis_envoye") else ("pill-orange" if v.get("commande_ali_passee") else "pill-red")
            actions = ""
            if not v.get("commande_ali_passee"):
                ali_url = v.get("url_aliexpress","")
                ali_link = f'<a href="{ali_url}" target="_blank" class="btn btn-ghost btn-sm">🛒 Ali</a>' if ali_url else ""
                actions += f'{ali_link}<button class="btn btn-warning btn-sm" onclick="marquerCommande({v["id"]})">✓ Commandee</button>'
            elif not v.get("colis_envoye"):
                actions += f'<input class="input-field" style="width:120px;display:inline" id="suivi_{v["id"]}" placeholder="N° suivi"><button class="btn btn-success btn-sm" onclick="marquerEnvoye({v["id"]})">📦 Envoye</button>'

            rows += f"""<tr>
              <td style="color:var(--text2);font-size:0.75rem">{v.get('date_vente','')[:10]}</td>
              <td style="font-weight:600">{v.get('titre_vinted','N/A')[:35]}</td>
              <td style="color:var(--green);font-weight:700">{v.get('montant',0):.2f}€</td>
              <td>{v.get('acheteur_nom','N/A')}</td>
              <td><span class="status-pill {pill}">{statut_env}</span></td>
              <td style="color:var(--text2);font-size:0.75rem">{v.get('numero_suivi','—')}</td>
              <td class="flex gap-8">{actions}</td>
            </tr>"""

        filtres_tabs = [("toutes","Toutes"),("a_commander","A commander"),("a_envoyer","A envoyer"),("envoyees","Envoyees")]
        tabs_html = "".join(f'<a href="/ventes?filtre={k}" class="tab {"active" if filtre==k else ""}">{l}</a>' for k,l in filtres_tabs)

        pagination = "".join(
            f'<a href="/ventes?filtre={filtre}&page={p}" class="page-btn {"active" if p==page else ""}">{p}</a>'
            for p in range(1, data["pages"]+1)
        )

        content = f"""
<div class="grid grid-4 mb-16">
  <div class="card"><div class="kpi-value green">{stats["ventes_mois"]}</div><div class="kpi-label">Ventes ce mois</div></div>
  <div class="card"><div class="kpi-value green">{stats["ca_mois"]:.2f}€</div><div class="kpi-label">CA ce mois</div></div>
  <div class="card"><div class="kpi-value orange">{stats["commandes_a_passer"]}</div><div class="kpi-label">A commander</div></div>
  <div class="card"><div class="kpi-value yellow">{stats["colis_a_envoyer"]}</div><div class="kpi-label">A envoyer</div></div>
</div>
<div class="card">
  <div class="flex-between mb-16">
    <div class="tabs" style="border:none;margin:0">{tabs_html}</div>
    <a href="/api/ventes/export-csv" class="btn btn-ghost btn-sm">📥 Export CSV</a>
  </div>
  <table>
    <tr><th>Date</th><th>Produit</th><th>Montant</th><th>Acheteur</th><th>Statut</th><th>Suivi</th><th>Actions</th></tr>
    {rows or '<tr><td colspan="7" style="text-align:center;color:var(--text2);padding:24px">Aucune vente</td></tr>'}
  </table>
  <div class="flex-between mt-16">
    <span style="color:var(--text2);font-size:0.8rem">{data['total']} ventes</span>
    <div class="pagination">{pagination}</div>
  </div>
</div>
<script>
async function marquerCommande(id) {{
  const r = await apiCall(`/api/ventes/${{id}}/commande-passee`);
  if (r?.ok) {{ showToast('Commande marquee!','success'); setTimeout(()=>location.reload(),500); }}
}}
async function marquerEnvoye(id) {{
  const suivi = document.getElementById(`suivi_${{id}}`).value;
  const r = await apiCall(`/api/ventes/${{id}}/colis-envoye`,'POST',{{numero_suivi:suivi}});
  if (r?.ok) {{ showToast('Colis marque envoye!','success'); setTimeout(()=>location.reload(),500); }}
  else showToast(r?.error||'Erreur','error');
}}
</script>"""

        return HTMLResponse(base_html("ventes", content, "Ventes"))
    except Exception as e:
        return HTMLResponse(f"<p>Erreur: {e}</p>", status_code=500)


# ─── PAGE COLIS ───────────────────────────────────────────────────────────────

@app.get("/colis", response_class=HTMLResponse)
async def page_colis():
    try:
        import logistique
        colis = logistique.get_colis_a_preparer()
        historique = logistique.get_historique_envois(30)

        rows_actif = ""
        for c in colis:
            if c.get("colis_envoye"):
                continue
            if not c.get("commande_ali_passee"):
                statut_html = '<span class="status-pill pill-red">A COMMANDER</span>'
                ali_url = c.get("url_aliexpress", "")
                action = f'<a href="{ali_url}" target="_blank" class="btn btn-warning btn-sm">🛒 Commander sur Ali</a><button class="btn btn-success btn-sm" onclick="marquerCommande({c["id"]})">✓ Commande passee</button>'
            else:
                statut_html = '<span class="status-pill pill-orange">A ENVOYER</span>'
                action = f'<input class="input-field" style="width:130px;display:inline" id="suivi_{c["id"]}" placeholder="N° suivi"><button class="btn btn-success btn-sm" onclick="marquerEnvoye({c["id"]})">📦 Marquer envoye</button>'

            rows_actif += f"""<tr>
              <td>{statut_html}</td>
              <td style="font-weight:600">{c.get('titre_vinted','N/A')[:35]}</td>
              <td>{c.get('acheteur_nom','N/A')}</td>
              <td style="font-size:0.8rem;color:var(--text2)">{c.get('adresse_livraison','N/A')[:40]}</td>
              <td style="color:var(--green);font-weight:600">{c.get('montant',0):.2f}€</td>
              <td class="flex gap-8">{action}</td>
            </tr>"""

        rows_histo = ""
        for e in historique:
            rows_histo += f"""<tr>
              <td style="color:var(--text2)">{e.get('date_vente','')[:10]}</td>
              <td>{e.get('titre_vinted','N/A')[:35]}</td>
              <td>{e.get('acheteur_nom','N/A')}</td>
              <td style="color:var(--green)">{e.get('montant',0):.2f}€</td>
              <td style="color:var(--text2)">{e.get('numero_suivi','—')}</td>
            </tr>"""

        content = f"""
<div class="flex-between mb-16">
  <span style="color:var(--text2)">{len(colis)} colis en attente</span>
  <button class="btn btn-primary" onclick="envoyerRecap()">📱 Envoyer recap Telegram</button>
</div>
<div class="card mb-16">
  <div class="section-title">Colis a traiter ({len(colis)})</div>
  <table>
    <tr><th>Statut</th><th>Produit</th><th>Acheteur</th><th>Adresse</th><th>Montant</th><th>Actions</th></tr>
    {rows_actif or '<tr><td colspan="6" style="text-align:center;color:var(--green);padding:24px">Tous les colis sont traites!</td></tr>'}
  </table>
</div>
<div class="card">
  <div class="section-title">Historique des 30 derniers envois</div>
  <table>
    <tr><th>Date</th><th>Produit</th><th>Acheteur</th><th>Montant</th><th>N° Suivi</th></tr>
    {rows_histo or '<tr><td colspan="5" style="text-align:center;color:var(--text2);padding:16px">Aucun envoi</td></tr>'}
  </table>
</div>
<script>
async function marquerCommande(id) {{
  const r = await apiCall(`/api/ventes/${{id}}/commande-passee`);
  if (r?.ok) {{ showToast('Commande passee!','success'); setTimeout(()=>location.reload(),500); }}
}}
async function marquerEnvoye(id) {{
  const suivi = document.getElementById(`suivi_${{id}}`).value;
  const r = await apiCall(`/api/ventes/${{id}}/colis-envoye`,'POST',{{numero_suivi:suivi}});
  if (r?.ok) {{ showToast('Colis envoye!','success'); setTimeout(()=>location.reload(),500); }}
}}
async function envoyerRecap() {{
  const r = await apiCall('/api/bot/recap-colis');
  if (r) showToast('Recap envoye sur Telegram!','success');
}}
</script>"""

        return HTMLResponse(base_html("colis", content, "Colis & Logistique"))
    except Exception as e:
        return HTMLResponse(f"<p>Erreur: {e}</p>", status_code=500)


# ─── PAGE PARAMETRES ──────────────────────────────────────────────────────────

@app.get("/parametres", response_class=HTMLResponse)
async def page_parametres():
    try:
        settings = {s["cle"]: s["valeur"] for s in database.get_all_settings()}

        def chk(key): return "checked" if settings.get(key, "0") == "1" else ""
        def val(key, default=""): return settings.get(key, default)

        content = f"""
<form id="formParams">
<div class="grid grid-2 gap-12">

<div>
<div class="card mb-16">
  <div class="section-title">Bot et automatisation</div>
  <div class="input-group toggle-wrap">
    <label class="toggle"><input type="checkbox" name="bot_actif" {chk("bot_actif")} value="1"><span class="toggle-slider"></span></label>
    <span>Bot principal actif</span>
  </div>
  <div class="input-group toggle-wrap mt-16">
    <label class="toggle"><input type="checkbox" name="posting_actif" {chk("posting_actif")} value="1"><span class="toggle-slider"></span></label>
    <span>Posting automatique</span>
  </div>
  <div class="input-group toggle-wrap mt-16">
    <label class="toggle"><input type="checkbox" name="scraping_actif" {chk("scraping_actif")} value="1"><span class="toggle-slider"></span></label>
    <span>Scraping automatique</span>
  </div>
  <div class="grid grid-2 gap-8 mt-16">
    <div class="input-group"><label class="input-label">Heure posting matin</label><input class="input-field" type="time" name="heure_posting_matin" value="{val("heure_posting_matin","10:00")}"></div>
    <div class="input-group"><label class="input-label">Heure posting soir</label><input class="input-field" type="time" name="heure_posting_soir" value="{val("heure_posting_soir","15:30")}"></div>
    <div class="input-group"><label class="input-label">Heure scraping</label><input class="input-field" type="time" name="heure_scraping" value="{val("heure_scraping","08:00")}"></div>
    <div class="input-group"><label class="input-label">Max annonces/session</label><input class="input-field" type="number" name="max_posts_session" value="{val("max_posts_session","5")}"></div>
    <div class="input-group"><label class="input-label">Delai min entre posts (s)</label><input class="input-field" type="number" name="delai_min_posts" value="{val("delai_min_posts","60")}"></div>
    <div class="input-group"><label class="input-label">Delai max entre posts (s)</label><input class="input-field" type="number" name="delai_max_posts" value="{val("delai_max_posts","300")}"></div>
  </div>
</div>

<div class="card mb-16">
  <div class="section-title">Notifications Telegram</div>
  <div class="input-group toggle-wrap">
    <label class="toggle"><input type="checkbox" name="telegram_alertes_ventes" {chk("telegram_alertes_ventes")} value="1"><span class="toggle-slider"></span></label>
    <span>Alertes nouvelles ventes</span>
  </div>
  <div class="input-group toggle-wrap mt-16">
    <label class="toggle"><input type="checkbox" name="telegram_validation_annonces" {chk("telegram_validation_annonces")} value="1"><span class="toggle-slider"></span></label>
    <span>Validation annonces via Telegram</span>
  </div>
  <div class="input-group toggle-wrap mt-16">
    <label class="toggle"><input type="checkbox" name="recap_colis_quotidien" {chk("recap_colis_quotidien")} value="1"><span class="toggle-slider"></span></label>
    <span>Recap colis quotidien</span>
  </div>
  <div class="mt-16">
    <button type="button" class="btn btn-primary" onclick="testerTelegram()">📱 Envoyer message test</button>
    <button type="button" class="btn btn-ghost" onclick="testerClaude()">🤖 Tester Claude API</button>
  </div>
  <div id="test-result" class="mt-16" style="color:var(--green)"></div>
</div>
</div>

<div>
<div class="card mb-16">
  <div class="section-title">Scraping et produits</div>
  <div class="input-group"><label class="input-label">Mots-cles (un par ligne)</label>
    <textarea class="input-field" name="mots_cles_textarea" rows="6">{chr(10).join(val("mots_cles","").split(","))}</textarea>
  </div>
  <div class="grid grid-2 gap-8">
    <div class="input-group"><label class="input-label">Prix min achat (€)</label><input class="input-field" type="number" step="0.1" name="prix_min_achat" value="{val("prix_min_achat","2.0")}"></div>
    <div class="input-group"><label class="input-label">Prix max achat (€)</label><input class="input-field" type="number" step="0.1" name="prix_max_achat" value="{val("prix_max_achat","12.0")}"></div>
    <div class="input-group"><label class="input-label">Heures avant republication</label><input class="input-field" type="number" name="intervalle_republication" value="{val("intervalle_republication","72")}"></div>
  </div>
</div>

<div class="card mb-16">
  <div class="section-title">Tarification</div>
  <div class="grid grid-3 gap-8">
    <div class="input-group"><label class="input-label">Multiplicateur &lt;=3€</label><input class="input-field" type="number" step="0.1" name="multiplicateur_<=3" value="{val("multiplicateur_<=3","6.0")}"></div>
    <div class="input-group"><label class="input-label">Multiplicateur &lt;=7€</label><input class="input-field" type="number" step="0.1" name="multiplicateur_<=7" value="{val("multiplicateur_<=7","4.5")}"></div>
    <div class="input-group"><label class="input-label">Multiplicateur defaut</label><input class="input-field" type="number" step="0.1" name="multiplicateur_default" value="{val("multiplicateur_default","3.5")}"></div>
  </div>
  <div class="mt-16">
    <div class="input-label">Calculateur live</div>
    <div class="flex gap-8 flex-center">
      <input class="input-field" style="width:120px" type="number" step="0.01" id="calcPrix" placeholder="Prix achat €" oninput="calculerPrix()">
      <span style="color:var(--text2)">→</span>
      <span id="calcResult" style="font-size:1.2rem;font-weight:700;color:var(--green)">—</span>
    </div>
  </div>
</div>

<div class="card mb-16">
  <div class="section-title">Credentials</div>
  <div class="input-group"><label class="input-label">Claude API Key</label>
    <div class="flex gap-8">
      <input class="input-field" type="password" id="claudeKey" value="{val("ANTHROPIC_API_KEY", config.ANTHROPIC_API_KEY)}" placeholder="sk-ant-...">
      <button type="button" class="btn btn-ghost btn-sm" onclick="togglePwd('claudeKey')">👁</button>
    </div>
  </div>
  <div class="input-group"><label class="input-label">Telegram Token</label>
    <div class="flex gap-8">
      <input class="input-field" type="password" id="tgToken" value="{config.TELEGRAM_TOKEN}" placeholder="123456:ABC...">
      <button type="button" class="btn btn-ghost btn-sm" onclick="togglePwd('tgToken')">👁</button>
    </div>
  </div>
  <div class="input-group"><label class="input-label">Telegram Chat ID</label>
    <input class="input-field" id="tgChatId" value="{config.TELEGRAM_CHAT_ID}">
  </div>
  <div class="input-group"><label class="input-label">Vinted Email</label>
    <input class="input-field" id="vintedEmail" value="{config.VINTED_EMAIL}">
  </div>
  <div class="input-group"><label class="input-label">IMAP Email</label>
    <input class="input-field" id="imapEmail" value="{config.IMAP_EMAIL}">
  </div>
  <div class="input-group"><label class="input-label">IMAP Password</label>
    <div class="flex gap-8">
      <input class="input-field" type="password" id="imapPwd" value="{config.IMAP_PASSWORD}">
      <button type="button" class="btn btn-ghost btn-sm" onclick="togglePwd('imapPwd')">👁</button>
    </div>
  </div>
  <button type="button" class="btn btn-warning mt-8" onclick="sauvegarderCredentials()">💾 Sauvegarder credentials dans .env</button>
</div>
</div>

</div>

<div style="text-align:center;margin-top:24px">
  <button type="button" class="btn btn-primary btn-lg" style="padding:14px 40px;font-size:1.1rem" onclick="sauvegarderParams()">
    💾 SAUVEGARDER LES PARAMETRES
  </button>
</div>
</form>

<script>
function togglePwd(id) {{
  const el = document.getElementById(id);
  el.type = el.type === 'password' ? 'text' : 'password';
}}

function calculerPrix() {{
  const p = parseFloat(document.getElementById('calcPrix').value);
  if (!p) {{ document.getElementById('calcResult').textContent = '—'; return; }}
  let m = p <= 3 ? parseFloat(document.querySelector('[name="multiplicateur_<=3"]').value||6)
          : p <= 7 ? parseFloat(document.querySelector('[name="multiplicateur_<=7"]').value||4.5)
          : parseFloat(document.querySelector('[name="multiplicateur_default"]').value||3.5);
  const vente = Math.max((p * m - 0.01).toFixed(2), 1.99);
  document.getElementById('calcResult').textContent = vente + '€';
}}

async function sauvegarderParams() {{
  const form = document.getElementById('formParams');
  const data = {{}};
  form.querySelectorAll('input,textarea,select').forEach(el => {{
    if (!el.name || el.name === 'mots_cles_textarea') return;
    if (el.type === 'checkbox') data[el.name] = el.checked ? '1' : '0';
    else data[el.name] = el.value;
  }});
  // Mots-cles depuis textarea
  const ta = form.querySelector('[name="mots_cles_textarea"]');
  if (ta) data['mots_cles'] = ta.value.split('\\n').map(s=>s.trim()).filter(Boolean).join(',');

  const r = await apiCall('/api/settings/sauvegarder','POST', data);
  if (r?.ok) showToast('Parametres sauvegardes!','success');
  else showToast(r?.error||'Erreur sauvegarde','error');
}}

async function testerTelegram() {{
  const r = await apiCall('/api/settings/tester-telegram');
  const el = document.getElementById('test-result');
  if (r?.ok) {{ el.textContent = 'Telegram: Message envoye!'; el.style.color='var(--green)'; }}
  else {{ el.textContent = 'Telegram: ' + (r?.error||'Erreur'); el.style.color='var(--red)'; }}
}}
async function testerClaude() {{
  const r = await apiCall('/api/settings/tester-claude');
  const el = document.getElementById('test-result');
  if (r?.ok) {{ el.textContent = 'Claude API: OK'; el.style.color='var(--green)'; }}
  else {{ el.textContent = 'Claude API: Cle invalide'; el.style.color='var(--red)'; }}
}}
async function sauvegarderCredentials() {{
  const data = {{
    ANTHROPIC_API_KEY: document.getElementById('claudeKey').value,
    TELEGRAM_TOKEN: document.getElementById('tgToken').value,
    TELEGRAM_CHAT_ID: document.getElementById('tgChatId').value,
    VINTED_EMAIL: document.getElementById('vintedEmail').value,
    IMAP_EMAIL: document.getElementById('imapEmail').value,
    IMAP_PASSWORD: document.getElementById('imapPwd').value,
  }};
  const r = await apiCall('/api/settings/credentials','POST', data);
  if (r?.ok) showToast('Credentials sauvegardes dans .env!','success');
  else showToast(r?.error||'Erreur','error');
}}
</script>"""

        return HTMLResponse(base_html("parametres", content, "Parametres"))
    except Exception as e:
        return HTMLResponse(f"<p>Erreur: {e}</p>", status_code=500)


# ─── PAGE LOGS ────────────────────────────────────────────────────────────────

@app.get("/logs", response_class=HTMLResponse)
async def page_logs(filtre: str = "tous"):
    try:
        logs = database.get_logs_recents(100)
        rows = ""
        for l in logs:
            if filtre != "tous":
                if filtre == "erreurs" and l["statut"] != "erreur": continue
                if filtre == "scraping" and l["type_action"] != "scraping": continue
                if filtre == "posting" and l["type_action"] != "posting": continue
                if filtre == "ventes" and l["type_action"] != "vente": continue
            cls = "log-error" if l["statut"] == "erreur" else "log-info" if l["statut"] == "succes" else "log-debug"
            rows += f'<div><span class="log-time">{l["date_debut"][:16]}</span><span class="{cls}">[{l["type_action"]}:{l["statut"]}] {l["details"][:120]}</span></div>\n'

        filtres_tabs = [("tous","Tous"),("erreurs","Erreurs"),("scraping","Scraping"),("posting","Posting"),("ventes","Ventes")]
        tabs_html = "".join(f'<a href="/logs?filtre={k}" class="tab {"active" if filtre==k else ""}">{l}</a>' for k,l in filtres_tabs)

        content = f"""
<div class="card">
  <div class="flex-between mb-16">
    <div class="tabs" style="border:none;margin:0">{tabs_html}</div>
    <button class="btn btn-danger btn-sm" onclick="effacerLogs()">🗑 Effacer les logs</button>
  </div>
  <div class="terminal" id="terminal" style="max-height:600px">
    {rows or '<span class="log-debug">Aucun log</span>'}
  </div>
</div>
<script>
async function effacerLogs() {{
  confirmAction('Effacer tous les logs?', async () => {{
    const r = await apiCall('/api/logs/effacer');
    if (r?.ok) {{ showToast('Logs effaces','info'); setTimeout(()=>location.reload(),500); }}
  }});
}}
async function refreshLogs() {{
  const r = await fetch('/api/logs?filtre={filtre}').then(x=>x.json()).catch(()=>null);
  if (!r) return;
  const t = document.getElementById('terminal');
  t.innerHTML = r.items.map(l => {{
    const cls = l.statut==='erreur'?'log-error':l.statut==='succes'?'log-info':'log-debug';
    return `<div><span class="log-time">${{l.date_debut?.slice(0,16)||''}}</span><span class="${{cls}}">[{{'${{l.type_action}}'}}:{{'${{l.statut}}'}}] ${{l.details?.slice(0,120)||''}}</span></div>`;
  }}).join('');
}}
setInterval(refreshLogs, 5000);
</script>"""

        return HTMLResponse(base_html("logs", content, "Logs & Activite"))
    except Exception as e:
        return HTMLResponse(f"<p>Erreur: {e}</p>", status_code=500)


# ─── API ROUTES ───────────────────────────────────────────────────────────────

@app.get("/api/stats")
async def api_stats():
    try:
        stats = database.get_stats_dashboard()
        return JSONResponse(stats)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/settings")
async def api_settings():
    try:
        return JSONResponse({"items": database.get_all_settings(), "ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/annonces")
async def api_annonces(statut: str = "toutes", page: int = 1, search: str = ""):
    try:
        data = database.get_toutes_annonces(statut if statut != "toutes" else None, page, 20, search)
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/produits")
async def api_produits(page: int = 1):
    try:
        return JSONResponse(database.get_tous_produits(page, 20))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/ventes")
async def api_ventes(filtre: str = "toutes", page: int = 1):
    try:
        return JSONResponse(database.get_toutes_ventes(filtre, page, 20))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/colis")
async def api_colis():
    try:
        import logistique
        return JSONResponse({"items": logistique.get_colis_a_preparer(), "ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/logs")
async def api_logs(filtre: str = "tous"):
    try:
        logs = database.get_logs_recents(100)
        if filtre == "erreurs":
            logs = [l for l in logs if l["statut"] == "erreur"]
        elif filtre in ("scraping", "posting", "ventes"):
            logs = [l for l in logs if l["type_action"] == filtre]
        return JSONResponse({"items": logs, "ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/logs/effacer")
async def api_effacer_logs():
    try:
        conn = database.get_conn()
        conn.execute("DELETE FROM sessions_bot")
        conn.commit()
        conn.close()
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/status")
async def api_status():
    try:
        import requests as req
        tg_ok = False
        claude_ok = False
        try:
            r = req.get(f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/getMe", timeout=5)
            tg_ok = r.json().get("ok", False)
        except Exception:
            pass
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
            client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=5, messages=[{"role": "user", "content": "hi"}])
            claude_ok = True
        except Exception:
            pass
        return JSONResponse({
            "telegram": tg_ok,
            "claude": claude_ok,
            "bot_actif": BOT_STATUS.get("bot_actif"),
            "posting_en_cours": BOT_STATUS.get("posting_en_cours"),
            "scraping_en_cours": BOT_STATUS.get("scraping_en_cours"),
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── API ACTIONS ANNONCES ─────────────────────────────────────────────────────

@app.post("/api/annonces/{annonce_id}/approuver")
async def api_approuver(annonce_id: int):
    try:
        database.update_statut_annonce(annonce_id, "approuvee")
        add_log(f"Annonce #{annonce_id} approuvee")
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/annonces/{annonce_id}/refuser")
async def api_refuser(annonce_id: int):
    try:
        database.update_statut_annonce(annonce_id, "refusee")
        add_log(f"Annonce #{annonce_id} refusee")
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/annonces/{annonce_id}/modifier")
async def api_modifier(annonce_id: int, request: Request):
    try:
        body = await request.json()
        database.update_annonce(annonce_id, titre=body.get("titre"), description=body.get("description"), prix=body.get("prix"))
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/annonces/approuver-toutes")
async def api_approuver_toutes():
    try:
        annonces = database.get_annonces_en_attente()
        for a in annonces:
            database.update_statut_annonce(a["id"], "approuvee")
        add_log(f"{len(annonces)} annonces approuvees en masse")
        return JSONResponse({"ok": True, "nb": len(annonces)})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/annonces/{annonce_id}/poster")
async def api_poster_annonce(annonce_id: int, background_tasks: BackgroundTasks):
    try:
        annonce = database.get_toutes_annonces(page=1, par_page=1000)
        target = next((a for a in annonce["items"] if a["id"] == annonce_id), None)
        if not target:
            return JSONResponse({"error": "Annonce non trouvee"}, status_code=404)

        def do_post():
            try:
                import asyncio
                import poster_vinted
                database.update_statut_annonce(annonce_id, "en_ligne", f"manual_{annonce_id}")
                add_log(f"Annonce #{annonce_id} marquee en ligne (simulation)")
            except Exception as e:
                add_log(f"Erreur posting annonce #{annonce_id}: {e}", "error")

        background_tasks.add_task(do_post)
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/annonces/{annonce_id}/supprimer")
async def api_supprimer_annonce(annonce_id: int):
    try:
        database.supprimer_annonce(annonce_id)
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/annonces/envoyer-telegram")
async def api_envoyer_telegram():
    try:
        import telegram_bot
        nb = telegram_bot.envoyer_toutes_annonces_en_attente()
        add_log(f"{nb} annonces envoyees sur Telegram")
        return JSONResponse({"ok": True, "nb": nb})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── API ACTIONS PRODUITS ─────────────────────────────────────────────────────

@app.post("/api/produits/ajouter")
async def api_ajouter_produit(request: Request):
    try:
        body = await request.json()
        produit_id = database.sauvegarder_produit(
            titre=body.get("titre", ""),
            prix_achat=float(body.get("prix", 0)),
            url=body.get("url", ""),
            photo_url=body.get("photo_url", ""),
            categorie=body.get("categorie", "Accessoires"),
        )
        add_log(f"Produit #{produit_id} ajoute manuellement")
        return JSONResponse({"ok": True, "id": produit_id})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/produits/{produit_id}/supprimer")
async def api_supprimer_produit(produit_id: int):
    try:
        database.supprimer_produit(produit_id)
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/produits/{produit_id}/generer-annonce")
async def api_generer_annonce(produit_id: int):
    try:
        import generateur
        produit = database.get_produit_par_id(produit_id)
        if not produit:
            return JSONResponse({"error": "Produit non trouve"}, status_code=404)
        annonce = generateur.generer_annonce_ia(produit)
        annonce_id = database.sauvegarder_annonce(
            produit_id=produit_id, titre=annonce["titre_vinted"],
            description=annonce["description"], prix=annonce["prix_vente"],
            categorie=annonce["categorie_vinted"],
        )
        add_log(f"Annonce #{annonce_id} generee pour produit #{produit_id}")
        return JSONResponse({"ok": True, "annonce_id": annonce_id})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/produits/{produit_id}/indisponible")
async def api_produit_indisponible(produit_id: int):
    try:
        database.marquer_produit_indisponible(produit_id)
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── API VENTES ET COLIS ──────────────────────────────────────────────────────

@app.post("/api/ventes/{vente_id}/commande-passee")
async def api_commande_passee(vente_id: int):
    try:
        database.update_commande_passee(vente_id)
        add_log(f"Commande #{vente_id} marquee passee")
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/ventes/{vente_id}/colis-envoye")
async def api_colis_envoye(vente_id: int, request: Request):
    try:
        body = await request.json()
        numero_suivi = body.get("numero_suivi", "")
        database.update_colis_envoye(vente_id, numero_suivi)
        add_log(f"Colis #{vente_id} marque envoye - suivi: {numero_suivi}")
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/ventes/export-csv")
async def api_export_csv():
    try:
        data = database.get_toutes_ventes(page=1, par_page=10000)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Date", "Produit", "Montant", "Acheteur", "Adresse", "Commande", "Envoye", "Suivi"])
        for v in data["items"]:
            writer.writerow([
                v.get("id"), v.get("date_vente", "")[:10], v.get("titre_vinted", ""),
                v.get("montant", 0), v.get("acheteur_nom", ""), v.get("adresse_livraison", ""),
                "Oui" if v.get("commande_ali_passee") else "Non",
                "Oui" if v.get("colis_envoye") else "Non",
                v.get("numero_suivi", ""),
            ])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=ventes_{datetime.now().strftime('%Y%m%d')}.csv"},
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── API BOT ACTIONS ──────────────────────────────────────────────────────────

@app.post("/api/bot/scraping/lancer")
async def api_lancer_scraping(request: Request, background_tasks: BackgroundTasks):
    try:
        if BOT_STATUS.get("scraping_en_cours"):
            return JSONResponse({"ok": False, "message": "Scraping deja en cours"})
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        mots_cles_str = body.get("mots_cles", "")
        mots_cles = [m.strip() for m in mots_cles_str.split(",") if m.strip()] if mots_cles_str else None

        def do_scraping():
            BOT_STATUS["scraping_en_cours"] = True
            try:
                import scraper, generateur
                nb = scraper.scraper_et_sauvegarder(mots_cles)
                nb_ann = generateur.generer_toutes_annonces()
                add_log(f"Scraping OK: {nb} produits, {nb_ann} annonces", "succes")
            except Exception as e:
                add_log(f"Erreur scraping: {e}", "error")
            finally:
                BOT_STATUS["scraping_en_cours"] = False

        background_tasks.add_task(do_scraping)
        return JSONResponse({"ok": True, "message": "Scraping lance"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/bot/posting/lancer")
async def api_lancer_posting(background_tasks: BackgroundTasks):
    try:
        if BOT_STATUS.get("posting_en_cours"):
            return JSONResponse({"ok": False, "message": "Posting deja en cours"})

        def do_posting():
            BOT_STATUS["posting_en_cours"] = True
            try:
                import asyncio, poster_vinted
                nb = asyncio.run(poster_vinted.session_posting())
                add_log(f"Posting OK: {nb} annonces postees", "succes")
            except Exception as e:
                add_log(f"Erreur posting: {e}", "error")
            finally:
                BOT_STATUS["posting_en_cours"] = False

        background_tasks.add_task(do_posting)
        return JSONResponse({"ok": True, "message": "Posting lance"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/bot/audit-stock")
async def api_audit_stock(background_tasks: BackgroundTasks):
    try:
        def do_audit():
            try:
                import stock
                stock.run_audit_stock()
                add_log("Audit stock termine", "succes")
            except Exception as e:
                add_log(f"Erreur audit: {e}", "error")

        background_tasks.add_task(do_audit)
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/bot/recap-colis")
async def api_recap_colis():
    try:
        import logistique
        ok = logistique.envoyer_recap_telegram()
        add_log("Recap colis envoye sur Telegram")
        return JSONResponse({"ok": ok})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/bot/toggle")
async def api_bot_toggle(request: Request):
    try:
        body = await request.json()
        actif = body.get("actif", True)
        valeur = "1" if actif else "0"
        database.update_setting("bot_actif", valeur)
        BOT_STATUS["bot_actif"] = actif
        add_log(f"Bot {'active' if actif else 'mis en pause'}")
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/bot/posting/toggle")
async def api_posting_toggle(request: Request):
    try:
        body = await request.json()
        actif = body.get("actif", True)
        database.update_setting("posting_actif", "1" if actif else "0")
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── API SETTINGS ─────────────────────────────────────────────────────────────

@app.post("/api/settings/sauvegarder")
async def api_sauvegarder_settings(request: Request):
    try:
        body = await request.json()
        for cle, valeur in body.items():
            database.update_setting(cle, str(valeur))
        add_log(f"{len(body)} parametres mis a jour")
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/settings/tester-telegram")
async def api_tester_telegram():
    try:
        import telegram_bot
        ok = telegram_bot.envoyer_message_sync("Test depuis le dashboard Bot Vinted - connexion OK!")
        return JSONResponse({"ok": ok, "error": None if ok else "Chat non trouve ou token invalide"})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/settings/tester-claude")
async def api_tester_claude():
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=5,
            messages=[{"role": "user", "content": "test"}]
        )
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/settings/tester-imap")
async def api_tester_imap():
    try:
        import imaplib
        m = imaplib.IMAP4_SSL(config.IMAP_SERVER, 993)
        m.login(config.IMAP_EMAIL, config.IMAP_PASSWORD)
        m.logout()
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/settings/credentials")
async def api_sauvegarder_credentials(request: Request):
    try:
        body = await request.json()
        env_lines = []
        if os.path.exists(".env"):
            with open(".env", "r") as f:
                env_lines = f.readlines()

        env_dict = {}
        for line in env_lines:
            if "=" in line and not line.startswith("#"):
                k, _, v = line.strip().partition("=")
                env_dict[k.strip()] = v.strip()

        key_map = {
            "ANTHROPIC_API_KEY": body.get("ANTHROPIC_API_KEY"),
            "TELEGRAM_TOKEN": body.get("TELEGRAM_TOKEN"),
            "TELEGRAM_CHAT_ID": body.get("TELEGRAM_CHAT_ID"),
            "VINTED_EMAIL": body.get("VINTED_EMAIL"),
            "IMAP_EMAIL": body.get("IMAP_EMAIL"),
            "IMAP_PASSWORD": body.get("IMAP_PASSWORD"),
        }
        for k, v in key_map.items():
            if v:
                env_dict[k] = v

        with open(".env", "w") as f:
            for k, v in env_dict.items():
                f.write(f"{k}={v}\n")

        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


if __name__ == "__main__":
    database.init_db()
    print("Dashboard demarre sur http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning", reload=False)
