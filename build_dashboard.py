#!/usr/bin/env python3
"""
Meta Ads Dashboard Builder for Los Lagos Condominio
Reads JSON data files and generates a self-contained HTML dashboard.
"""

import json
import os
import csv
import subprocess
import sys
from datetime import datetime
from collections import defaultdict

# ── File paths ──────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CAMPAIGN_FILE = os.path.expanduser(
    "~/.claude/projects/-Users-global-Desktop-Meta-Ads/"
    "b503a204-759d-45db-8517-6d1399e45c9a/tool-results/b5297eb.txt"
)
DAILY_FILE = os.path.join(SCRIPT_DIR, "daily_insights.json")
ADSET_FILE = os.path.join(SCRIPT_DIR, "adset_insights.json")
VENTAS_FILE = os.path.join(SCRIPT_DIR, "ventas_2026.csv")
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "dashboard.html")

# ── Helpers ─────────────────────────────────────────────────────────────────

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_action_value(actions, action_type):
    """Extract a numeric value from the actions list."""
    if not actions:
        return 0
    for a in actions:
        if a["action_type"] == action_type:
            return float(a["value"])
    return 0


def get_cost_per_action(cost_list, action_type):
    if not cost_list:
        return 0
    for a in cost_list:
        if a["action_type"] == action_type:
            return float(a["value"])
    return 0


def fmt_cop(val):
    """Format as COP currency string."""
    if val >= 1_000_000:
        return f"${val:,.0f}".replace(",", ".")
    return f"${val:,.0f}".replace(",", ".")


def infer_objective(campaign_name):
    """Infer campaign objective from naming convention."""
    name_upper = campaign_name.upper()
    if "TRAF" in name_upper:
        return "TRAFFIC"
    if "RECON" in name_upper or "MENSAJES" in name_upper:
        return "AWARENESS"
    if "FORM" in name_upper or "LEAD" in name_upper:
        return "LEADS"
    return "OTHER"


# ── Auto-sync ventas from Google Sheet ──────────────────────────────────────
print("Syncing ventas from Google Sheet...")
try:
    subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "sync_ventas.py")],
                   check=True, cwd=SCRIPT_DIR)
except Exception as e:
    print(f"Warning: Could not sync ventas: {e}")


def parse_cop_value(val):
    """Parse COP from Sheet format: $45.626.500 -> 45626500"""
    s = val.strip().replace('$', '').replace('.', '').replace(',', '.')
    try:
        return float(s)
    except:
        return 0


def load_ventas(path):
    """Load and process ventas CSV from Google Sheet."""
    if not os.path.exists(path):
        print(f"Warning: {path} not found. Run sync_ventas.py first.")
        return []
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = []
        for r in reader:
            if len(r) < 13 or not r[0].strip():
                continue
            rows.append({
                'mes': r[0].strip(),
                'nombre': r[1].strip(),
                'asesor': r[2].strip(),
                'lote': r[3].strip(),
                'dia_contacto': r[4].strip(),
                'dia_cierre': r[5].strip(),
                'dias_cierre': int(r[6].strip()) if r[6].strip().isdigit() else None,
                'fuente': r[7].strip(),
                'campana': r[8].strip(),
                'conjunto': r[9].strip(),
                'anuncio': r[10].strip(),
                'tipo_campana': r[11].strip(),
                'precio': parse_cop_value(r[12]),
            })
    return rows


# ── Load data ───────────────────────────────────────────────────────────────
print("Loading data files...")
campaign_raw = load_json(CAMPAIGN_FILE)
daily_raw = load_json(DAILY_FILE)
adset_raw = load_json(ADSET_FILE)
ventas_raw = load_ventas(VENTAS_FILE)

# ── Process campaign-level (30-day aggregate) ───────────────────────────────
campaigns = []
for c in campaign_raw["data"]:
    # The campaign file has one entry per campaign for the 30-day window
    impressions = int(c.get("impressions", 0))
    clicks = int(c.get("clicks", 0))
    spend = float(c.get("spend", 0))
    cpc = float(c.get("cpc", 0))
    cpm = float(c.get("cpm", 0))
    ctr = float(c.get("ctr", 0))
    reach = int(c.get("reach", 0))
    frequency = float(c.get("frequency", 0))

    actions = c.get("actions", [])
    cost_actions = c.get("cost_per_action_type", [])

    leads = get_action_value(actions, "lead")
    link_clicks = get_action_value(actions, "link_click")
    landing_page_views = get_action_value(actions, "landing_page_view")
    video_views = get_action_value(actions, "video_view")
    post_engagement = get_action_value(actions, "post_engagement")
    messaging = get_action_value(actions, "onsite_conversion.total_messaging_connection")

    cpl = get_cost_per_action(cost_actions, "lead")
    if cpl == 0 and leads > 0:
        cpl = spend / leads

    objective = infer_objective(c["campaign_name"])

    campaigns.append({
        "name": c["campaign_name"],
        "id": c["campaign_id"],
        "impressions": impressions,
        "clicks": clicks,
        "spend": spend,
        "cpc": cpc,
        "cpm": cpm,
        "ctr": ctr,
        "reach": reach,
        "frequency": frequency,
        "leads": int(leads),
        "link_clicks": int(link_clicks),
        "landing_page_views": int(landing_page_views),
        "video_views": int(video_views),
        "post_engagement": int(post_engagement),
        "messaging": int(messaging),
        "cpl": cpl,
        "objective": objective,
    })

# Sort by spend desc
campaigns.sort(key=lambda x: x["spend"], reverse=True)

# ── Compute account-level KPIs ──────────────────────────────────────────────
total_spend = sum(c["spend"] for c in campaigns)
total_impressions = sum(c["impressions"] for c in campaigns)
total_clicks = sum(c["clicks"] for c in campaigns)
total_reach = sum(c["reach"] for c in campaigns)
total_leads = sum(c["leads"] for c in campaigns)
total_link_clicks = sum(c["link_clicks"] for c in campaigns)
total_landing_views = sum(c["landing_page_views"] for c in campaigns)
total_video_views = sum(c["video_views"] for c in campaigns)
total_engagement = sum(c["post_engagement"] for c in campaigns)
total_messaging = sum(c["messaging"] for c in campaigns)

avg_ctr = (total_clicks / total_impressions * 100) if total_impressions else 0
avg_cpm = (total_spend / total_impressions * 1000) if total_impressions else 0
avg_cpl = (total_spend / total_leads) if total_leads else 0

# ── Process daily insights ──────────────────────────────────────────────────
# Daily data has one entry per campaign per day
daily_agg = defaultdict(lambda: {
    "spend": 0, "impressions": 0, "clicks": 0, "leads": 0,
    "link_clicks": 0, "video_views": 0, "reach": 0
})

for row in daily_raw["data"]:
    date = row["date_start"]
    daily_agg[date]["spend"] += float(row.get("spend", 0))
    daily_agg[date]["impressions"] += int(row.get("impressions", 0))
    daily_agg[date]["clicks"] += int(row.get("clicks", 0))
    daily_agg[date]["reach"] += int(row.get("reach", 0))

    actions = row.get("actions", [])
    daily_agg[date]["leads"] += int(get_action_value(actions, "lead"))
    daily_agg[date]["link_clicks"] += int(get_action_value(actions, "link_click"))
    daily_agg[date]["video_views"] += int(get_action_value(actions, "video_view"))

# Sort by date
daily_dates = sorted(daily_agg.keys())
daily_spend = [daily_agg[d]["spend"] for d in daily_dates]
daily_leads = [daily_agg[d]["leads"] for d in daily_dates]
daily_impressions = [daily_agg[d]["impressions"] for d in daily_dates]
daily_clicks = [daily_agg[d]["clicks"] for d in daily_dates]
daily_cpl = []
daily_ctr = []
daily_cpm = []
for d in daily_dates:
    imp = daily_agg[d]["impressions"]
    cl = daily_agg[d]["clicks"]
    sp = daily_agg[d]["spend"]
    ld = daily_agg[d]["leads"]
    daily_cpl.append(round(sp / ld, 0) if ld > 0 else 0)
    daily_ctr.append(round(cl / imp * 100, 2) if imp > 0 else 0)
    daily_cpm.append(round(sp / imp * 1000, 0) if imp > 0 else 0)

