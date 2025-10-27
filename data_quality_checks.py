import os
import psycopg2
import pandas as pd
import re

DB_CONFIG = {
  'host' : os.getenv('DB_HOST', 'localhost'),
  'port' : os.getenv('DB_PORT', '5432'),
  'database' : os.getenv('DB_NAME', 'counties_db'),
  'user' : os.getenv('DB_USER', 'postgres'),
  'password' : os.getenv('DB_PASSWORD', 'Qazokn@123')
}

def load_selected_columns(file_path='selected_columns_for_dq.txt'):
  try:
    with open(file_path, 'r') as f:
      content =  f.read()

    match = re.search(r'SELECTED_COLUMNS\s*=\s*\[(.*?)\]', content, re.DOTALL)

    if not match:
      raise ValueError("Could not find Selected_Columns list in the file")
    
    columns_str = match.group(1)
    columns = re.findall(r"'([^']+)'", columns_str)
    print(f"Loaded {len(columns)} columns from {file_path}")
    return columns
  
  except FileNotFoundError:
    print(f"Error {file_path} not found")
    exit(1)
  except Exception as e:
    print(f"Error loading selected columns : {e}")
    exit(1)

def categorize_columns(columns):
  domain_keywords = {
    'identifiers': ['fips', 'area_name', 'state', 'county', 'matriculating', 'retained'],
    'population_base': ['pop_estimate', 'population', 'per_100000_population'],
    'demographics_vulnerable': ['age65', 'age85', 'age_65', 'age_85', 'elderly'],
    'healthcare_capacity': ['icu', 'hospital', 'physician', 'healthcare', 'patient_care'],
    'socioeconomic': ['income', 'poverty', 'pov', 'unemploy', 'employment'],
    'density_urbanization': ['density', 'urban', 'rural', 'area_in_square', 'square_mile']
  }

  categorized = {domain: [] for domain in domain_keywords.keys()}
  categorized['other'] = []

  for col in columns:
    col_lower = col.lower()
    matched = False

    for domain, keywords in domain_keywords.items():
      if any(keyword in col_lower for keyword in keywords):
        categorized[domain].append(col)
        matched = True
        break

    if not matched:
      categorized['other'].append(col)

  categorized = {k: v for k, v in categorized.items() if v}
  return categorized

print("Covid-19 NPI Analysis: Data Quality Checks")
ALL_SELECTED_COLUMNS = load_selected_columns()
SELECTED_COLUMNS = categorize_columns(ALL_SELECTED_COLUMNS)

dq_results = {
  'selected_columns_count' : len(ALL_SELECTED_COLUMNS),
  'total_columns_in_dataset' : 348,
  'coverage_percentage': round(len(ALL_SELECTED_COLUMNS)/348*100,2),
  'domains_covered': list(SELECTED_COLUMNS.keys()),
  'selected_columns': ALL_SELECTED_COLUMNS,
  'checks' : []
}

print(f"\n Total columns in dataset: {dq_results['total_columns_in_dataset']}")
print(f"Selected columns for DQ Checks: {dq_results['selected_columns_count']} ({dq_results['coverage_percentage']}%)")

def execute_check(cursor, check_name,sql_query, severity='HIGH', pass_condition='equals_zero'):
  try:
    cursor.execute(sql_query)
    result = cursor.fetchone()[0]

    if pass_condition == 'equals_zero':
      passed = (result == 0)
    elif pass_condition == 'greater_than_zero':
      passed = (result > 0)
    else:
      passed = False

    status = "PASS" if passed else "FAIL"
    check_result = {
      'check_name': check_name,
      'status': "PASS" if passed else "FAIL",
      'severity': severity,
      'result_value': result,
      'passed': passed,
      'sql_query': sql_query.strip()
    }

    dq_results['checks'].append(check_result)
    print(f" {status} | {severity:6s} | {check_name:60s} | Result: {result}")
    return passed,result
  
  except Exception as e:
    print(f"ERROR | {severity: 6s} | {check_name:60s} | Error: {str(e)}")
    dq_results['checks'].append({
      'check_name': check_name,
      'status': 'ERROR',
      'severity': severity,
      'result_value': None,
      'passed': False,
      'error': str(e),
      'sql_query': sql_query.strip()
    })
    return False, None
  
