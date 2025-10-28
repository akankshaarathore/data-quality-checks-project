import streamlit as st
import pandas as pd
import plotly.express as px

# Page Configuration
st.set_page_config(
  page_title="Data Quality Visualisation Dashboard",
  layout="wide"
)

st.markdown("""
<style>
  header[data-testid="stHeader"], .stApp, [data-testid="stSidebar"] {background-color: #0e1117;}
  h1, h2, h3, h4, h5, h6, p, span, div, label, .stMarkdown {color: #fff !important;}
  [data-testid="stMetric"] {background-color: #1e2130; padding: 20px; border-radius: 8px; height: 140px; display: flex; flex-direction: column; justify-content: space-between;}
  [data-testid="stMetricLabel"] {font-size: 14px !important; margin-bottom: 8px !important;}
  [data-testid="stMetricValue"] {font-size: 36px !important; font-weight: 600 !important; line-height: 1.2 !important;}
  [data-testid="stVerticalBlock"] > div[data-testid="stMetric"] {height: 140px !important;}
  button[kind="header"], [data-testid="collapsedControl"], button[data-testid="baseButton-header"] {background-color: #000 !important; color: #fff !important;}
  [data-testid="collapsedControl"] svg, [data-testid="stDataFrame"] svg {fill: #fff !important;}
  .stTextInput input {background-color: #1e2130; color: #fff; border: 1px solid #4a4a4a;}
  .stTextInput input::placeholder {color: #888;}   
  .stMultiSelect, .stMultiSelect [data-baseweb="select"] {background-color: #1e2130;}
  .stMultiSelect [data-baseweb="tag"] {background-color: #2d3748; color: #fff;}   
  .stDataFrame, [data-testid="stDataFrame"] {background-color: #1e2130; color: #fff;}
  [data-testid="stDataFrame"] button {background-color: #2d3748 !important; color: #fff !important; border: 1px solid #4a4a4a !important;}
  [data-testid="stDataFrame"] button:hover {background-color: #3d4758 !important;}
  .stDownloadButton button {background-color: #1e2130; color: #fff; border: 1px solid #4a4a4a;}
  .stDownloadButton button:hover {background-color: #2d3748; border-color: #fff;}  
  hr {border-color: #4a4a4a;}
  .stAlert {background-color: rgba(255, 182, 193, 0.15); backdrop-filter: blur(10px); color: #fff; border-left: 4px solid;}
  .element-container .stAlert[data-baseweb="notification"] > div {backdrop-filter: blur(10px);}
  div[data-baseweb="notification"] {background-color: rgba(255, 182, 193, 0.15) !important; backdrop-filter: blur(10px) !important;}
  .js-plotly-plot {background-color: #0e1117 !important;}
</style>
""", unsafe_allow_html=True)

st.title("COVID-19 Counties Data Quality Dashboard")
st.markdown("Comprehensive data quality analysis for the covid_counties dataset")

# Load the data
@st.cache_data
def load_data():
  try:
    df = pd.read_csv('dq_results.csv')
    return df
  except FileNotFoundError:
    st.error("Error: File not found.")
    st.stop()
df = load_data()

# Sidebar Filters
st.sidebar.header("Filters")
severity_filter = st.sidebar.multiselect(
  "Severity Level",
  options=df['severity'].unique(),
  default=df['severity'].unique()
)

status_filter = st.sidebar.multiselect(
  "Status",
  options=df['status'].unique(),
  default=df['status'].unique()
)

# Apply Filters
filtered_df = df[
  (df['severity'].isin(severity_filter)) & 
  (df['status'].isin(status_filter))
]

# Key Metrics
st.header("Key Metrics")
col1, col2, col3, col4, col5 = st.columns(5)
total_checks = len(df)
passed_checks = len(df[df['passed'] == True])
failed_checks = len(df[df['passed'] == False])
pass_rate = (passed_checks / total_checks * 100) if total_checks > 0 else 0
high_severity_fails = len(df[(df['severity'] == 'HIGH') & (df['passed'] == False)])

col1.metric("Total Checks", total_checks)
col2.metric("Passed", passed_checks, delta=f"{pass_rate:.1f}%")
col3.metric("Failed", failed_checks, delta=f"-{100-pass_rate:.1f}%", delta_color="inverse")
col4.metric("Pass Rate", f"{pass_rate:.1f}%")
col5.metric("High Severity Fails", high_severity_fails, delta_color="off")

