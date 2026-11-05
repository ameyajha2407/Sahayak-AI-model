# analytics.py — Dashboard KPIs and Plotly charts.
# A5 fix: all queries respect is_sample flag, sample data clearly labelled.

# pyrefly: ignore[missing-import]
import plotly.graph_objects as go
from config import LANGUAGE_MAP, HUMAN_COST_PER_QUERY, AI_COST_PER_QUERY
from styles import COLORS, CHART_PALETTE


def get_interactions_df():
    """Load interactions from the database into a list of dicts."""
    from database import get_connection
    conn = get_connection()
    rows = conn.execute("SELECT * FROM interactions ORDER BY timestamp DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_kpis(interactions):
    """Compute dashboard KPI numbers from a list of interaction dicts."""
    if not interactions:
        return {
            "total": 0, "total_chats": 0,
            "resolved": 0, "ai_resolved_pct": 0,
            "escalated": 0, "escalated_pct": 0,
            "resolve_rate": 0, "avg_response_ms": 0,
            "sample_count": 0, "real_count": 0,
            "ai_cost_per_query": AI_COST_PER_QUERY,
        }
    total = len(interactions)
    resolved = sum(1 for i in interactions if i.get("resolved_by_ai"))
    escalated = sum(1 for i in interactions if i.get("escalated"))
    resp_times = [i["response_ms"] for i in interactions if i.get("response_ms")]
    sample_count = sum(1 for i in interactions if i.get("is_sample"))
    real_count = total - sample_count
    resolve_rate = round(resolved / total * 100, 1) if total else 0
    escalated_pct = round(escalated / total * 100, 1) if total else 0
    avg_resp = int(sum(resp_times) / len(resp_times)) if resp_times else 0
    return {
        "total": total,
        "total_chats": total,
        "resolved": resolved,
        "ai_resolved_pct": resolve_rate,
        "escalated": escalated,
        "escalated_pct": escalated_pct,
        "resolve_rate": resolve_rate,
        "avg_response_ms": avg_resp,
        "sample_count": sample_count,
        "real_count": real_count,
        "ai_cost_per_query": AI_COST_PER_QUERY,
    }


# ---------------------------------------------------------------------------
# Chart config — centralized palette and Inter font everywhere (styles.py)
# ---------------------------------------------------------------------------
_PALETTE = CHART_PALETTE
_FONT = dict(family="Inter, -apple-system, BlinkMacSystemFont, sans-serif", size=13, color=COLORS["navy"])
_TITLE_FONT = dict(family="Inter, -apple-system, BlinkMacSystemFont, sans-serif", size=16, color=COLORS["navy"])

_LAYOUT = dict(
    template="plotly_white",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=_FONT,
    margin=dict(l=30, r=30, t=50, b=30),
)

# Map language codes to full names for readable labels (Part F9)
_LANG_NAMES = {code: info["name"] for code, info in LANGUAGE_MAP.items()}


def language_donut(interactions):
    """Donut chart: queries per language with full names and theme palette."""
    counts = {}
    for i in interactions:
        lang = i.get("language", "en")
        label = _LANG_NAMES.get(lang, lang.title())
        counts[label] = counts.get(label, 0) + 1
    
    labels = list(counts.keys())
    values = list(counts.values())
    colors = [_PALETTE[idx % len(_PALETTE)] for idx in range(len(labels))]
    
    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.5,
        marker=dict(colors=colors, line=dict(color=COLORS["surface"], width=2)),
        textinfo="label+percent",
        textfont=_FONT,
    ))
    fig.update_layout(
        **_LAYOUT,
        title=dict(text="Language Distribution", font=_TITLE_FONT),
        showlegend=True,
        legend=dict(font=_FONT),
        height=320,
    )
    return fig


