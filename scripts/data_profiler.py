import os
import psycopg2
import pandas as pd

DB_CONFIG = {
  'host': os.getenv('DB_HOST', 'localhost'),
  'port': os.getenv('DB_PORT', '5432'),
  'database': os.getenv('DB_NAME', 'counties_db'),
  'user': os.getenv('DB_USER', 'postgres'),
  'password': os.getenv('DB_PASSWORD', 'Qazokn@123')
}

LOCKED_FILE = "/mnt/dq_persistent/selected_columns_for_dq.txt"

#Domains suited for dataset
ANALYTICAL_DOMAINS = {
  'identifiers': {
    'keywords': ['fips', 'state', 'county', 'area_name'],
    'required': True,
    'max_null_pct': 1,
    'reason': 'Geographic identification for county-level analysis'
  },
  'population_base': {
    'keywords': ['pop_estimate', 'population_2018'],
    'required': True,
    'max_null_pct': 1,
    'reason': 'Foundation for calculating rates and per-capita metrics'
  },
  'demographics_vulnerable': {
    'keywords': ['age65plus', 'age_65', 'elderly', 'age85plus'],
    'required': True,
    'max_null_pct': 10,
    'reason': 'COVID-19 high-risk populations for outcome prediction'
  },
  'healthcare_capacity': {
    'keywords': ['icu', 'hospital', 'physician', 'healthcare'],
    'required': True,
    'max_null_pct': 10,
    'reason': 'Healthcare system capacity affects disease consequences'
  },
  'socioeconomic': {
    'keywords': ['income', 'poverty', 'pov', 'unemploy', 'employment'],
    'required': True,
    'max_null_pct': 10,
    'reason': 'Socioeconomic factors affecting NPI compliance and spread'
  },
  'density_urbanization': {
    'keywords': ['density', 'urban', 'rural', 'area_in_square'],
    'required': True,
    'max_null_pct': 10,
    'reason': 'Population density affects disease transmission dynamics'
  },
  'education': {
    'keywords': ['education', 'diploma', 'bachelor', 'degree', 'school'],
    'required': False,
    'max_null_pct': 5,
    'reason': 'Education level may correlate with NPI adherence'
  },
  'demographics_gender': {
    'keywords': ['tot_male', 'tot_female', 'total_male', 'total_female'],
    'required': False,
    'max_null_pct': 10,
    'reason': 'Gender demographics for stratified analysis'
  }
}

print(" Data Profiler for COVID-19 NPI Analysis")

if os.path.exists(LOCKED_FILE):
  print(f"   Using existing column selection from: {LOCKED_FILE}")
  with open(LOCKED_FILE, 'r') as f:
    content = f.read()
  print(content)
  exit(0)

# Connect to database
conn = psycopg2.connect(**DB_CONFIG)
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM covid_counties_2")
total_rows = cursor.fetchone()[0]
print(f"\nTotal records: {total_rows:,}")

cursor.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns 
    WHERE table_name = 'covid_counties_2'
    AND column_name NOT IN ('id', 'input_date')
    ORDER BY ordinal_position
