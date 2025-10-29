import os
import psycopg2

DB_CONFIG = {
  'host' : os.getenv('DB_HOST', 'localhost'),
  'port' : os.getenv('DB_PORT', '5432'),
  'database' : os.getenv('DB_NAME', 'counties_db'),
  'user' : os.getenv('DB_USER', 'postgres'),
  'password': os.getenv('DB_PASSWORD', 'Qazokn@123')
}

def create_cleaned_table():
  conn = psycopg2.connect(**DB_CONFIG)
  cursor = conn.cursor()

  print("Creating a copy of the original table \n")
  cursor.execute("DROP TABLE IF EXISTS covid_counties_cleaned CASCADE;")
  cursor.execute("CREATE TABLE covid_counties_cleaned AS SELECT * FROM covid_counties;")
  cursor.execute("SELECT COUNT(*) FROM covid_counties_cleaned")
  initial_count = cursor.fetchone()[0]
  print(f"Created table with {initial_count:,} rows")

  print("Filling Completeness-High Severity Fails with average values\n")

  high_severity_fields = [
    'total_age65plus',
    'total_hospitals_2019',
    'icu_beds',
    'unemployment_rate_2018',
    'median_household_income_2018',
    'area_in_square_miles_land_area'
  ]
  for field in high_severity_fields:
    cursor.execute(f"""
      SELECT COUNT(*)
      FROM information_schema.columns
      WHERE table_name = 'covid_counties_cleaned'
      AND column_name = '{field}'
    """)
    if cursor.fetchone()[0] > 0:
      cursor.execute(f"SELECT COUNT(*) FROM covid_counties_cleaned WHERE {field} IS NULL")
      null_values_before = cursor.fetchone()[0]

      if null_values_before > 0:
        cursor.execute(f"""
          UPDATE covid_counties_cleaned AS c1
            SET {field} = (
              SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {field})
              FROM covid_counties_cleaned AS c2
              WHERE c2.state = c1.state
              AND c2.{field} IS NOT NULL
            )
            WHERE {field} IS NULL
        """)
        cursor.execute(f"SELECT COUNT(*) FROM covid_counties_cleaned WHERE {field} IS NULL")
        nulls_after_state_median = cursor.fetchone()[0]
        filled_with_state_median = null_values_before - nulls_after_state_median

        cursor.execute(f"""
          UPDATE covid_counties_cleaned
            SET {field} = (
              SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {field})
              FROM covid_counties_cleaned
              WHERE {field} IS NOT NULL
            )
            WHERE {field} IS NULL
        """)

        cursor.execute(f"SELECT COUNT(*) FROM covid_counties_cleaned WHERE {field} IS NULL")
        null_values_after = cursor.fetchone()[0]
        filled_with_national_median = nulls_after_state_median - null_values_after

        print(f" {field} : {null_values_before} NULLs -> {null_values_after} NULLs")
        print(f"{filled_with_state_median} filled with state avg")
        print(f"{filled_with_national_median} filled with national avg")
  
  print("Filling Completeness - Medium severity Fails with 0\n")

  medium_severity_fields = [
    'med_hh_income_percent_of_state_total_2018',
    'fraction_of_md_students_matriculating_in_state_ay_2018_2019_',
    'fraction_of_physicians_retained_in_state_from_undergraduate_',
    'density_per_square_mile_of_land_area_population',
    'active_physicians_per_100000_population_2018_aamc',
    'total_active_patient_care_physicians_per_100000_population_2',
    'active_primary_care_physicians_per_100000_population_2018_aa',
    'male_age65plus',
    'female_age65plus',
    'total_age85plusr',
    'male_age85plusr',
    'total_physician_assistants_2019',
    'fraction_of_active_physicians_who_are_female_2018_aamc',
    'fraction_of_active_physicians_who_are_international_medical_',
    'fraction_of_active_physicians_who_are_age_60_or_older_2018_a',
    'active_patient_care_primary_care_physicians_per_100000_popul',
    'total_specialist_physicians_2019',
    'total_primary_care_physicians_2019',
    'pctpovall_2018',
    'density_per_square_mile_of_land_area_housing_units',
    'area_in_square_miles_water_area'
  ]

  for field in medium_severity_fields:
    cursor.execute(f"""
      SELECT COUNT(*) 
      FROM information_schema.columns 
      WHERE table_name = 'covid_counties_cleaned' 
      AND column_name = '{field}'
    """) 

    if cursor.fetchone()[0] > 0:
      cursor.execute(f"SELECT COUNT(*) FROM covid_counties_cleaned WHERE {field} IS NULL")
      nulls_values_before = cursor.fetchone()[0]

      if nulls_values_before > 0:
        cursor.execute(f"""
          UPDATE covid_counties_cleaned AS c1
            SET {field} = (
              SELECT AVG({field})
              FROM covid_counties_cleaned AS c2
              WHERE c2.state = c1.state
              AND c2.{field} IS NOT NULL
            )
            WHERE {field} IS NULL
        """)

        cursor.execute(f"SELECT COUNT(*) FROM covid_counties_cleaned WHERE {field} IS NULL")
        nulls_after_state = cursor.fetchone()[0]
        filled_with_state = nulls_values_before - nulls_after_state

        cursor.execute(f"""
          UPDATE covid_counties_cleaned
            SET {field} = (
              SELECT AVG({field})
              FROM covid_counties_cleaned
              WHERE {field} IS NOT NULL
            )
            WHERE {field} IS NULL
        """)

        cursor.execute(f"SELECT COUNT(*) FROM covid_counties_cleaned WHERE {field} IS NULL")
        nulls_values_after = cursor.fetchone()[0]
        filled_with_national = nulls_after_state - nulls_values_after

        print(f"  {field}: {nulls_values_before} NULLs -> {nulls_values_after} NULLs")
        print(f"{filled_with_state} filled with state avg")
        print(f"{filled_with_national} filled with national avg")
   
  conn.commit()
  print("Summary")
  cursor.execute("SELECT COUNT(*) FROM covid_counties")
  original_count = cursor.fetchone()[0]
  cursor.execute("SELECT COUNT(*) FROM covid_counties_cleaned")
  final_count = cursor.fetchone()[0]
  print(f"Original table rows: {original_count:,}\n")
  print(f"Cleaned table rows:  {final_count:,}\n")

  cursor.close()
  conn.close()

if __name__ == "__main__":
  try:
    create_cleaned_table()
  except Exception as e:
    print(f"Error: {e}")
    exit(1)