st.divider()

# Row1: Overall Status and Severity Distribution
st.header("Overall Status")
row1_col1, row1_col2 = st.columns(2)

with row1_col1:
  st.subheader("Status Distribution")
  status_counts = df['status'].value_counts()
  fig_status = px.pie(
    values=status_counts.values,
    names=status_counts.index,
    color=status_counts.index,
    color_discrete_map={'PASS': '#28a745', 'FAIL': '#dc3545', 'ERROR': '#ffc107'},
    hole=0.4
  )
  fig_status.update_traces(textposition='inside', textinfo='percent+label')
  fig_status.update_layout(
    height=350,
    paper_bgcolor='#0e1117',
    plot_bgcolor='#0e1117',
    font=dict(color='#ffffff', size=14)
  )
  st.plotly_chart(fig_status, use_container_width=True)

with row1_col2:
  st.subheader("Severity Distribution")
  severity_counts = df['severity'].value_counts().reindex(['HIGH', 'MEDIUM', 'LOW'], fill_value=0)
  fig_severity = px.bar(
  x=severity_counts.index,
  y=severity_counts.values,
  color=severity_counts.index,
  color_discrete_map={'HIGH': '#dc3545', 'MEDIUM': '#ffc107', 'LOW': '#17a2b8'},
  labels={'x': 'Severity', 'y': 'Count'}
  )
  fig_severity.update_layout(
    showlegend=False,
    height=350,
    paper_bgcolor='#0e1117',
    plot_bgcolor='#0e1117',
    font=dict(color='#ffffff', size=14),
    xaxis=dict(gridcolor='#4a4a4a', tickfont=dict(color='#ffffff', size=12), title_font=dict(color='#ffffff', size=14)),
    yaxis=dict(gridcolor='#4a4a4a', tickfont=dict(color='#ffffff', size=12), title_font=dict(color='#ffffff', size=14))
  )
  st.plotly_chart(fig_severity, use_container_width=True)

st.divider()

# Row2: Failures by Severity
st.header("Failed Check Analysis")
failed_df = df[df['passed'] == False]

if len(failed_df) > 0:
  row2_col1, row2_col2 = st.columns([2.5, 1])
  with row2_col1:
    st.subheader("Failed Checks by Severity")
    severity_order = ['HIGH', 'MEDIUM', 'LOW']
    failed_by_severity = failed_df.groupby('severity').size().reindex(severity_order, fill_value=0)
    fig_fails = px.bar(
      x=failed_by_severity.index,
      y=failed_by_severity.values,
      color=failed_by_severity.index,
      color_discrete_map={'HIGH': '#dc3545', 'MEDIUM': '#ffc107', 'LOW': '#17a2b8'},
      labels={'x': 'Severity', 'y': 'Number of Failed Checks'},
      text=failed_by_severity.values
    )
    fig_fails.update_traces(textposition='outside', textfont=dict(size=14))
    fig_fails.update_layout(
      showlegend=False,
      height=420,
      paper_bgcolor='#0e1117',
      plot_bgcolor='#0e1117',
      font=dict(color='#ffffff', size=14),
      xaxis=dict(gridcolor='#4a4a4a', tickfont=dict(color='#ffffff', size=12), title_font=dict(color='#ffffff', size=14)),
      yaxis=dict(gridcolor='#4a4a4a', range=[0, failed_by_severity.max() * 1.15], tickfont=dict(color='#ffffff', size=12), title_font=dict(color='#ffffff', size=14))
    )
    st.plotly_chart(fig_fails, use_container_width=True)

  with row2_col2:
    st.subheader("Failure Summary")
    st.markdown("""
    <style>
      .compact-metric {
        background-color: #1e2130;
        padding: 12px;
        border-radius: 6px;
        margin-bottom: 10px;
      }
      .compact-metric .label {
        font-size: 13px;
        color: #aaaaaa;
        margin-bottom: 4px;
      }
      .compact-metric .value {
        font-size: 28px;
        font-weight: 600;
        color: #ffffff;
      }
      </style>
      """, unsafe_allow_html=True)
        
    st.markdown(f"""
      <div class="compact-metric">
        <div class="label">Total Failures</div>
        <div class="value">{len(failed_df)}</div>
      </div>
      <div class="compact-metric">
        <div class="label">HIGH Severity</div>
        <div class="value">{len(failed_df[failed_df['severity'] == 'HIGH'])}</div>
      </div>
      <div class="compact-metric">
        <div class="label">MEDIUM Severity</div>
        <div class="value">{len(failed_df[failed_df['severity'] == 'MEDIUM'])}</div>
      </div>
      <div class="compact-metric">
        <div class="label">LOW Severity</div>
        <div class="value">{len(failed_df[failed_df['severity'] == 'LOW'])}</div>
      </div>
      """, unsafe_allow_html=True)
        
    total_issues = failed_df['result_value'].sum()
    st.markdown(f"""
      <div class="compact-metric">
        <div class="label">Total Records Affected</div>
        <div class="value">{int(total_issues):,}</div>
      </div>
      """, unsafe_allow_html=True)