try:
  conn = psycopg2.connect(**DB_CONFIG)
  cursor = conn.cursor()
  print("\n Connected to PostgreSQL database\n")
except Exception as e:
  print(f"\n Database Connection failed: {e}")
  exit(1)

cursor.execute("SELECT COUNT(*) FROM covid_counties")
total_rows = cursor.fetchone()[0]
print(f"Total record in database: {total_rows:,}\n")

#Check1: Completeness (Critical Fields should not be NULL)
print("Data Quality Check 1: Completeness ")

if 'identifiers' in SELECTED_COLUMNS:
  for col in SELECTED_COLUMNS['identifiers']:
    severity = 'HIGH' if col in ['fips', 'area_name', 'state'] else 'MEDIUM'
    execute_check(cursor, f"{col} should not be NULL",  f"SELECT COUNT(*) FROM covid_counties WHERE {col} IS NULL", severity = severity)

if 'population_base' in SELECTED_COLUMNS:
  for col in SELECTED_COLUMNS['population_base']:
    severity = 'HIGH' if 'pop_estimate' in col else 'MEDIUM'
    execute_check(cursor, f"{col} should not be NULL", f"SELECT COUNT(*) FROM covid_counties WHERE {col} IS NULL", severity=severity)

if 'demographics_vulnerable' in SELECTED_COLUMNS:
  for col in SELECTED_COLUMNS['demographics_vulnerable']:
    severity = 'HIGH' if 'total_age65plus' in col else 'MEDIUM'
    execute_check(cursor, f"{col} should not be NULL",  f"SELECT COUNT(*) FROM covid_counties WHERE {col} IS NULL", severity = severity)

if 'healthcare_capacity' in SELECTED_COLUMNS:
  for col in SELECTED_COLUMNS['healthcare_capacity']:
    severity = 'HIGH' if col in ['icu_beds', 'total_hospitals_2019'] else 'MEDIUM'
    execute_check(cursor, f"{col} should not be NULL",  f"SELECT COUNT(*) FROM covid_counties WHERE {col} IS NULL", severity = severity)

if 'socioeconomic' in SELECTED_COLUMNS:
  for col in SELECTED_COLUMNS['socioeconomic']:
    severity = 'HIGH' if col in ['unemployment_rate_2018', 'median_household_income_2018'] else 'MEDIUM'
    execute_check(cursor, f"{col} should not be NULL", 
    f"SELECT COUNT(*) FROM covid_counties WHERE {col} IS NULL",
    severity=severity)

if 'density_urbanization' in SELECTED_COLUMNS:
  for col in SELECTED_COLUMNS['density_urbanization']:
    severity = 'HIGH' if col in ['density_per_square_mile_of_land_area_population', 'area_in_square_miles_land_area'] else 'MEDIUM'
    execute_check(cursor, f"{col} should not be NULL", 
    f"SELECT COUNT(*) FROM covid_counties WHERE {col} IS NULL",
    severity=severity)

#Check2: Uniqueness (Records should be unique)
print("Data Quality Check 2: Uniqueness")
if 'fips' in ALL_SELECTED_COLUMNS:
  execute_check(cursor, "No duplicate FIPS codes (primary key)", """SELECT COUNT(*) FROM (
        SELECT fips, COUNT(*) as cnt 
        FROM covid_counties 
        WHERE fips IS NOT NULL
        GROUP BY fips 
        HAVING COUNT(*) > 1
  ) duplicates""",severity='HIGH')

if 'area_name' in ALL_SELECTED_COLUMNS:
  execute_check(cursor, "No duplicate area names", 
    """SELECT COUNT(*) FROM (
       SELECT area_name, COUNT(*) as cnt 
       FROM covid_counties 
       WHERE area_name IS NOT NULL
       GROUP BY area_name 
       HAVING COUNT(*) > 1
  ) duplicates""",severity='MEDIUM')

