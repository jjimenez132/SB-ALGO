#!/usr/bin/env python3
"""
================================================================================
SB-ALGO BACKTEST DASHBOARD v1.0
================================================================================
Professional Streamlit app for backtesting the SB-ALGO prop engine.

Run: streamlit run backtest_dashboard.py
================================================================================
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date, timedelta
import numpy as np

from backtest_engine import BacktestEngine, get_default_filters

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="SB-ALGO Backtest",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# CUSTOM CSS
# ============================================================
st.markdown("""
<style>
    /* Dark theme overrides */
    .stApp { background-color: #0e1117; }
    
    /* KPI cards */
    .kpi-card {
        background: linear-gradient(135deg, #1a1f2e 0%, #252b3b 100%);
        border: 1px solid #2d3548;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        margin: 5px;
    }
    .kpi-value {
        font-size: 2.2rem;
        font-weight: 800;
        margin: 0;
        line-height: 1.2;
    }
    .kpi-label {
        font-size: 0.85rem;
        color: #8899aa;
        margin-top: 4px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .kpi-good { color: #00d97e; }
    .kpi-warn { color: #f6c343; }
    .kpi-bad { color: #e63757; }
    .kpi-neutral { color: #6e84a3; }
    
    /* Section headers */
    .section-header {
        font-size: 1.1rem;
        font-weight: 700;
        color: #b0c4de;
        text-transform: uppercase;
        letter-spacing: 2px;
        margin: 30px 0 15px 0;
        padding-bottom: 8px;
        border-bottom: 2px solid #2d3548;
    }
    
    /* Fix dataframe styling */
    .stDataFrame { border-radius: 8px; overflow: hidden; }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d1117 0%, #161b22 100%);
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# HELPER FUNCTIONS
# ============================================================
def kpi_card(label, value, color_class="kpi-neutral"):
    return f"""
    <div class="kpi-card">
        <p class="kpi-value {color_class}">{value}</p>
        <p class="kpi-label">{label}</p>
    </div>
    """

def get_color_class(win_rate):
    if win_rate >= 70: return "kpi-good"
    if win_rate >= 60: return "kpi-warn"
    return "kpi-bad"

def format_result(r):
    if r == 'win': return '✅ W'
    if r == 'loss': return '❌ L'
    if r == 'push': return '➖ P'
    return '❓'


# ============================================================
# SIDEBAR
# ============================================================
st.sidebar.markdown("# 🎯 SB-ALGO Backtest")
st.sidebar.markdown("---")

# Initialize engine
@st.cache_resource
def get_engine():
    return BacktestEngine()

engine = get_engine()

# Get available dates
@st.cache_data(ttl=3600)
def get_dates():
    return get_engine().get_available_dates()

avail_dates = get_dates()

if not avail_dates:
    st.error("No data available. Check database connection.")
    st.stop()

st.sidebar.markdown("### 📅 Date Range")
col1, col2 = st.sidebar.columns(2)
start_date = col1.date_input("Start", value=avail_dates[0], min_value=avail_dates[0], max_value=avail_dates[-1])
end_date = col2.date_input("End", value=avail_dates[-1], min_value=avail_dates[0], max_value=avail_dates[-1])

st.sidebar.markdown("### 🏀 Stat Types")
col1, col2 = st.sidebar.columns(2)
use_pts = col1.checkbox("PTS", value=True)
use_reb = col2.checkbox("REB", value=True)
use_ast = col1.checkbox("AST", value=True)
use_3pm = col2.checkbox("3PM", value=True)

stat_types = []
if use_pts: stat_types.append('pts')
if use_reb: stat_types.append('reb')
if use_ast: stat_types.append('ast')
if use_3pm: stat_types.append('3pm')

st.sidebar.markdown("### 🏆 Tiers")
col1, col2, col3 = st.sidebar.columns(3)
use_t1 = col1.checkbox("T1", value=True)
use_t2 = col2.checkbox("T2", value=True)
use_t3 = col3.checkbox("T3", value=True)

tiers = []
if use_t1: tiers.append(1)
if use_t2: tiers.append(2)
if use_t3: tiers.append(3)

st.sidebar.markdown("### ⚙️ Filter Overrides")
use_custom = st.sidebar.checkbox("Custom filter thresholds", value=False)

custom_filters = None
if use_custom:
    edge_override = st.sidebar.slider("Edge Min (%)", 0, 50, 15, 1) / 100
    cv_override = st.sidebar.slider("CV Max", 0.10, 1.00, 0.45, 0.01)
    proj_override = st.sidebar.slider("Projection Min", 0, 30, 5, 1)
    
    base = get_default_filters()
    custom_filters = {}
    for k, v in base.items():
        custom_filters[k] = dict(v)
        custom_filters[k]['edge_min'] = edge_override
        custom_filters[k]['cv_max'] = cv_override
        custom_filters[k]['proj_min'] = proj_override

# Run button
run_clicked = st.sidebar.button("🚀 Run Backtest", type="primary", use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Data:** {len(avail_dates)} days available")
st.sidebar.markdown(f"**Range:** {avail_dates[0]} → {avail_dates[-1]}")


# ============================================================
# MAIN CONTENT
# ============================================================

# Run backtest
@st.cache_data(show_spinner=False, ttl=1800)
def run_cached_backtest(_engine, start, end, filters_key, stat_types_key, tiers_key):
    """Run backtest with caching. _engine prefix means don't hash it."""
    filters = None
    if filters_key != 'default':
        # Decode the custom filters from the key
        parts = filters_key.split('_')
        edge = float(parts[1])
        cv = float(parts[2])
        proj = float(parts[3])
        base = get_default_filters()
        filters = {}
        for k, v in base.items():
            filters[k] = dict(v)
            filters[k]['edge_min'] = edge
            filters[k]['cv_max'] = cv
            filters[k]['proj_min'] = proj
    
    stat_list = stat_types_key.split(',') if stat_types_key else None
    tier_list = [int(t) for t in tiers_key.split(',') if t] if tiers_key else None
    
    return _engine.run_backtest(start, end, filters, 'DraftKings',
                                stat_list, tier_list)

# Build cache key
if use_custom and custom_filters:
    filters_key = f"custom_{edge_override}_{cv_override}_{proj_override}"
else:
    filters_key = "default"

stat_key = ','.join(stat_types) if stat_types else ''
tier_key = ','.join(str(t) for t in tiers) if tiers else ''

if run_clicked or 'backtest_run' not in st.session_state:
    if stat_types and tiers:
        st.session_state['backtest_run'] = True
        progress = st.progress(0, "Starting backtest...")
        
        # Can't easily pass progress to cached function, so run uncached first time
        df = engine.run_backtest(
            start_date, end_date,
            custom_filters, 'DraftKings',
            stat_types, tiers,
            progress_callback=lambda p, m: progress.progress(p, m)
        )
        progress.empty()
        st.session_state['df'] = df
    else:
        st.warning("Select at least one stat type and tier.")
        st.stop()

df = st.session_state.get('df', pd.DataFrame())

if df.empty:
    st.info("No picks generated. Try adjusting filters or date range.")
    st.stop()

# Filter to graded picks (have actual data)
graded = df[df['result'].isin(['win', 'loss', 'push'])].copy()
wins = len(graded[graded['result'] == 'win'])
losses = len(graded[graded['result'] == 'loss'])
pushes = len(graded[graded['result'] == 'push'])
total = wins + losses
n_days = df['date'].nunique()
win_rate = (wins / total * 100) if total > 0 else 0
ppd = total / n_days if n_days > 0 else 0

# ROI calculation
tier_units = {1: 1.5, 2: 1.0, 3: 0.5}
total_risked = sum(tier_units.get(int(t), 1.0) for t in graded['tier'])
total_won = sum(tier_units.get(int(t), 1.0) * 0.909
               for t in graded[graded['result'] == 'win']['tier'])
total_lost = sum(tier_units.get(int(t), 1.0)
                for t in graded[graded['result'] == 'loss']['tier'])
roi = ((total_won - total_lost) / total_risked * 100) if total_risked > 0 else 0

# OVER/UNDER split
over_picks = graded[graded['direction'] == 'OVER']
under_picks = graded[graded['direction'] == 'UNDER']
over_wins = len(over_picks[over_picks['result'] == 'win'])
over_total = len(over_picks[over_picks['result'].isin(['win', 'loss'])])
under_wins = len(under_picks[under_picks['result'] == 'win'])
under_total = len(under_picks[under_picks['result'].isin(['win', 'loss'])])

over_wr = (over_wins / over_total * 100) if over_total > 0 else 0
under_wr = (under_wins / under_total * 100) if under_total > 0 else 0


# ============================================================
# TABS
# ============================================================
tab1, tab2, tab3, tab4 = st.tabs(["📊 Summary", "📋 Pick Log", "🔍 Filter Analysis", "⚡ Optimizer"])

# ============================================================
# TAB 1: SUMMARY
# ============================================================
with tab1:
    st.markdown('<div class="section-header">Performance Overview</div>', unsafe_allow_html=True)
    
    # KPI Row
    cols = st.columns(6)
    cols[0].markdown(kpi_card("Win Rate", f"{win_rate:.1f}%", get_color_class(win_rate)), unsafe_allow_html=True)
    cols[1].markdown(kpi_card("Record", f"{wins}-{losses}", "kpi-neutral"), unsafe_allow_html=True)
    cols[2].markdown(kpi_card("ROI", f"{roi:+.1f}%", "kpi-good" if roi > 0 else "kpi-bad"), unsafe_allow_html=True)
    cols[3].markdown(kpi_card("Picks/Day", f"{ppd:.1f}", "kpi-neutral"), unsafe_allow_html=True)
    cols[4].markdown(kpi_card("Days", f"{n_days}", "kpi-neutral"), unsafe_allow_html=True)
    cols[5].markdown(kpi_card("Total Picks", f"{total}", "kpi-neutral"), unsafe_allow_html=True)
    
    # Direction breakdown
    st.markdown('<div class="section-header">Direction Breakdown</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    cols[0].markdown(kpi_card("OVER Picks", f"{over_total}", "kpi-neutral"), unsafe_allow_html=True)
    cols[1].markdown(kpi_card("OVER Win%", f"{over_wr:.1f}%", get_color_class(over_wr)), unsafe_allow_html=True)
    cols[2].markdown(kpi_card("UNDER Picks", f"{under_total}", "kpi-neutral"), unsafe_allow_html=True)
    cols[3].markdown(kpi_card("UNDER Win%", f"{under_wr:.1f}%", get_color_class(under_wr)), unsafe_allow_html=True)
    
    # Daily win rate chart
    st.markdown('<div class="section-header">Daily Performance</div>', unsafe_allow_html=True)
    
    daily = graded.groupby('date').apply(
        lambda x: pd.Series({
            'wins': len(x[x['result'] == 'win']),
            'losses': len(x[x['result'] == 'loss']),
            'total': len(x[x['result'].isin(['win', 'loss'])]),
            'win_rate': len(x[x['result'] == 'win']) / len(x[x['result'].isin(['win', 'loss'])]) * 100
                        if len(x[x['result'].isin(['win', 'loss'])]) > 0 else 0,
        })
    ).reset_index()
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Bar chart for picks
    fig.add_trace(
        go.Bar(x=daily['date'], y=daily['total'], name='Total Picks',
               marker_color='rgba(99, 110, 250, 0.4)', text=daily['total'],
               textposition='outside'),
        secondary_y=False,
    )
    
    # Line for win rate
    fig.add_trace(
        go.Scatter(x=daily['date'], y=daily['win_rate'], name='Win Rate %',
                   line=dict(color='#00d97e', width=3),
                   mode='lines+markers', marker=dict(size=8)),
        secondary_y=True,
    )
    
    # Target line at 70%
    fig.add_hline(y=70, line_dash="dash", line_color="#f6c343",
                  annotation_text="70% target", secondary_y=True)
    
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='#0e1117',
        plot_bgcolor='#151922',
        height=400,
        margin=dict(l=20, r=20, t=30, b=20),
        legend=dict(orientation='h', y=1.12),
        xaxis=dict(tickangle=-45),
    )
    fig.update_yaxes(title_text="Picks", secondary_y=False)
    fig.update_yaxes(title_text="Win Rate %", secondary_y=True, range=[0, 100])
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Tier breakdown
    st.markdown('<div class="section-header">Tier Breakdown</div>', unsafe_allow_html=True)
    
    tier_data = []
    for tier in sorted(graded['tier'].unique()):
        t = graded[graded['tier'] == tier]
        t_wl = t[t['result'].isin(['win', 'loss'])]
        t_wins = len(t_wl[t_wl['result'] == 'win'])
        t_total = len(t_wl)
        t_wr = t_wins / t_total * 100 if t_total > 0 else 0
        tier_data.append({
            'Tier': f'T{int(tier)}',
            'Picks': t_total,
            'Wins': t_wins,
            'Losses': t_total - t_wins,
            'Win Rate': f'{t_wr:.1f}%',
            'Units': f'{tier_units.get(int(tier), 1.0)}u',
        })
    
    st.dataframe(pd.DataFrame(tier_data), use_container_width=True, hide_index=True)
    
    # Stat breakdown
    st.markdown('<div class="section-header">Stat × Direction</div>', unsafe_allow_html=True)
    
    stat_dir_data = []
    for stat in sorted(graded['stat'].unique()):
        for direction in ['OVER', 'UNDER']:
            subset = graded[(graded['stat'] == stat) & (graded['direction'] == direction)]
            wl = subset[subset['result'].isin(['win', 'loss'])]
            w = len(wl[wl['result'] == 'win'])
            t = len(wl)
            if t > 0:
                stat_dir_data.append({
                    'Stat': stat,
                    'Direction': direction,
                    'Picks': t,
                    'W-L': f'{w}-{t-w}',
                    'Win Rate': round(w / t * 100, 1),
                })
    
    if stat_dir_data:
        sdf = pd.DataFrame(stat_dir_data)
        
        fig2 = px.bar(sdf, x='Stat', y='Win Rate', color='Direction',
                      barmode='group', text='Win Rate',
                      color_discrete_map={'OVER': '#636efa', 'UNDER': '#ef553b'},
                      hover_data=['Picks', 'W-L'])
        fig2.add_hline(y=70, line_dash="dash", line_color="#f6c343")
        fig2.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig2.update_layout(
            template='plotly_dark',
            paper_bgcolor='#0e1117',
            plot_bgcolor='#151922',
            height=350,
            margin=dict(l=20, r=20, t=30, b=20),
            yaxis_range=[0, 100],
        )
        st.plotly_chart(fig2, use_container_width=True)


# ============================================================
# TAB 2: PICK LOG
# ============================================================
with tab2:
    st.markdown('<div class="section-header">All Simulated Picks</div>', unsafe_allow_html=True)
    
    # Filters
    col1, col2, col3, col4 = st.columns(4)
    
    result_filter = col1.multiselect("Result", ['win', 'loss', 'push', 'no_data'],
                                      default=['win', 'loss'])
    stat_filter = col2.multiselect("Stat", sorted(df['stat'].unique()),
                                    default=sorted(df['stat'].unique()))
    dir_filter = col3.multiselect("Direction", ['OVER', 'UNDER'],
                                   default=['OVER', 'UNDER'])
    tier_filter = col4.multiselect("Tier", sorted(df['tier'].unique()),
                                    default=sorted(df['tier'].unique()))
    
    filtered = df[
        (df['result'].isin(result_filter)) &
        (df['stat'].isin(stat_filter)) &
        (df['direction'].isin(dir_filter)) &
        (df['tier'].isin(tier_filter))
    ].copy()
    
    filtered['Result'] = filtered['result'].apply(format_result)
    
    display_cols = ['date', 'player', 'stat', 'direction', 'line', 'projection',
                    'edge', 'cv', 'tier', 'actual', 'Result', 'is_home',
                    'pace_factor', 'def_factor']
    
    st.dataframe(
        filtered[display_cols].sort_values('date', ascending=False),
        use_container_width=True,
        hide_index=True,
        height=600,
        column_config={
            'date': st.column_config.TextColumn("Date"),
            'player': st.column_config.TextColumn("Player"),
            'edge': st.column_config.NumberColumn("Edge %", format="%.1f%%"),
            'cv': st.column_config.NumberColumn("CV", format="%.3f"),
            'projection': st.column_config.NumberColumn("Proj", format="%.1f"),
            'actual': st.column_config.NumberColumn("Actual", format="%.1f"),
            'pace_factor': st.column_config.NumberColumn("Pace", format="%.3f"),
            'def_factor': st.column_config.NumberColumn("Def", format="%.3f"),
        }
    )
    
    st.caption(f"Showing {len(filtered)} of {len(df)} picks")


# ============================================================
# TAB 3: FILTER ANALYSIS
# ============================================================
with tab3:
    st.markdown('<div class="section-header">Win Rate Heatmap</div>', unsafe_allow_html=True)
    
    # Build heatmap data
    if len(graded) > 0:
        heatmap_data = graded.groupby(['stat', 'direction']).apply(
            lambda x: len(x[x['result'] == 'win']) / len(x[x['result'].isin(['win', 'loss'])]) * 100
                      if len(x[x['result'].isin(['win', 'loss'])]) > 0 else 0
        ).unstack(fill_value=0)
        
        count_data = graded.groupby(['stat', 'direction']).apply(
            lambda x: len(x[x['result'].isin(['win', 'loss'])])
        ).unstack(fill_value=0)
        
        # Heatmap text: "WR% (N)"
        text_data = pd.DataFrame(
            [[f"{heatmap_data.iloc[i, j]:.0f}% ({count_data.iloc[i, j]})"
              if count_data.iloc[i, j] > 0 else "—"
              for j in range(len(heatmap_data.columns))]
             for i in range(len(heatmap_data.index))],
            index=heatmap_data.index,
            columns=heatmap_data.columns
        )
        
        fig_heat = go.Figure(data=go.Heatmap(
            z=heatmap_data.values,
            x=heatmap_data.columns,
            y=heatmap_data.index,
            text=text_data.values,
            texttemplate="%{text}",
            textfont=dict(size=14, color='white'),
            colorscale=[[0, '#e63757'], [0.5, '#f6c343'], [0.7, '#00d97e'], [1, '#00b874']],
            zmin=40, zmax=85,
            showscale=True,
            colorbar=dict(title='Win Rate %'),
        ))
        fig_heat.update_layout(
            template='plotly_dark',
            paper_bgcolor='#0e1117',
            plot_bgcolor='#151922',
            height=300,
            margin=dict(l=20, r=20, t=10, b=20),
        )
        st.plotly_chart(fig_heat, use_container_width=True)
    
    # Edge distribution
    st.markdown('<div class="section-header">Edge Distribution vs Win Rate</div>', unsafe_allow_html=True)
    
    if len(graded) > 0:
        graded_copy = graded.copy()
        graded_copy['edge_bin'] = pd.cut(graded_copy['edge'], bins=range(0, 105, 5),
                                          labels=[f"{i}-{i+5}%" for i in range(0, 100, 5)])
        
        edge_wr = graded_copy.groupby('edge_bin', observed=True).apply(
            lambda x: pd.Series({
                'win_rate': len(x[x['result'] == 'win']) / len(x[x['result'].isin(['win', 'loss'])]) * 100
                           if len(x[x['result'].isin(['win', 'loss'])]) > 0 else 0,
                'count': len(x[x['result'].isin(['win', 'loss'])]),
            })
        ).reset_index()
        
        fig_edge = make_subplots(specs=[[{"secondary_y": True}]])
        fig_edge.add_trace(
            go.Bar(x=edge_wr['edge_bin'], y=edge_wr['count'], name='Picks',
                   marker_color='rgba(99, 110, 250, 0.4)'),
            secondary_y=False
        )
        fig_edge.add_trace(
            go.Scatter(x=edge_wr['edge_bin'], y=edge_wr['win_rate'], name='Win Rate',
                       line=dict(color='#00d97e', width=3), mode='lines+markers'),
            secondary_y=True
        )
        fig_edge.add_hline(y=70, line_dash="dash", line_color="#f6c343", secondary_y=True)
        fig_edge.update_layout(
            template='plotly_dark', paper_bgcolor='#0e1117', plot_bgcolor='#151922',
            height=350, margin=dict(l=20, r=20, t=30, b=20),
            legend=dict(orientation='h', y=1.12),
        )
        fig_edge.update_yaxes(title_text="Picks", secondary_y=False)
        fig_edge.update_yaxes(title_text="Win Rate %", secondary_y=True, range=[0, 100])
        st.plotly_chart(fig_edge, use_container_width=True)
    
    # CV vs Win Rate
    st.markdown('<div class="section-header">CV vs Win Rate</div>', unsafe_allow_html=True)
    
    if len(graded) > 0:
        cv_bins = pd.cut(graded['cv'], bins=np.arange(0, 1.0, 0.05),
                          labels=[f"{i:.2f}" for i in np.arange(0, 0.95, 0.05)])
        graded_cv = graded.copy()
        graded_cv['cv_bin'] = cv_bins
        
        cv_wr = graded_cv.groupby('cv_bin', observed=True).apply(
            lambda x: pd.Series({
                'win_rate': len(x[x['result'] == 'win']) / len(x[x['result'].isin(['win', 'loss'])]) * 100
                           if len(x[x['result'].isin(['win', 'loss'])]) > 0 else 0,
                'count': len(x[x['result'].isin(['win', 'loss'])]),
            })
        ).reset_index()
        
        fig_cv = px.scatter(cv_wr, x='cv_bin', y='win_rate', size='count',
                            color='win_rate', color_continuous_scale=['#e63757', '#f6c343', '#00d97e'],
                            labels={'cv_bin': 'CV', 'win_rate': 'Win Rate %', 'count': 'Picks'})
        fig_cv.add_hline(y=70, line_dash="dash", line_color="#f6c343")
        fig_cv.update_layout(
            template='plotly_dark', paper_bgcolor='#0e1117', plot_bgcolor='#151922',
            height=350, margin=dict(l=20, r=20, t=30, b=20),
        )
        st.plotly_chart(fig_cv, use_container_width=True)
    
    # Per-filter breakdown
    st.markdown('<div class="section-header">Per-Filter Breakdown</div>', unsafe_allow_html=True)
    
    if len(graded) > 0:
        filter_data = graded.groupby('filter').apply(
            lambda x: pd.Series({
                'Picks': len(x[x['result'].isin(['win', 'loss'])]),
                'Wins': len(x[x['result'] == 'win']),
                'Losses': len(x[x['result'] == 'loss']),
                'Win Rate': round(len(x[x['result'] == 'win']) / len(x[x['result'].isin(['win', 'loss'])]) * 100, 1)
                           if len(x[x['result'].isin(['win', 'loss'])]) > 0 else 0,
                'Avg Edge': round(x['edge'].mean(), 1),
                'Avg CV': round(x['cv'].mean(), 3),
            })
        ).reset_index().sort_values('Win Rate', ascending=False)
        
        st.dataframe(filter_data, use_container_width=True, hide_index=True)


# ============================================================
# TAB 4: OPTIMIZER
# ============================================================
with tab4:
    st.markdown('<div class="section-header">Parameter Sweep</div>', unsafe_allow_html=True)
    st.caption("Sweep a filter parameter across a range to find optimal values.")
    
    col1, col2 = st.columns(2)
    sweep_param = col1.selectbox("Parameter to sweep", ['edge_min', 'cv_max'])
    
    if sweep_param == 'edge_min':
        sweep_range = col2.slider("Range (%)", 0, 50, (5, 40), 1)
        param_values = [x / 100 for x in range(sweep_range[0], sweep_range[1] + 1, 2)]
    else:
        sweep_range = col2.slider("Range", 0.10, 1.00, (0.20, 0.60), 0.02)
        param_values = [round(x, 2) for x in np.arange(sweep_range[0], sweep_range[1] + 0.01, 0.02)]
    
    run_sweep = st.button("🔄 Run Sweep", type="secondary", use_container_width=True)
    
    if run_sweep:
        sweep_progress = st.progress(0, "Starting sweep...")
        
        sweep_df = engine.sweep_parameter(
            start_date, end_date, sweep_param, param_values,
            custom_filters, 'DraftKings', stat_types, tiers,
            progress_callback=lambda p, m: sweep_progress.progress(p, m)
        )
        sweep_progress.empty()
        
        if len(sweep_df) > 0:
            st.session_state['sweep_df'] = sweep_df
    
    sweep_df = st.session_state.get('sweep_df')
    
    if sweep_df is not None and len(sweep_df) > 0:
        # Win Rate vs Volume tradeoff
        fig_sweep = make_subplots(specs=[[{"secondary_y": True}]])
        
        fig_sweep.add_trace(
            go.Scatter(x=sweep_df['param_value'], y=sweep_df['win_rate'],
                       name='Win Rate %', line=dict(color='#00d97e', width=3),
                       mode='lines+markers'),
            secondary_y=False
        )
        fig_sweep.add_trace(
            go.Bar(x=sweep_df['param_value'], y=sweep_df['ppd'],
                   name='Picks/Day', marker_color='rgba(99, 110, 250, 0.4)'),
            secondary_y=True
        )
        fig_sweep.add_hline(y=70, line_dash="dash", line_color="#f6c343", secondary_y=False)
        
        param_label = "Edge Min %" if sweep_param == 'edge_min' else "CV Max"
        fig_sweep.update_layout(
            template='plotly_dark', paper_bgcolor='#0e1117', plot_bgcolor='#151922',
            height=400, margin=dict(l=20, r=20, t=30, b=20),
            xaxis_title=param_label,
            legend=dict(orientation='h', y=1.12),
        )
        fig_sweep.update_yaxes(title_text="Win Rate %", secondary_y=False, range=[40, 100])
        fig_sweep.update_yaxes(title_text="Picks/Day", secondary_y=True)
        
        st.plotly_chart(fig_sweep, use_container_width=True)
        
        # Data table
        st.markdown('<div class="section-header">Sweep Results</div>', unsafe_allow_html=True)
        display_sweep = sweep_df.copy()
        if sweep_param == 'edge_min':
            display_sweep['param_value'] = (display_sweep['param_value'] * 100).round(0).astype(int).astype(str) + '%'
        st.dataframe(display_sweep, use_container_width=True, hide_index=True)


# ============================================================
# FOOTER
# ============================================================
st.markdown("---")
st.markdown(
    f"""<div style='text-align: center; color: #4a5568; font-size: 0.8rem;'>
    SB-ALGO Backtest Dashboard v1.0 • {n_days} days simulated • {total} picks graded
    </div>""",
    unsafe_allow_html=True
)