else:
  st.success("No failed checks!")

st.divider()

# Row3: Top Issues
st.header("Top Data Quality Issues")

if len(failed_df) > 0:
  top_issues = failed_df.nlargest(10, 'result_value')[['check_name', 'severity', 'result_value']]

  fig_top = px.bar(
    top_issues,
    x='result_value',
    y='check_name',
    color='severity',
    color_discrete_map={'HIGH': '#dc3545', 'MEDIUM': '#ffc107', 'LOW': '#17a2b8'},
    orientation='h',
    labels={'result_value': 'Number of Records Affected', 'check_name': 'Check Name'},
    text='result_value'
  )
  fig_top.update_traces(textposition='outside')
  fig_top.update_layout(
    height=500,
    paper_bgcolor='#0e1117',
    plot_bgcolor='#0e1117',
    font=dict(color='#ffffff', size=14),
    xaxis=dict(gridcolor='#4a4a4a', tickfont=dict(color='#ffffff', size=12), title_font=dict(color='#ffffff', size=14)),
    yaxis=dict(categoryorder='total ascending', gridcolor='#4a4a4a', tickfont=dict(color='#ffffff', size=11), title_font=dict(color='#ffffff', size=14)),
    legend=dict(font=dict(color='#ffffff', size=13), bgcolor='#0e1117')
  )
  st.plotly_chart(fig_top, use_container_width=True)
else:
  st.info("No issues to display!")

st.divider()

# Detailed Results Table:
st.header("Detailed Check Results")

# Add search functionality
search_term = st.text_input("Search checks", placeholder="Type to filter checks...")
if search_term:
  display_df = filtered_df[filtered_df['check_name'].str.contains(search_term, case=False)]
else:
  display_df = filtered_df

display_df_formatted = display_df.copy()
display_df_formatted['passed'] = display_df_formatted['passed'].map({True: '✅', False: '❌'})

# Color coding function
def highlight_status(row):
  if row['status'] == 'PASS':
    return ['background-color: #28a745; color: #ffffff'] * len(row)
  elif row['status'] == 'FAIL':
    if row['severity'] == 'HIGH':
      return ['background-color: #dc3545; color: #ffffff'] * len(row)
    else:
      return ['background-color: #ffc107; color: #ffffff'] * len(row)
  else:
    return ['color: #ffffff'] * len(row)

st.dataframe(
  display_df_formatted.style.apply(highlight_status, axis=1),
  use_container_width=True,
  height=400
)

# Download Button
st.download_button(
  label="📥 Download Full Results as CSV",
  data=df.to_csv(index=False).encode('utf-8'),
  file_name='dq_results_export.csv',
  mime='text/csv',
  use_container_width=True
)
st.divider()

#Summary
st.markdown('<p class="section-header">Summary</p>', unsafe_allow_html=True)

if high_severity_fails > 0:
  st.error(f"**URGENT**: {high_severity_fails} high-severity checks failed. These should be addressed immediately as they impact critical data fields.")

medium_severity_fails = len(df[(df['severity'] == 'MEDIUM') & (df['passed'] == False)])
if medium_severity_fails > 0:
  st.warning(f"**ATTENTION**: {medium_severity_fails} medium-severity checks failed. Review and address these issues to improve data quality.")