#Check3: Conformity (Data should follow expected formats)
print("Data Quality Checks 3 : Conformity")
if 'fips' in ALL_SELECTED_COLUMNS:
  execute_check(cursor, "FIPS codes must be 5 digits (standard US format)", 
    """SELECT COUNT(*) 
       FROM covid_counties 
       WHERE fips IS NOT NULL 
       AND (LENGTH(fips::text) != 5 OR fips::text !~ '^[0-9]+$')""", severity='HIGH')

numeric_fields = ['pop_estimate_2018', 'icu_beds', 'total_hospitals_2019']
for col in numeric_fields:
  if col in ALL_SELECTED_COLUMNS:
    execute_check(cursor, f"{col} must be non-negative", 
    f"SELECT COUNT(*) FROM covid_counties WHERE {col} IS NOT NULL AND {col} < 0", severity='HIGH')

#Check4: Accuracy (Values should be reasonable and realistic)
print("Data Quality Checks: Accuracy")

if 'total_age65plus' in ALL_SELECTED_COLUMNS and 'pop_estimate_2018' in ALL_SELECTED_COLUMNS:
  execute_check(cursor, "Age 65+ cannot exceed total population", """SELECT COUNT(*) 
    FROM covid_counties 
    WHERE total_age65plus > pop_estimate_2018 
    AND total_age65plus IS NOT NULL 
    AND pop_estimate_2018 IS NOT NULL""",
    severity='HIGH')

if all(col in ALL_SELECTED_COLUMNS for col in ['male_age65plus', 'female_age65plus', 'total_age65plus']):
  execute_check(cursor, "Male + Female age 65+ should not exceed Total age 65+", """SELECT COUNT(*) 
    FROM covid_counties 
    WHERE (male_age65plus + female_age65plus) > total_age65plus * 1.01
    AND male_age65plus IS NOT NULL 
    AND female_age65plus IS NOT NULL 
    AND total_age65plus IS NOT NULL""",
    severity='MEDIUM')
    
if 'icu_beds' in ALL_SELECTED_COLUMNS and 'pop_estimate_2018' in ALL_SELECTED_COLUMNS:
  execute_check(cursor, "ICU beds cannot exceed population",
    """SELECT COUNT(*) 
    FROM covid_counties 
    WHERE icu_beds > pop_estimate_2018 
    AND icu_beds IS NOT NULL 
    AND pop_estimate_2018 IS NOT NULL""",
    severity='HIGH')

if 'total_hospitals_2019' in ALL_SELECTED_COLUMNS:
  execute_check(cursor, "Hospital count should be realistic (<1000 per county)",
    "SELECT COUNT(*) FROM covid_counties WHERE total_hospitals_2019 > 1000",
    severity='MEDIUM')
  
if 'unemployment_rate_2018' in ALL_SELECTED_COLUMNS:
  execute_check(cursor, "Unemployment rate must be between 0-100%", """SELECT COUNT(*) 
    FROM covid_counties 
    WHERE unemployment_rate_2018 IS NOT NULL 
    AND (unemployment_rate_2018 < 0 OR unemployment_rate_2018 > 100)""",
    severity='MEDIUM')
  
if 'pctpovall_2018' in ALL_SELECTED_COLUMNS:
  execute_check(cursor, "Poverty rate must be between 0-100%", """SELECT COUNT(*) 
    FROM covid_counties 
    WHERE pctpovall_2018 IS NOT NULL 
    AND (pctpovall_2018 < 0 OR pctpovall_2018 > 100)""",
    severity='MEDIUM')
  
fraction_cols = [col for col in ALL_SELECTED_COLUMNS if 'fraction_of_' in col]
for col in fraction_cols:
  execute_check(cursor, f"{col} must be between 0-1", 
    f"""SELECT COUNT(*) 
    FROM covid_counties 
    WHERE {col} IS NOT NULL 
    AND ({col} < 0 OR {col} > 1)""",
    severity='MEDIUM')
  