""")
columns_info = cursor.fetchall()
print(f"Total columns: {len(columns_info)}")

print("Scoring each column based on: relevance + data quality + analytical value\n")

scored_columns = []

for col_name, data_type in columns_info:
  try:
    # Get statistics
    cursor.execute(f"""
      SELECT 
        COUNT(*) - COUNT({col_name}) as null_count,
        ROUND(((COUNT(*) - COUNT({col_name}))::numeric / COUNT(*)) * 100, 2) as null_pct,
        COUNT(DISTINCT {col_name}) as unique_count
        FROM covid_counties_2
    """)
    null_count, null_pct, unique_count = cursor.fetchone()
    null_pct = float(null_pct) if null_pct else 0
    uniqueness_ratio = unique_count / total_rows if total_rows > 0 else 0
        
    # Scoring Algorithm
    score = 0
    matched_domain = None
    relevance_reason = []
        
    col_lower = col_name.lower()
        
    # Score 1: Domain Relevance 
    for domain, config in ANALYTICAL_DOMAINS.items():
      if any(keyword in col_lower for keyword in config['keywords']):
        if config['required']:
          score += 100  
        else:
          score += 50   
        matched_domain = domain
        relevance_reason.append(f"Matches {domain}")
        break
        
    # Score 2: Data Quality 
    if null_pct == 0:
      score += 30
      relevance_reason.append("Fully populated")
    elif null_pct < 5:
      score += 25
      relevance_reason.append("Well populated")
    elif null_pct < 15:
      score += 15
      relevance_reason.append("Moderately populated")
    elif null_pct < 50:
      score += 5
      relevance_reason.append("Sparse but usable")
    else:
      score -= 20  
      relevance_reason.append("Too sparse")
        
    # Score 3: Analytical Value 
    if uniqueness_ratio > 0.99:
      score += 20  # Identifiers are critical
      relevance_reason.append("Unique identifier")
    elif uniqueness_ratio < 0.01:
      score -= 10  # Nearly constant columns are useless
      relevance_reason.append("Nearly constant")
    elif data_type in ('integer', 'numeric', 'double precision'):
      score += 10  # Numeric columns useful for modeling
      relevance_reason.append("Numeric - model-ready")
        
    # Score 4: Bonus for specific high-value columns
    high_value_terms = ['icu', 'hospital', 'physician', 'poverty', 'income', 'age65', 'density', 'unemployment']
    if any(term in col_lower for term in high_value_terms):
      score += 15
      relevance_reason.append("High analytical value")
        
    # Score 5: Penalty for irrelevant domains
    irrelevant_terms = ['temp_', 'precipitation', 'crime', 'marital', 'veteran', 'transit_score']
    if any(term in col_lower for term in irrelevant_terms):
      score -= 30
      relevance_reason.append("Low relevance to COVID NPIs")
        
    scored_columns.append({
      'column_name': col_name,
      'score': score,
      'null_pct': null_pct,
      'unique_pct': uniqueness_ratio * 100,
      'data_type': data_type,
      'domain': matched_domain or 'OTHER',
      'reason': ' | '.join(relevance_reason)
    })
        
  except Exception as e:
    print(f" Error scoring {col_name}: {e}")

df_scored = pd.DataFrame(scored_columns)
df_scored = df_scored.sort_values('score', ascending=False) #sort by score

# Select top columns ensuring required domains are included
selected_columns = []
domain_counts = {}

for domain, config in ANALYTICAL_DOMAINS.items():
  if config['required']:
    domain_cols = df_scored[
      (df_scored['domain'] == domain) & 
      (df_scored['null_pct'] <= config['max_null_pct'])
    ].head(2)  # Take top 2 from each required domain
        
    for _, col in domain_cols.iterrows():
      if col['column_name'] not in [c['column_name'] for c in selected_columns]:
        selected_columns.append(col.to_dict())
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

remaining_slots = 30 - len(selected_columns)
for _, col in df_scored.head(50).iterrows():  # Check top 50 scored and selects remaining cols accordingly
  if len(selected_columns) >= 30:
    break
  if col['column_name'] not in [c['column_name'] for c in selected_columns]:
    selected_columns.append(col.to_dict())
    domain_counts[col['domain']] = domain_counts.get(col['domain'], 0) + 1

# Sort selected columns by score
selected_columns = sorted(selected_columns, key=lambda x: x['score'], reverse=True)

print(f" SELECTED COLUMNS ({len(selected_columns)} columns)")
print("These columns are automatically selected as most relevant for COVID NPI analysis:\n")

print(f"{'Column Name':50s} | {'Domain':25s} | {'Score':>5s} | {'NULL%':>6s} | Reason")

for col in selected_columns:
  print(f"{col['column_name']:50s} | {col['domain']:25s} | {col['score']:>5.0f} | {col['null_pct']:>5.1f}% | {col['reason']}")

# Domain distribution
print("SELECTED COLUMNS BY ANALYTICAL DOMAIN")
print(f"\n{'Domain':30s} | {'Count':>6s} | Purpose")

for domain, config in ANALYTICAL_DOMAINS.items():
  count = domain_counts.get(domain, 0)
  print(f" {domain:28s} | {count:>6d} | {config['reason']}")

selected_col_names = [col['column_name'] for col in selected_columns]

# Save as Python list for DQ script
output_dir = "/mnt/dq_persistent"
os.makedirs(output_dir, exist_ok=True)

with open(LOCKED_FILE, 'w') as f:
  f.write("# Auto-selected columns for COVID-19 NPI Data Quality Checks\n")
  f.write(f"# Generated: {pd.Timestamp.now()}\n")
  f.write(f"# Total selected: {len(selected_col_names)} out of 348\n\n")
  f.write("SELECTED_COLUMNS = [\n")
  for col in selected_col_names:
    f.write(f"    '{col}',\n")
  f.write("]\n\n")
    
  f.write("# Domain breakdown:\n")
  for domain, count in domain_counts.items():
    f.write(f"# {domain}: {count} columns\n")

print(f"\n Selected columns saved to: {LOCKED_FILE}")

print("Data Profiling Completed")

cursor.close()
conn.close()