# Format dates for display (DD/MM)
daily_labels = []
for d in daily_dates:
    parts = d.split("-")
    daily_labels.append(f"{parts[2]}/{parts[1]}")

# ── Process ad set data ─────────────────────────────────────────────────────
adsets = []
for a in adset_raw["data"]:
    impressions = int(a.get("impressions", 0))
    clicks = int(a.get("clicks", 0))
    spend = float(a.get("spend", 0))
    cpc = float(a.get("cpc", 0))
    cpm = float(a.get("cpm", 0))
    ctr = float(a.get("ctr", 0))
    reach = int(a.get("reach", 0))
    frequency = float(a.get("frequency", 0))

    actions = a.get("actions", [])
    cost_actions = a.get("cost_per_action_type", [])

    leads = get_action_value(actions, "lead")
    link_clicks = get_action_value(actions, "link_click")
    video_views = get_action_value(actions, "video_view")
    post_engagement = get_action_value(actions, "post_engagement")

    cpl = get_cost_per_action(cost_actions, "lead")
    if cpl == 0 and leads > 0:
        cpl = spend / leads

    adsets.append({
        "campaign_name": a.get("campaign_name", ""),
        "name": a.get("adset_name", ""),
        "id": a.get("adset_id", ""),
        "impressions": impressions,
        "clicks": clicks,
        "spend": spend,
        "cpc": cpc,
        "cpm": cpm,
        "ctr": ctr,
        "reach": reach,
        "frequency": frequency,
        "leads": int(leads),
        "link_clicks": int(link_clicks),
        "video_views": int(video_views),
        "post_engagement": int(post_engagement),
        "cpl": cpl,
    })

adsets.sort(key=lambda x: x["spend"], reverse=True)

# ── Process Ventas Data ─────────────────────────────────────────────────────
print("Processing ventas data...")

# All ventas
ventas_total_count = len(ventas_raw)
ventas_total_revenue = sum(v['precio'] for v in ventas_raw)

# By source
ventas_by_source = defaultdict(lambda: {'count': 0, 'revenue': 0})
for v in ventas_raw:
    src = v['fuente']
    if src:
        ventas_by_source[src]['count'] += 1
        ventas_by_source[src]['revenue'] += v['precio']

# META ventas only
meta_ventas = [v for v in ventas_raw if v['fuente'] == 'META']
meta_ventas_count = len(meta_ventas)
meta_ventas_revenue = sum(v['precio'] for v in meta_ventas)
meta_avg_ticket = meta_ventas_revenue / meta_ventas_count if meta_ventas_count else 0