if 'median_household_income_2018' in ALL_SELECTED_COLUMNS:
  execute_check(cursor, "Median income should be realistic (>$10,000)", """SELECT COUNT(*) 
    FROM covid_counties 
    WHERE median_household_income_2018 IS NOT NULL 
    AND median_household_income_2018 < 10000""",
    severity='MEDIUM')

#Check5: Integrity - Relationships between fields should be valid
print("Data Quality Checks: Integrity")
if all(col in ALL_SELECTED_COLUMNS for col in ['male_age65plus', 'female_age65plus', 'total_age65plus']):
  execute_check(cursor, "Male + Female age 65+ should equal Total age 65+ (±10)",
    """SELECT COUNT(*) 
    FROM covid_counties 
    WHERE male_age65plus IS NOT NULL 
    AND female_age65plus IS NOT NULL 
    AND total_age65plus IS NOT NULL
    AND ABS((male_age65plus + female_age65plus) - total_age65plus) > 10""",
    severity='MEDIUM')
  
if all(col in ALL_SELECTED_COLUMNS for col in ['total_age85plusr', 'total_age65plus']):
  execute_check(cursor, "Age 85+ should be subset of Age 65+ population",
    """SELECT COUNT(*) 
    FROM covid_counties 
    WHERE total_age85plusr > total_age65plus 
    AND total_age85plusr IS NOT NULL 
    AND total_age65plus IS NOT NULL""",
    severity='HIGH')
  
#Check6: Consistency - Related values should be logically consistent
print("Data Quality Checks: Consistency")

if all(col in ALL_SELECTED_COLUMNS for col in ['density_per_square_mile_of_land_area_population','pop_estimate_2018', 'area_in_square_miles_land_area']):
  execute_check(cursor, "Population density consistent with pop/land area (±1)",
    """SELECT COUNT(*) 
    FROM covid_counties 
    WHERE pop_estimate_2018 IS NOT NULL 
    AND area_in_square_miles_land_area IS NOT NULL 
    AND area_in_square_miles_land_area > 0
    AND density_per_square_mile_of_land_area_population IS NOT NULL
    AND ABS(density_per_square_mile_of_land_area_population - 
      (pop_estimate_2018::float /area_in_square_miles_land_area)) > 1""",
    severity='LOW')

#Check7: Validity - Values should be acceptable
print("Data Quality Checks : Validity")

if 'area_in_square_miles_land_area' in ALL_SELECTED_COLUMNS:
  execute_check(cursor, "Land area must be positive", 
    """SELECT COUNT(*) 
    FROM covid_counties 
    WHERE area_in_square_miles_land_area IS NOT NULL 
    AND area_in_square_miles_land_area <= 0""",
    severity='HIGH')

if 'median_household_income_2018' in ALL_SELECTED_COLUMNS:
  execute_check(cursor, "Median income must be positive",
    """SELECT COUNT(*) 
    FROM covid_counties 
    WHERE median_household_income_2018 IS NOT NULL 
    AND median_household_income_2018 <= 0""",
    severity='MEDIUM')

print("Data Quality Check Summary")
total_checks = len(dq_results['checks'])
passed_checks = sum(1 for check in dq_results['checks'] if check['passed'])
failed_checks = total_checks - passed_checks
pass_rate = (passed_checks/total_checks * 100) if total_checks > 0 else 0

print(f"\nTotal Checks Run: {total_checks}")
print(f"Passed: {passed_checks} ({pass_rate:.1f}%)")
print(f"Failed: {failed_checks} ({100-pass_rate:.1f}%)")

df_results = pd.DataFrame(dq_results['checks'])
visualisations_columns = ['check_name', 'status', 'severity', 'result_value', 'passed']
df_visualisation = df_results[visualisations_columns]
df_visualisation.to_csv('dq_results.csv',index=False)
cursor.close()
conn.close()