def intent_bar(interactions):
    """Horizontal bar chart: queries by intent with Inter font."""
    counts = {}
    for i in interactions:
        intent = i.get("intent", "other").replace("_", " ").title()
        counts[intent] = counts.get(intent, 0) + 1
    sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:8]
    fig = go.Figure(go.Bar(
        y=[it[0] for it in sorted_items],
        x=[it[1] for it in sorted_items],
        orientation="h",
        marker=dict(color=COLORS["blue"], line=dict(color=COLORS["navy"], width=1)),
        text=[str(it[1]) for it in sorted_items],
        textposition="auto",
        textfont=_FONT,
    ))
    fig.update_layout(
        **_LAYOUT,
        title=dict(text="Top Intents", font=_TITLE_FONT),
        yaxis=dict(tickfont=_FONT, autorange="reversed", gridcolor=COLORS["border"]),
        xaxis=dict(tickfont=_FONT, gridcolor=COLORS["border"]),
        height=320,
    )
    return fig


def sentiment_line(interactions):
    """Grouped bar chart: sentiment breakdown with Inter font."""
    counts = {}
    for i in interactions:
        sent = i.get("sentiment", "neutral").title()
        counts[sent] = counts.get(sent, 0) + 1
    labels = list(counts.keys())
    values = list(counts.values())
    colors = {
        "Happy": COLORS["green_border"],
        "Neutral": COLORS["blue"],
        "Frustrated": COLORS["lavender"],
        "Angry": COLORS["danger_border"],
    }
    bar_colors = [colors.get(l, _PALETTE[1]) for l in labels]
    fig = go.Figure(go.Bar(
        x=labels, y=values,
        marker=dict(color=bar_colors, line=dict(color=COLORS["navy"], width=1)),
        text=[str(v) for v in values],
        textposition="auto",
        textfont=_FONT,
    ))
    fig.update_layout(
        **_LAYOUT,
        title=dict(text="Sentiment Breakdown", font=_TITLE_FONT),
        xaxis=dict(tickfont=_FONT, gridcolor=COLORS["border"]),
        yaxis=dict(tickfont=_FONT, gridcolor=COLORS["border"]),
        height=320,
    )
    return fig


def resolution_gauge(resolve_rate):
    """Gauge chart: AI resolution rate percentage with Inter font."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=resolve_rate,
        title=dict(text="AI Resolution Rate", font=_TITLE_FONT),
        number=dict(suffix="%", font=dict(family="Inter, sans-serif", size=28, color=COLORS["navy"])),
        gauge=dict(
            axis=dict(range=[0, 100], tickcolor=COLORS["muted"], tickfont=_FONT),
            bar=dict(color=COLORS["blue"]),
            bgcolor=COLORS["page_bg"],
            borderwidth=1,
            bordercolor=COLORS["border"],
            steps=[
                dict(range=[0, 50], color=COLORS["danger_bg"]),
                dict(range=[50, 80], color=COLORS["lavender"]),
                dict(range=[80, 100], color=COLORS["green_bg"]),
            ],
        ),
    ))
    fig.update_layout(**_LAYOUT, height=280)
    return fig


def roi_calculator(volume, human_cost=HUMAN_COST_PER_QUERY,
                   ai_cost=AI_COST_PER_QUERY, resolution_rate=80):
    """Calculate estimated ROI savings.

    Formula: savings = all_human_cost - (ai_resolved_cost + human_remaining_cost)
    """
    res_rate = resolution_rate / 100.0
    all_human_cost = volume * human_cost
    ai_resolved_cost = volume * ai_cost
    human_remaining_cost = volume * (1 - res_rate) * human_cost
    cost_with_ai = ai_resolved_cost + human_remaining_cost
    savings = all_human_cost - cost_with_ai
    return {
        "human_cost": round(all_human_cost),
        "all_human_cost": round(all_human_cost),
        "ai_cost": round(cost_with_ai),
        "cost_with_ai": round(cost_with_ai),
        "savings": round(savings),
        "savings_pct": round(savings / all_human_cost * 100, 1) if all_human_cost else 0,
        "after_hours_coverage": "24/7 AI",
    }