# Days to close (META only)
meta_dias = [v['dias_cierre'] for v in meta_ventas if v['dias_cierre'] is not None]
meta_avg_dias = sum(meta_dias) / len(meta_dias) if meta_dias else 0
meta_median_dias = sorted(meta_dias)[len(meta_dias)//2] if meta_dias else 0

# ROAS calculation: META revenue / META Ads spend
roas = meta_ventas_revenue / total_spend if total_spend > 0 else 0

# By month
ventas_by_month = defaultdict(lambda: {'total': 0, 'revenue': 0, 'meta': 0, 'meta_revenue': 0})
for v in ventas_raw:
    m = v['mes']
    ventas_by_month[m]['total'] += 1
    ventas_by_month[m]['revenue'] += v['precio']
    if v['fuente'] == 'META':
        ventas_by_month[m]['meta'] += 1
        ventas_by_month[m]['meta_revenue'] += v['precio']

# Top campaigns by sales (normalize name for matching)
def normalize_camp_name(name):
    return name.strip().lower().replace('  ', ' ')

meta_ventas_by_campaign = defaultdict(lambda: {'count': 0, 'revenue': 0})
for v in meta_ventas:
    cn = normalize_camp_name(v['campana'])
    if cn:
        meta_ventas_by_campaign[cn]['count'] += 1
        meta_ventas_by_campaign[cn]['revenue'] += v['precio']

# Top asesores
meta_ventas_by_asesor = defaultdict(lambda: {'count': 0, 'revenue': 0})
for v in meta_ventas:
    name = v['nombre']
    if name and name != 'INMOBILIARIA':
        meta_ventas_by_asesor[name]['count'] += 1
        meta_ventas_by_asesor[name]['revenue'] += v['precio']

# Top creativos (anuncios)
meta_ventas_by_creative = defaultdict(lambda: {'count': 0, 'revenue': 0})
for v in meta_ventas:
    ad = v['anuncio']
    if ad:
        meta_ventas_by_creative[ad]['count'] += 1
        meta_ventas_by_creative[ad]['revenue'] += v['precio']

# Cross-reference: campaign spend vs revenue (ROAS per campaign)
campaign_roas = []
for c in campaigns:
    cn = normalize_camp_name(c['name'])
    vdata = meta_ventas_by_campaign.get(cn, {'count': 0, 'revenue': 0})
    camp_roas = vdata['revenue'] / c['spend'] if c['spend'] > 0 else 0
    campaign_roas.append({
        'name': c['name'],
        'spend': c['spend'],
        'leads': c['leads'],
        'ventas': vdata['count'],
        'revenue': vdata['revenue'],
        'roas': camp_roas,
        'conversion_rate': (vdata['count'] / c['leads'] * 100) if c['leads'] > 0 else 0,
        'cost_per_sale': c['spend'] / vdata['count'] if vdata['count'] > 0 else 0,
    })

campaign_roas.sort(key=lambda x: x['revenue'], reverse=True)

# Source chart data
source_labels = []
source_counts = []
source_revenues = []
for src, data in sorted(ventas_by_source.items(), key=lambda x: -x[1]['revenue']):
    source_labels.append(src)
    source_counts.append(data['count'])
    source_revenues.append(data['revenue'])

print(f"  Ventas totales: {ventas_total_count}")
print(f"  Ventas META: {meta_ventas_count}")
print(f"  Revenue META: ${meta_ventas_revenue:,.0f} COP")
print(f"  ROAS META: {roas:.1f}x")

# ── Objective distribution (spend) ──────────────────────────────────────────
obj_spend = defaultdict(float)
for c in campaigns:
    obj_spend[c["objective"]] += c["spend"]

obj_labels = list(obj_spend.keys())
obj_values = [obj_spend[k] for k in obj_labels]

# Spanish labels for objectives
obj_labels_es = []
for o in obj_labels:
    if o == "LEADS":
        obj_labels_es.append("Leads / Formularios")
    elif o == "TRAFFIC":
        obj_labels_es.append("Trafico")
    elif o == "AWARENESS":
        obj_labels_es.append("Reconocimiento")
    else:
        obj_labels_es.append("Otro")

# ── Top & Bottom performers by CPL (only campaigns with leads) ──────────────
lead_campaigns = [c for c in campaigns if c["leads"] > 0 and c["cpl"] > 0]
lead_campaigns_sorted = sorted(lead_campaigns, key=lambda x: x["cpl"])
top_performers = lead_campaigns_sorted[:3]
bottom_performers = lead_campaigns_sorted[-3:]
bottom_performers.reverse()

# ── Build campaign table rows ───────────────────────────────────────────────
def build_campaign_rows():
    rows = []
    # Compute CPL range for color coding
    cpls = [c["cpl"] for c in campaigns if c["cpl"] > 0]
    min_cpl = min(cpls) if cpls else 0
    max_cpl = max(cpls) if cpls else 1

    for c in campaigns:
        cpl_class = ""
        if c["cpl"] > 0:
            ratio = (c["cpl"] - min_cpl) / (max_cpl - min_cpl) if max_cpl != min_cpl else 0.5
            if ratio < 0.33:
                cpl_class = "cpl-low"
            elif ratio < 0.66:
                cpl_class = "cpl-mid"
            else:
                cpl_class = "cpl-high"

        obj_badge = ""
        if c["objective"] == "LEADS":
            obj_badge = '<span class="badge badge-leads">Leads</span>'
        elif c["objective"] == "TRAFFIC":
            obj_badge = '<span class="badge badge-traffic">Trafico</span>'
        elif c["objective"] == "AWARENESS":
            obj_badge = '<span class="badge badge-awareness">Awareness</span>'
        else:
            obj_badge = '<span class="badge badge-other">Otro</span>'

        cpl_display = f'${c["cpl"]:,.0f}'.replace(",", ".") if c["cpl"] > 0 else "-"
        spend_display = f'${c["spend"]:,.0f}'.replace(",", ".")
        cpm_display = f'${c["cpm"]:,.0f}'.replace(",", ".")

        rows.append(f"""<tr>
            <td class="campaign-name">{c['name']} {obj_badge}</td>
            <td class="num">{spend_display}</td>
            <td class="num">{c['impressions']:,}</td>
            <td class="num">{c['clicks']:,}</td>
            <td class="num">{c['ctr']:.2f}%</td>
            <td class="num">{c['leads']}</td>
            <td class="num {cpl_class}">{cpl_display}</td>
            <td class="num">{c['link_clicks']:,}</td>
            <td class="num">{c['video_views']:,}</td>
        </tr>""")
    return "\n".join(rows)


def build_adset_rows():
    rows = []
    cpls = [a["cpl"] for a in adsets if a["cpl"] > 0]
    min_cpl = min(cpls) if cpls else 0
    max_cpl = max(cpls) if cpls else 1

    for a in adsets:
        cpl_class = ""
        if a["cpl"] > 0:
            ratio = (a["cpl"] - min_cpl) / (max_cpl - min_cpl) if max_cpl != min_cpl else 0.5
            if ratio < 0.33:
                cpl_class = "cpl-low"
            elif ratio < 0.66:
                cpl_class = "cpl-mid"
            else:
                cpl_class = "cpl-high"

        cpl_display = f'${a["cpl"]:,.0f}'.replace(",", ".") if a["cpl"] > 0 else "-"
        spend_display = f'${a["spend"]:,.0f}'.replace(",", ".")

        rows.append(f"""<tr>
            <td class="campaign-name">{a['campaign_name']}</td>
            <td class="adset-name">{a['name']}</td>
            <td class="num">{spend_display}</td>
            <td class="num">{a['impressions']:,}</td>
            <td class="num">{a['clicks']:,}</td>
            <td class="num">{a['ctr']:.2f}%</td>
            <td class="num">{a['leads']}</td>
            <td class="num {cpl_class}">{cpl_display}</td>
            <td class="num">{a['link_clicks']:,}</td>
            <td class="num">{a['video_views']:,}</td>
        </tr>""")
    return "\n".join(rows)


def build_ventas_source_rows():
    """Build rows for the source attribution table."""
    rows = []
    for src, data in sorted(ventas_by_source.items(), key=lambda x: -x[1]['revenue']):
        pct_count = (data['count'] / ventas_total_count * 100) if ventas_total_count else 0
        pct_rev = (data['revenue'] / ventas_total_revenue * 100) if ventas_total_revenue else 0
        rev_display = f"${data['revenue']:,.0f}".replace(",", ".")
        color = '#4361ee' if src == 'META' else '#8892b0'
        rows.append(f"""<tr>
            <td style="font-weight:600; color:{color}">{src}</td>
            <td class="num">{data['count']}</td>
            <td class="num">{pct_count:.1f}%</td>
            <td class="num">{rev_display}</td>
            <td class="num">{pct_rev:.1f}%</td>
        </tr>""")
    return "\n".join(rows)


def build_campaign_roas_rows():
    """Build rows for the campaign ROAS cross-reference table."""
    rows = []
    for cr in campaign_roas:
        if cr['spend'] == 0:
            continue
        spend_d = f"${cr['spend']:,.0f}".replace(",", ".")
        rev_d = f"${cr['revenue']:,.0f}".replace(",", ".") if cr['revenue'] > 0 else "-"
        roas_d = f"{cr['roas']:.1f}x" if cr['roas'] > 0 else "-"
        conv_d = f"{cr['conversion_rate']:.1f}%" if cr['conversion_rate'] > 0 else "-"
        cps_d = f"${cr['cost_per_sale']:,.0f}".replace(",", ".") if cr['cost_per_sale'] > 0 else "-"
        
        roas_class = ""
        if cr['roas'] >= 5:
            roas_class = "cpl-low"
        elif cr['roas'] >= 2:
            roas_class = "cpl-mid"
        elif cr['roas'] > 0:
            roas_class = "cpl-high"
        
        rows.append(f"""<tr>
            <td class="campaign-name">{cr['name']}</td>
            <td class="num">{spend_d}</td>
            <td class="num">{cr['leads']}</td>
            <td class="num" style="font-weight:700">{cr['ventas']}</td>
            <td class="num">{conv_d}</td>
            <td class="num">{rev_d}</td>
            <td class="num {roas_class}" style="font-weight:700">{roas_d}</td>
            <td class="num">{cps_d}</td>
        </tr>""")
    return "\n".join(rows)


def build_asesor_rows():
    """Build rows for asesores table."""
    rows = []
    for name, data in sorted(meta_ventas_by_asesor.items(), key=lambda x: -x[1]['revenue']):
        rev_d = f"${data['revenue']:,.0f}".replace(",", ".")
        avg_d = f"${data['revenue']/data['count']:,.0f}".replace(",", ".") if data['count'] else "-"
        rows.append(f"""<tr>
            <td style="font-weight:600">{name}</td>
            <td class="num">{data['count']}</td>
            <td class="num">{rev_d}</td>
            <td class="num">{avg_d}</td>
        </tr>""")
    return "\n".join(rows)


def build_creative_ventas_rows():
    """Build rows for creative performance by actual sales."""
    rows = []
    for ad, data in sorted(meta_ventas_by_creative.items(), key=lambda x: -x[1]['count'])[:12]:
        rev_d = f"${data['revenue']:,.0f}".replace(",", ".")
        rows.append(f"""<tr>
            <td style="font-weight:600">{ad}</td>
            <td class="num">{data['count']}</td>
            <td class="num">{rev_d}</td>
        </tr>""")
    return "\n".join(rows)


def build_performer_cards(performers, is_top=True):
    cards = []
    for i, c in enumerate(performers):
        rank = i + 1
        icon = "&#9650;" if is_top else "&#9660;"
        color = "#00d4aa" if is_top else "#ff6b6b"
        cpl_display = f'${c["cpl"]:,.0f}'.replace(",", ".")
        spend_display = f'${c["spend"]:,.0f}'.replace(",", ".")

        cards.append(f"""
        <div class="performer-card" style="border-left: 4px solid {color}">
            <div class="performer-rank" style="color: {color}">{icon} #{rank}</div>
            <div class="performer-name">{c['name']}</div>
            <div class="performer-stats">
                <div class="performer-stat">
                    <span class="stat-label">CPL</span>
                    <span class="stat-value" style="color: {color}">{cpl_display}</span>
                </div>
                <div class="performer-stat">
                    <span class="stat-label">Leads</span>
                    <span class="stat-value">{c['leads']}</span>
                </div>
                <div class="performer-stat">
                    <span class="stat-label">Inversion</span>
                    <span class="stat-value">{spend_display}</span>
                </div>
            </div>
        </div>
        """)
    return "\n".join(cards)


# ── Generate HTML ───────────────────────────────────────────────────────────
now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Los Lagos Condominio - Dashboard Meta Ads</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
/* ── RESET & BASE ─────────────────────────────────────── */
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

:root {{
    --bg-dark: #0f0f1a;
    --bg-card: #16213e;
    --bg-card-alt: #1a1a2e;
    --bg-table-header: #0e1628;
    --bg-table-row-hover: #1e2d4f;
    --accent-blue: #4361ee;
    --accent-purple: #7b2ff7;
    --accent-cyan: #00d4aa;
    --accent-pink: #ff6b9d;
    --accent-orange: #ff9f43;
    --accent-red: #ff6b6b;
    --text-primary: #e8e8f0;
    --text-secondary: #8892b0;
    --text-muted: #5a6380;
    --border-color: #2a2a4a;
    --gradient-1: linear-gradient(135deg, #4361ee 0%, #7b2ff7 100%);
    --gradient-2: linear-gradient(135deg, #00d4aa 0%, #4361ee 100%);
    --gradient-3: linear-gradient(135deg, #ff6b9d 0%, #ff9f43 100%);
    --gradient-4: linear-gradient(135deg, #7b2ff7 0%, #ff6b9d 100%);
    --shadow: 0 4px 24px rgba(0,0,0,0.3);
    --shadow-lg: 0 8px 40px rgba(0,0,0,0.4);
}}

body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    background: var(--bg-dark);
    color: var(--text-primary);
    line-height: 1.6;
    min-height: 100vh;
}}

/* ── ANIMATIONS ───────────────────────────────────────── */
@keyframes fadeInUp {{
    from {{ opacity: 0; transform: translateY(30px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}
@keyframes fadeIn {{
    from {{ opacity: 0; }}
    to {{ opacity: 1; }}
}}
@keyframes slideInLeft {{
    from {{ opacity: 0; transform: translateX(-30px); }}
    to {{ opacity: 1; transform: translateX(0); }}
}}
@keyframes pulse {{
    0%, 100% {{ transform: scale(1); }}
    50% {{ transform: scale(1.05); }}
}}
@keyframes shimmer {{
    0% {{ background-position: -200% 0; }}
    100% {{ background-position: 200% 0; }}
}}

.animate-in {{
    animation: fadeInUp 0.6s ease forwards;
    opacity: 0;
}}
.animate-in:nth-child(1) {{ animation-delay: 0.05s; }}
.animate-in:nth-child(2) {{ animation-delay: 0.1s; }}
.animate-in:nth-child(3) {{ animation-delay: 0.15s; }}
.animate-in:nth-child(4) {{ animation-delay: 0.2s; }}
.animate-in:nth-child(5) {{ animation-delay: 0.25s; }}
.animate-in:nth-child(6) {{ animation-delay: 0.3s; }}
.animate-in:nth-child(7) {{ animation-delay: 0.35s; }}
.animate-in:nth-child(8) {{ animation-delay: 0.4s; }}

/* ── LAYOUT ───────────────────────────────────────────── */
.container {{
    max-width: 1600px;
    margin: 0 auto;
    padding: 20px 24px 60px;
}}

/* ── HEADER ───────────────────────────────────────────── */
.header {{
    background: linear-gradient(135deg, #16213e 0%, #1a1a2e 50%, #0f0f1a 100%);
    border-bottom: 1px solid var(--border-color);
    padding: 28px 0;
    margin-bottom: 32px;
    animation: fadeIn 0.8s ease;
    position: relative;
    overflow: hidden;
}}
.header::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: var(--gradient-1);
}}
.header-content {{
    max-width: 1600px;
    margin: 0 auto;
    padding: 0 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 16px;
}}
.header-left h1 {{
    font-size: 28px;
    font-weight: 700;
    background: var(--gradient-1);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.5px;
}}
.header-left .subtitle {{
    color: var(--text-secondary);
    font-size: 14px;
    margin-top: 4px;
}}
.header-right {{
    text-align: right;
}}
.header-right .date-range {{
    color: var(--text-primary);
    font-size: 15px;
    font-weight: 600;
}}
.header-right .updated {{
    color: var(--text-muted);
    font-size: 12px;
    margin-top: 2px;
}}
.account-id {{
    display: inline-block;
    background: rgba(67, 97, 238, 0.15);
    color: var(--accent-blue);
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-family: monospace;
    margin-top: 6px;
}}

/* ── KPI CARDS ────────────────────────────────────────── */
.kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 32px;
}}
.kpi-card {{
    background: var(--bg-card);
    border-radius: 16px;
    padding: 24px 20px;
    position: relative;
    overflow: hidden;
    box-shadow: var(--shadow);
    transition: transform 0.3s ease, box-shadow 0.3s ease;
    border: 1px solid var(--border-color);
}}
.kpi-card:hover {{
    transform: translateY(-4px);
    box-shadow: var(--shadow-lg);
}}
.kpi-card::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    border-radius: 16px 16px 0 0;
}}
.kpi-card:nth-child(1)::before {{ background: var(--gradient-1); }}
.kpi-card:nth-child(2)::before {{ background: var(--gradient-2); }}
.kpi-card:nth-child(3)::before {{ background: var(--gradient-3); }}
.kpi-card:nth-child(4)::before {{ background: linear-gradient(135deg, #4361ee, #00d4aa); }}
.kpi-card:nth-child(5)::before {{ background: linear-gradient(135deg, #ff9f43, #ff6b9d); }}
.kpi-card:nth-child(6)::before {{ background: var(--gradient-4); }}
.kpi-card:nth-child(7)::before {{ background: linear-gradient(135deg, #00d4aa, #7b2ff7); }}
.kpi-card:nth-child(8)::before {{ background: linear-gradient(135deg, #ff6b6b, #ff9f43); }}
.kpi-icon {{
    font-size: 28px;
    margin-bottom: 8px;
    display: block;
}}
.kpi-label {{
    color: var(--text-secondary);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
    font-weight: 600;
}}
.kpi-value {{
    font-size: 26px;
    font-weight: 800;
    margin-top: 6px;
    color: var(--text-primary);
    letter-spacing: -0.5px;
}}
.kpi-sub {{
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 4px;
}}

/* ── SECTION ──────────────────────────────────────────── */
.section {{
    margin-bottom: 36px;
    animation: fadeInUp 0.6s ease forwards;
}}
.section-title {{
    font-size: 20px;
    font-weight: 700;
    margin-bottom: 18px;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 10px;
}}
.section-title .icon {{
    font-size: 22px;
}}

/* ── CHART CONTAINERS ─────────────────────────────────── */
.chart-container {{
    background: var(--bg-card);
    border-radius: 16px;
    padding: 24px;
    box-shadow: var(--shadow);
    border: 1px solid var(--border-color);
}}
.chart-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    margin-bottom: 32px;
}}
.chart-grid-3 {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 24px;
    margin-bottom: 32px;
}}
.chart-full {{
    margin-bottom: 32px;
}}

/* ── TABLES ───────────────────────────────────────────── */
.table-wrapper {{
    background: var(--bg-card);
    border-radius: 16px;
    overflow: hidden;
    box-shadow: var(--shadow);
    border: 1px solid var(--border-color);
    margin-bottom: 32px;
}}
.table-scroll {{
    overflow-x: auto;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}}
thead th {{
    background: var(--bg-table-header);
    color: var(--text-secondary);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-size: 11px;
    padding: 14px 16px;
    text-align: left;
    white-space: nowrap;
    cursor: pointer;
    user-select: none;
    border-bottom: 2px solid var(--border-color);
    position: sticky;
    top: 0;
    z-index: 1;
    transition: background 0.2s;
}}
thead th:hover {{
    background: #141d35;
    color: var(--accent-blue);
}}
thead th .sort-icon {{
    margin-left: 4px;
    opacity: 0.4;
    font-size: 10px;
}}
thead th.sorted .sort-icon {{
    opacity: 1;
    color: var(--accent-blue);
}}
tbody td {{
    padding: 12px 16px;
    border-bottom: 1px solid rgba(42, 42, 74, 0.4);
    white-space: nowrap;
}}
tbody tr {{
    transition: background 0.2s ease;
}}
tbody tr:hover {{
    background: var(--bg-table-row-hover);
}}
.num {{
    text-align: right;
    font-family: 'SF Mono', 'Fira Code', monospace;
    font-size: 12px;
}}
.campaign-name {{
    max-width: 320px;
    overflow: hidden;
    text-overflow: ellipsis;
    font-weight: 500;
}}
.adset-name {{
    max-width: 200px;
    font-weight: 500;
    color: var(--accent-cyan);
}}

/* CPL color coding */
.cpl-low {{
    color: var(--accent-cyan) !important;
    font-weight: 700;
}}
.cpl-mid {{
    color: var(--accent-orange) !important;
    font-weight: 700;
}}
.cpl-high {{
    color: var(--accent-red) !important;
    font-weight: 700;
}}

/* ── BADGES ───────────────────────────────────────────── */
.badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    vertical-align: middle;
    margin-left: 6px;
}}
.badge-leads {{
    background: rgba(0, 212, 170, 0.15);
    color: var(--accent-cyan);
}}
.badge-traffic {{
    background: rgba(67, 97, 238, 0.15);
    color: var(--accent-blue);
}}
.badge-awareness {{
    background: rgba(123, 47, 247, 0.15);
    color: var(--accent-purple);
}}
.badge-other {{
    background: rgba(255, 159, 67, 0.15);
    color: var(--accent-orange);
}}

/* ── PERFORMER CARDS ──────────────────────────────────── */
.performers-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    margin-bottom: 32px;
}}
.performers-section {{
    background: var(--bg-card);
    border-radius: 16px;
    padding: 24px;
    box-shadow: var(--shadow);
    border: 1px solid var(--border-color);
}}
.performers-section h3 {{
    font-size: 16px;
    font-weight: 700;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
}}
.performer-card {{
    background: var(--bg-card-alt);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 12px;
    transition: transform 0.2s ease;
}}
.performer-card:hover {{
    transform: translateX(4px);
}}
.performer-rank {{
    font-size: 14px;
    font-weight: 800;
    margin-bottom: 4px;
}}
.performer-name {{
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 10px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.performer-stats {{
    display: flex;
    gap: 20px;
}}
.performer-stat {{
    display: flex;
    flex-direction: column;
}}
.stat-label {{
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
.stat-value {{
    font-size: 15px;
    font-weight: 700;
    color: var(--text-primary);
    font-family: 'SF Mono', monospace;
}}

/* ── RESPONSIVE ───────────────────────────────────────── */
@media (max-width: 1200px) {{
    .chart-grid-3 {{ grid-template-columns: 1fr 1fr; }}
}}
@media (max-width: 900px) {{
    .chart-grid, .performers-grid {{ grid-template-columns: 1fr; }}
    .chart-grid-3 {{ grid-template-columns: 1fr; }}
    .kpi-grid {{ grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }}
    .header-content {{ flex-direction: column; text-align: center; }}
    .header-right {{ text-align: center; }}
}}
@media (max-width: 600px) {{
    .kpi-value {{ font-size: 20px; }}
    .container {{ padding: 12px; }}
}}

/* ── FOOTER ───────────────────────────────────────────── */
.footer {{
    text-align: center;
    padding: 30px;
    color: var(--text-muted);
    font-size: 12px;
    border-top: 1px solid var(--border-color);
    margin-top: 40px;
}}
</style>
</head>
<body>

<!-- HEADER -->
<div class="header">
    <div class="header-content">
        <div class="header-left">
            <h1>Los Lagos Condominio</h1>
            <div class="subtitle">Dashboard de Meta Ads &mdash; Analisis de Campanas</div>
            <div class="account-id">act_1089998585939349</div>
        </div>
        <div class="header-right">
            <div class="date-range">28 Ene 2026 &mdash; 26 Feb 2026</div>
            <div class="updated">Ultima actualizacion: {now_str}</div>
        </div>
    </div>
</div>

<div class="container">

<!-- KPI CARDS -->
<div class="kpi-grid">
    <div class="kpi-card animate-in">
        <span class="kpi-icon">&#128176;</span>
        <div class="kpi-label">Inversion Total</div>
        <div class="kpi-value">${total_spend:,.0f}</div>
        <div class="kpi-sub">COP (30 dias)</div>
    </div>
    <div class="kpi-card animate-in">
        <span class="kpi-icon">&#128203;</span>
        <div class="kpi-label">Leads Totales</div>
        <div class="kpi-value">{total_leads:,}</div>
        <div class="kpi-sub">Formularios enviados</div>
    </div>
    <div class="kpi-card animate-in">
        <span class="kpi-icon">&#128178;</span>
        <div class="kpi-label">Costo por Lead</div>
        <div class="kpi-value">${avg_cpl:,.0f}</div>
        <div class="kpi-sub">COP promedio</div>
    </div>
    <div class="kpi-card animate-in">
        <span class="kpi-icon">&#128065;</span>
        <div class="kpi-label">Impresiones</div>
        <div class="kpi-value">{total_impressions:,}</div>
        <div class="kpi-sub">CPM: ${avg_cpm:,.0f}</div>
    </div>
    <div class="kpi-card animate-in">
        <span class="kpi-icon">&#128073;</span>
        <div class="kpi-label">CTR (Total)</div>
        <div class="kpi-value">{avg_ctr:.2f}%</div>
        <div class="kpi-sub">{total_clicks:,} clics totales</div>
    </div>
    <div class="kpi-card animate-in">
        <span class="kpi-icon">&#127758;</span>
        <div class="kpi-label">Alcance</div>
        <div class="kpi-value">{total_reach:,}</div>
        <div class="kpi-sub">Cuentas unicas</div>
    </div>
    <div class="kpi-card animate-in">
        <span class="kpi-icon">&#127910;</span>
        <div class="kpi-label">Reproducciones Video</div>
        <div class="kpi-value">{total_video_views:,}</div>
        <div class="kpi-sub">Vistas totales</div>
    </div>
    <div class="kpi-card animate-in">
        <span class="kpi-icon">&#10084;</span>
        <div class="kpi-label">Engagement</div>
        <div class="kpi-value">{total_engagement:,}</div>
        <div class="kpi-sub">{total_messaging:,} conexiones msg</div>
    </div>
</div>

<!-- ══════════════════════════════════════════════════════ -->
<!-- VENTAS REALES & ROAS SECTION                          -->
<!-- ══════════════════════════════════════════════════════ -->

<!-- VENTAS KPI CARDS -->
<div class="section">
    <div class="section-title"><span class="icon">&#128176;</span> Ventas Reales &mdash; Cierre de Campanas (Google Sheet)</div>
    <div class="kpi-grid" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));">
        <div class="kpi-card animate-in" style="border: 1px solid rgba(0,212,170,0.3);">
            <span class="kpi-icon">&#127942;</span>
            <div class="kpi-label">ROAS META</div>
            <div class="kpi-value" style="color: {'var(--accent-cyan)' if roas >= 3 else 'var(--accent-orange)' if roas >= 1 else 'var(--accent-red)'};">{roas:.1f}x</div>
            <div class="kpi-sub">Revenue / Inversion Ads</div>
        </div>
        <div class="kpi-card animate-in">
            <span class="kpi-icon">&#128181;</span>
            <div class="kpi-label">Revenue META</div>
            <div class="kpi-value">{fmt_cop(meta_ventas_revenue)}</div>
            <div class="kpi-sub">{meta_ventas_count} lotes vendidos via Meta</div>
        </div>
        <div class="kpi-card animate-in">
            <span class="kpi-icon">&#128200;</span>
            <div class="kpi-label">Revenue Total</div>
            <div class="kpi-value">{fmt_cop(ventas_total_revenue)}</div>
            <div class="kpi-sub">{ventas_total_count} ventas todas las fuentes</div>
        </div>
        <div class="kpi-card animate-in">
            <span class="kpi-icon">&#127968;</span>
            <div class="kpi-label">Ticket Promedio</div>
            <div class="kpi-value">{fmt_cop(meta_avg_ticket)}</div>
            <div class="kpi-sub">Precio prom. lote (META)</div>
        </div>
        <div class="kpi-card animate-in">
            <span class="kpi-icon">&#9201;</span>
            <div class="kpi-label">Dias para Cierre</div>
            <div class="kpi-value">{meta_median_dias} dias</div>
            <div class="kpi-sub">Mediana ({meta_avg_dias:.1f} promedio)</div>
        </div>
        <div class="kpi-card animate-in">
            <span class="kpi-icon">&#128178;</span>
            <div class="kpi-label">Costo por Venta</div>
            <div class="kpi-value">{fmt_cop(total_spend / meta_ventas_count) if meta_ventas_count else '$0'}</div>
            <div class="kpi-sub">Inversion Ads / Ventas META</div>
        </div>
    </div>
</div>

<!-- VENTAS BY SOURCE CHART + TABLE -->
<div class="chart-grid">
    <div class="section">
        <div class="section-title"><span class="icon">&#128202;</span> Ventas por Fuente</div>
        <div class="chart-container">
            <canvas id="sourceChart" height="280"></canvas>
        </div>
    </div>
    <div class="section">
        <div class="section-title"><span class="icon">&#128203;</span> Atribucion de Ventas</div>
        <div class="table-wrapper" style="margin-bottom: 0;">
            <div class="table-scroll">
                <table>
                    <thead>
                        <tr>
                            <th>Fuente</th>
                            <th>Ventas</th>
                            <th>% Ventas</th>
                            <th>Revenue</th>
                            <th>% Revenue</th>
                        </tr>
                    </thead>
                    <tbody>
                        {build_ventas_source_rows()}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<!-- CAMPAIGN ROAS TABLE -->
<div class="section">
    <div class="section-title"><span class="icon">&#128176;</span> ROAS por Campana &mdash; Cruce Spend vs Ventas Reales</div>
    <div class="table-wrapper">
        <div class="table-scroll">
            <table id="roasTable">
                <thead>
                    <tr>
                        <th onclick="sortTable('roasTable', 0, 'str')">Campana <span class="sort-icon">&#8645;</span></th>
                        <th onclick="sortTable('roasTable', 1, 'num')">Inversion <span class="sort-icon">&#8645;</span></th>
                        <th onclick="sortTable('roasTable', 2, 'num')">Leads <span class="sort-icon">&#8645;</span></th>
                        <th onclick="sortTable('roasTable', 3, 'num')">Ventas <span class="sort-icon">&#8645;</span></th>
                        <th onclick="sortTable('roasTable', 4, 'num')">Conv. Rate <span class="sort-icon">&#8645;</span></th>
                        <th onclick="sortTable('roasTable', 5, 'num')">Revenue <span class="sort-icon">&#8645;</span></th>
                        <th onclick="sortTable('roasTable', 6, 'num')">ROAS <span class="sort-icon">&#8645;</span></th>
                        <th onclick="sortTable('roasTable', 7, 'num')">Costo/Venta <span class="sort-icon">&#8645;</span></th>
                    </tr>
                </thead>
                <tbody>
                    {build_campaign_roas_rows()}
                </tbody>
            </table>
        </div>
    </div>
</div>

<!-- ASESORES + CREATIVOS -->
<div class="chart-grid">
    <div class="section">
        <div class="section-title"><span class="icon">&#128100;</span> Asesores &mdash; Ventas META</div>
        <div class="table-wrapper" style="margin-bottom: 0;">
            <div class="table-scroll">
                <table>
                    <thead>
                        <tr>
                            <th>Asesor</th>
                            <th>Ventas</th>
                            <th>Revenue</th>
                            <th>Ticket Prom.</th>
                        </tr>
                    </thead>
                    <tbody>
                        {build_asesor_rows()}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    <div class="section">
        <div class="section-title"><span class="icon">&#127912;</span> Creativos que Venden &mdash; META</div>
        <div class="table-wrapper" style="margin-bottom: 0;">
            <div class="table-scroll">
                <table>
                    <thead>
                        <tr>
                            <th>Anuncio/Creativo</th>
                            <th>Ventas</th>
                            <th>Revenue</th>
                        </tr>
                    </thead>
                    <tbody>
                        {build_creative_ventas_rows()}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<!-- ══════════════════════════════════════════════════════ -->
<!-- META ADS PERFORMANCE (Original Sections)              -->
<!-- ══════════════════════════════════════════════════════ -->

<!-- DAILY SPEND & LEADS CHART -->
<div class="section">
    <div class="section-title"><span class="icon">&#128200;</span> Inversion Diaria y Leads</div>
    <div class="chart-container chart-full">
        <canvas id="dailyChart" height="100"></canvas>
    </div>
</div>

<!-- OBJECTIVE DISTRIBUTION + TRENDS -->
<div class="chart-grid">
    <div class="section">
        <div class="section-title"><span class="icon">&#127919;</span> Distribucion por Objetivo</div>
        <div class="chart-container">
            <canvas id="objectiveChart" height="260"></canvas>
        </div>
    </div>
    <div class="section">
        <div class="section-title"><span class="icon">&#128202;</span> Tendencia CPL Diario</div>
        <div class="chart-container">
            <canvas id="cplTrendChart" height="260"></canvas>
        </div>
    </div>
</div>

<!-- METRIC TRENDS -->
<div class="section">
    <div class="section-title"><span class="icon">&#128208;</span> Tendencias de Metricas Clave</div>
    <div class="chart-grid">
        <div class="chart-container">
            <canvas id="ctrTrendChart" height="220"></canvas>
        </div>
        <div class="chart-container">
            <canvas id="cpmTrendChart" height="220"></canvas>
        </div>
    </div>
</div>

<!-- TOP / BOTTOM PERFORMERS -->
<div class="section">
    <div class="section-title"><span class="icon">&#127942;</span> Mejores y Peores Campanas por CPL</div>
    <div class="performers-grid">
        <div class="performers-section">
            <h3><span style="color: var(--accent-cyan)">&#9650;</span> Mejor CPL (Mas Eficientes)</h3>
            {build_performer_cards(top_performers, is_top=True)}
        </div>
        <div class="performers-section">
            <h3><span style="color: var(--accent-red)">&#9660;</span> Mayor CPL (Menos Eficientes)</h3>
            {build_performer_cards(bottom_performers, is_top=False)}
        </div>
    </div>
</div>

<!-- CAMPAIGN PERFORMANCE TABLE -->
<div class="section">
    <div class="section-title"><span class="icon">&#128640;</span> Rendimiento por Campana</div>
    <div class="table-wrapper">
        <div class="table-scroll">
            <table id="campaignTable">
                <thead>
                    <tr>
                        <th onclick="sortTable('campaignTable', 0, 'str')">Campana <span class="sort-icon">&#8645;</span></th>
                        <th onclick="sortTable('campaignTable', 1, 'num')">Inversion <span class="sort-icon">&#8645;</span></th>
                        <th onclick="sortTable('campaignTable', 2, 'num')">Impresiones <span class="sort-icon">&#8645;</span></th>
                        <th onclick="sortTable('campaignTable', 3, 'num')">Clics <span class="sort-icon">&#8645;</span></th>
                        <th onclick="sortTable('campaignTable', 4, 'num')">CTR <span class="sort-icon">&#8645;</span></th>
                        <th onclick="sortTable('campaignTable', 5, 'num')">Leads <span class="sort-icon">&#8645;</span></th>
                        <th onclick="sortTable('campaignTable', 6, 'num')">CPL <span class="sort-icon">&#8645;</span></th>
                        <th onclick="sortTable('campaignTable', 7, 'num')">Link Clicks <span class="sort-icon">&#8645;</span></th>
                        <th onclick="sortTable('campaignTable', 8, 'num')">Video Views <span class="sort-icon">&#8645;</span></th>
                    </tr>
                </thead>
                <tbody>
                    {build_campaign_rows()}
                </tbody>
            </table>
        </div>
    </div>
</div>

<!-- AD SET PERFORMANCE TABLE -->
<div class="section">
    <div class="section-title"><span class="icon">&#128218;</span> Rendimiento por Conjunto de Anuncios</div>
    <div class="table-wrapper">
        <div class="table-scroll">
            <table id="adsetTable">
                <thead>
                    <tr>
                        <th onclick="sortTable('adsetTable', 0, 'str')">Campana <span class="sort-icon">&#8645;</span></th>
                        <th onclick="sortTable('adsetTable', 1, 'str')">Conjunto <span class="sort-icon">&#8645;</span></th>
                        <th onclick="sortTable('adsetTable', 2, 'num')">Inversion <span class="sort-icon">&#8645;</span></th>
                        <th onclick="sortTable('adsetTable', 3, 'num')">Impresiones <span class="sort-icon">&#8645;</span></th>
                        <th onclick="sortTable('adsetTable', 4, 'num')">Clics <span class="sort-icon">&#8645;</span></th>
                        <th onclick="sortTable('adsetTable', 5, 'num')">CTR <span class="sort-icon">&#8645;</span></th>
                        <th onclick="sortTable('adsetTable', 6, 'num')">Leads <span class="sort-icon">&#8645;</span></th>
                        <th onclick="sortTable('adsetTable', 7, 'num')">CPL <span class="sort-icon">&#8645;</span></th>
                        <th onclick="sortTable('adsetTable', 8, 'num')">Link Clicks <span class="sort-icon">&#8645;</span></th>
                        <th onclick="sortTable('adsetTable', 9, 'num')">Video Views <span class="sort-icon">&#8645;</span></th>
                    </tr>
                </thead>
                <tbody>
                    {build_adset_rows()}
                </tbody>
            </table>
        </div>
    </div>
</div>

<!-- FOOTER -->
<div class="footer">
    Los Lagos Condominio &mdash; Dashboard Meta Ads + Ventas Reales &mdash; Generado automaticamente el {now_str}<br>
    Datos de Meta Ads API &bull; Ventas: Google Sheet (Cierre Campanas) &bull; Cuenta: act_1089998585939349 &bull; COP
</div>

</div><!-- /container -->

<script>
// ── Chart.js Global Config ─────────────────────────────
Chart.defaults.color = '#8892b0';
Chart.defaults.borderColor = 'rgba(42, 42, 74, 0.5)';
Chart.defaults.font.family = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";

// ── VENTAS POR FUENTE CHART ────────────────────────────
const sourceLabels = {json.dumps(source_labels)};
const sourceCounts = {json.dumps(source_counts)};
const sourceRevenues = {json.dumps(source_revenues)};

new Chart(document.getElementById('sourceChart'), {{
    type: 'bar',
    data: {{
        labels: sourceLabels,
        datasets: [
            {{
                label: 'Ventas (#)',
                data: sourceCounts,
                backgroundColor: [
                    'rgba(67, 97, 238, 0.7)',
                    'rgba(0, 212, 170, 0.7)',
                    'rgba(123, 47, 247, 0.7)',
                    'rgba(255, 159, 67, 0.7)',
                    'rgba(255, 107, 157, 0.7)',
                    'rgba(255, 107, 107, 0.7)',
                    'rgba(100, 100, 150, 0.7)'
                ],
                borderColor: [
                    '#4361ee', '#00d4aa', '#7b2ff7', '#ff9f43', '#ff6b9d', '#ff6b6b', '#6464a0'
                ],
                borderWidth: 2,
                borderRadius: 6,
                yAxisID: 'y'
            }},
            {{
                label: 'Revenue (COP)',
                data: sourceRevenues,
                type: 'line',
                borderColor: '#00d4aa',
                backgroundColor: 'rgba(0, 212, 170, 0.1)',
                borderWidth: 3,
                pointBackgroundColor: '#00d4aa',
                pointRadius: 5,
                pointHoverRadius: 8,
                tension: 0.3,
                yAxisID: 'y1'
            }}
        ]
    }},
    options: {{
        responsive: true,
        interaction: {{ mode: 'index', intersect: false }},
        plugins: {{
            legend: {{ labels: {{ usePointStyle: true, padding: 16 }} }},
            tooltip: {{
                backgroundColor: 'rgba(15, 15, 26, 0.95)',
                borderColor: 'rgba(67, 97, 238, 0.3)',
                borderWidth: 1,
                padding: 12,
                callbacks: {{
                    label: function(ctx) {{
                        if (ctx.dataset.yAxisID === 'y1') {{
                            return 'Revenue: $' + (ctx.parsed.y / 1000000).toFixed(0) + 'M';
                        }}
                        return ctx.dataset.label + ': ' + ctx.parsed.y;
                    }}
                }}
            }}
        }},
        scales: {{
            y: {{
                position: 'left',
                title: {{ display: true, text: '# Ventas', font: {{ weight: '600' }} }},
                grid: {{ color: 'rgba(42, 42, 74, 0.3)' }}
            }},
            y1: {{
                position: 'right',
                title: {{ display: true, text: 'Revenue (COP)', font: {{ weight: '600' }} }},
                ticks: {{ callback: v => '$' + (v/1000000).toFixed(0) + 'M' }},
                grid: {{ drawOnChartArea: false }}
            }},
            x: {{ grid: {{ color: 'rgba(42, 42, 74, 0.2)' }} }}
        }}
    }}
}});

const dailyLabels = {json.dumps(daily_labels)};
const dailySpend = {json.dumps(daily_spend)};
const dailyLeads = {json.dumps(daily_leads)};
const dailyCPL = {json.dumps(daily_cpl)};
const dailyCTR = {json.dumps(daily_ctr)};
const dailyCPM = {json.dumps(daily_cpm)};

// ── DAILY SPEND & LEADS CHART ──────────────────────────
new Chart(document.getElementById('dailyChart'), {{
    type: 'bar',
    data: {{
        labels: dailyLabels,
        datasets: [
            {{
                label: 'Inversion Diaria (COP)',
                data: dailySpend,
                type: 'bar',
                backgroundColor: 'rgba(67, 97, 238, 0.35)',
                borderColor: 'rgba(67, 97, 238, 0.8)',
                borderWidth: 1,
                borderRadius: 4,
                order: 2,
                yAxisID: 'y'
            }},
            {{
                label: 'Leads Diarios',
                data: dailyLeads,
                type: 'line',
                borderColor: '#00d4aa',
                backgroundColor: 'rgba(0, 212, 170, 0.1)',
                borderWidth: 3,
                pointBackgroundColor: '#00d4aa',
                pointBorderColor: '#00d4aa',
                pointRadius: 4,
                pointHoverRadius: 7,
                tension: 0.3,
                fill: true,
                order: 1,
                yAxisID: 'y1'
            }}
        ]
    }},
    options: {{
        responsive: true,
        interaction: {{ mode: 'index', intersect: false }},
        plugins: {{
            legend: {{
                labels: {{ usePointStyle: true, padding: 20 }}
            }},
            tooltip: {{
                backgroundColor: 'rgba(15, 15, 26, 0.95)',
                borderColor: 'rgba(67, 97, 238, 0.3)',
                borderWidth: 1,
                padding: 12,
                titleFont: {{ weight: '600' }},
                callbacks: {{
                    label: function(ctx) {{
                        if (ctx.dataset.yAxisID === 'y') {{
                            return 'Inversion: $' + ctx.parsed.y.toLocaleString('es-CO');
                        }}
                        return 'Leads: ' + ctx.parsed.y;
                    }}
                }}
            }}
        }},
        scales: {{
            y: {{
                position: 'left',
                title: {{ display: true, text: 'Inversion (COP)', font: {{ weight: '600' }} }},
                ticks: {{
                    callback: v => '$' + (v/1000).toFixed(0) + 'K'
                }},
                grid: {{ color: 'rgba(42, 42, 74, 0.3)' }}
            }},
            y1: {{
                position: 'right',
                title: {{ display: true, text: 'Leads', font: {{ weight: '600' }} }},
                grid: {{ drawOnChartArea: false }}
            }},
            x: {{
                grid: {{ color: 'rgba(42, 42, 74, 0.2)' }}
            }}
        }}
    }}
}});

// ── OBJECTIVE DONUT CHART ──────────────────────────────
new Chart(document.getElementById('objectiveChart'), {{
    type: 'doughnut',
    data: {{
        labels: {json.dumps(obj_labels_es)},
        datasets: [{{
            data: {json.dumps(obj_values)},
            backgroundColor: [
                'rgba(0, 212, 170, 0.8)',
                'rgba(67, 97, 238, 0.8)',
                'rgba(123, 47, 247, 0.8)',
                'rgba(255, 159, 67, 0.8)'
            ],
            borderColor: [
                '#00d4aa',
                '#4361ee',
                '#7b2ff7',
                '#ff9f43'
            ],
            borderWidth: 2,
            hoverOffset: 12
        }}]
    }},
    options: {{
        responsive: true,
        cutout: '65%',
        plugins: {{
            legend: {{
                position: 'bottom',
                labels: {{ usePointStyle: true, padding: 16, font: {{ size: 12 }} }}
            }},
            tooltip: {{
                backgroundColor: 'rgba(15, 15, 26, 0.95)',
                borderColor: 'rgba(67, 97, 238, 0.3)',
                borderWidth: 1,
                padding: 12,
                callbacks: {{
                    label: function(ctx) {{
                        const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                        const pct = ((ctx.parsed / total) * 100).toFixed(1);
                        return ctx.label + ': $' + ctx.parsed.toLocaleString('es-CO') + ' (' + pct + '%)';
                    }}
                }}
            }}
        }}
    }}
}});

// ── CPL TREND CHART ────────────────────────────────────
new Chart(document.getElementById('cplTrendChart'), {{
    type: 'line',
    data: {{
        labels: dailyLabels,
        datasets: [{{
            label: 'CPL Diario (COP)',
            data: dailyCPL,
            borderColor: '#ff6b9d',
            backgroundColor: 'rgba(255, 107, 157, 0.1)',
            borderWidth: 2.5,
            pointBackgroundColor: '#ff6b9d',
            pointRadius: 3,
            pointHoverRadius: 6,
            tension: 0.3,
            fill: true
        }}]
    }},
    options: {{
        responsive: true,
        plugins: {{
            legend: {{ labels: {{ usePointStyle: true }} }},
            tooltip: {{
                backgroundColor: 'rgba(15, 15, 26, 0.95)',
                callbacks: {{
                    label: ctx => 'CPL: $' + ctx.parsed.y.toLocaleString('es-CO')
                }}
            }}
        }},
        scales: {{
            y: {{
                title: {{ display: true, text: 'CPL (COP)' }},
                ticks: {{ callback: v => '$' + v.toLocaleString('es-CO') }},
                grid: {{ color: 'rgba(42, 42, 74, 0.3)' }}
            }},
            x: {{ grid: {{ color: 'rgba(42, 42, 74, 0.2)' }} }}
        }}
    }}
}});

// ── CTR TREND CHART ────────────────────────────────────
new Chart(document.getElementById('ctrTrendChart'), {{
    type: 'line',
    data: {{
        labels: dailyLabels,
        datasets: [{{
            label: 'CTR Diario (%)',
            data: dailyCTR,
            borderColor: '#4361ee',
            backgroundColor: 'rgba(67, 97, 238, 0.1)',
            borderWidth: 2.5,
            pointBackgroundColor: '#4361ee',
            pointRadius: 3,
            pointHoverRadius: 6,
            tension: 0.3,
            fill: true
        }}]
    }},
    options: {{
        responsive: true,
        plugins: {{
            legend: {{ labels: {{ usePointStyle: true }} }},
            tooltip: {{
                backgroundColor: 'rgba(15, 15, 26, 0.95)',
                callbacks: {{ label: ctx => 'CTR: ' + ctx.parsed.y.toFixed(2) + '%' }}
            }}
        }},
        scales: {{
            y: {{
                title: {{ display: true, text: 'CTR (%)' }},
                ticks: {{ callback: v => v.toFixed(1) + '%' }},
                grid: {{ color: 'rgba(42, 42, 74, 0.3)' }}
            }},
            x: {{ grid: {{ color: 'rgba(42, 42, 74, 0.2)' }} }}
        }}
    }}
}});

// ── CPM TREND CHART ────────────────────────────────────
new Chart(document.getElementById('cpmTrendChart'), {{
    type: 'line',
    data: {{
        labels: dailyLabels,
        datasets: [{{
            label: 'CPM Diario (COP)',
            data: dailyCPM,
            borderColor: '#ff9f43',
            backgroundColor: 'rgba(255, 159, 67, 0.1)',
            borderWidth: 2.5,
            pointBackgroundColor: '#ff9f43',
            pointRadius: 3,
            pointHoverRadius: 6,
            tension: 0.3,
            fill: true
        }}]
    }},
    options: {{
        responsive: true,
        plugins: {{
            legend: {{ labels: {{ usePointStyle: true }} }},
            tooltip: {{
                backgroundColor: 'rgba(15, 15, 26, 0.95)',
                callbacks: {{ label: ctx => 'CPM: $' + ctx.parsed.y.toLocaleString('es-CO') }}
            }}
        }},
        scales: {{
            y: {{
                title: {{ display: true, text: 'CPM (COP)' }},
                ticks: {{ callback: v => '$' + v.toLocaleString('es-CO') }},
                grid: {{ color: 'rgba(42, 42, 74, 0.3)' }}
            }},
            x: {{ grid: {{ color: 'rgba(42, 42, 74, 0.2)' }} }}
        }}
    }}
}});

// ── TABLE SORTING ──────────────────────────────────────
function sortTable(tableId, colIdx, type) {{
    const table = document.getElementById(tableId);
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const ths = table.querySelectorAll('thead th');

    // Toggle direction
    const th = ths[colIdx];
    const currentDir = th.dataset.sortDir || 'desc';
    const newDir = currentDir === 'asc' ? 'desc' : 'asc';

    // Reset all
    ths.forEach(h => {{ h.classList.remove('sorted'); h.dataset.sortDir = ''; }});
    th.classList.add('sorted');
    th.dataset.sortDir = newDir;

    rows.sort((a, b) => {{
        let aVal = a.cells[colIdx].textContent.trim();
        let bVal = b.cells[colIdx].textContent.trim();

        if (type === 'num') {{
            // Parse numeric: remove $, dots, commas, %, -
            aVal = aVal.replace(/[$%.]/g, '').replace(/,/g, '').replace('-', '0');
            bVal = bVal.replace(/[$%.]/g, '').replace(/,/g, '').replace('-', '0');
            aVal = parseFloat(aVal) || 0;
            bVal = parseFloat(bVal) || 0;
        }} else {{
            aVal = aVal.toLowerCase();
            bVal = bVal.toLowerCase();
        }}

        if (aVal < bVal) return newDir === 'asc' ? -1 : 1;
        if (aVal > bVal) return newDir === 'asc' ? 1 : -1;
        return 0;
    }});

    rows.forEach(row => tbody.appendChild(row));
}}

// ── Animate elements on scroll ─────────────────────────
const observer = new IntersectionObserver((entries) => {{
    entries.forEach(entry => {{
        if (entry.isIntersecting) {{
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
        }}
    }});
}}, {{ threshold: 0.1 }});

document.querySelectorAll('.section').forEach(el => {{
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    observer.observe(el);
}});
</script>
</body>
</html>"""

# ── Write output ────────────────────────────────────────────────────────────
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(html)

file_size = os.path.getsize(OUTPUT_FILE)
print(f"\nDashboard generated successfully!")
print(f"Output: {OUTPUT_FILE}")
print(f"File size: {file_size / 1024:.1f} KB")
print(f"\nAccount KPIs:")
print(f"  Total Spend:      ${total_spend:,.0f} COP")
print(f"  Total Leads:      {total_leads:,}")
print(f"  Avg CPL:          ${avg_cpl:,.0f} COP")
print(f"  Total Impressions: {total_impressions:,}")
print(f"  CTR:              {avg_ctr:.2f}%")
print(f"  Total Reach:      {total_reach:,}")
print(f"  Video Views:      {total_video_views:,}")
print(f"  Engagement:       {total_engagement:,}")
print(f"  Campaigns:        {len(campaigns)}")
print(f"  Ad Sets:          {len(adsets)}")
print(f"  Daily Data Points: {len(daily_dates)}")
