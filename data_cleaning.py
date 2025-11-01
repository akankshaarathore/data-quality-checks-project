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

  cursor.execute("""
    SELECT EXISTS (
      SELECT FROM information_schema.tables 
      WHERE table_name = 'covid_counties_cleaned'
    )
  """)
  table_exists = cursor.fetchone()[0]
  if table_exists:
    print("Table covid_counties_cleaned already exists\n")

    cursor.execute("""
      SELECT column_name 
      FROM information_schema.columns 
      WHERE table_name = 'covid_counties'
      AND column_name NOT IN (
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'covid_counties_cleaned'
      )
    """)
    new_columns = cursor.fetchall()
    if new_columns:
      for col in new_columns:
        col_name = col[0]
        cursor.execute(f"""
          SELECT data_type 
          FROM information_schema.columns 
          WHERE table_name = 'covid_counties' 
          AND column_name = '{col_name}'
        """)
        col_type = cursor.fetchone()[0]

        cursor.execute(f"""
          ALTER TABLE covid_counties_cleaned 
          ADD COLUMN IF NOT EXISTS {col_name} {col_type}
        """)
        print(f"Added column: {col_name} ({col_type})")
      
      conn.commit()

     #deleting rows removed from source
    cursor.execute("""   
      DELETE FROM covid_counties_cleaned
      WHERE fips NOT IN (SELECT fips FROM covid_counties WHERE fips IS NOT NULL)
      AND fips IS NOT NULL
    """)
    deleted_count = cursor.rowcount
    conn.commit();
    if deleted_count > 0:
      print(f" Deleted {deleted_count} rows removed from source")
    #insert new rows from source
    cursor.execute("""
      SELECT column_name 
      FROM information_schema.columns 
      WHERE table_name = 'covid_counties'
      ORDER BY ordinal_position
    """)
    common_columns = [row[0] for row in cursor.fetchall()]
    columns_str = ', '.join([f'src.{col}' for col in common_columns])
    columns_list = ', '.join(common_columns)

    cursor.execute(f"""
      INSERT INTO covid_counties_cleaned ({columns_list}, is_cleaned)
      SELECT {columns_str}, FALSE
      FROM covid_counties src
      LEFT JOIN covid_counties_cleaned cln ON src.fips = cln.fips
      WHERE cln.fips IS NULL AND src.fips IS NOT NULL
    """)
    new_rows_from_source = cursor.rowcount
    if new_rows_from_source > 0:
      cursor.execute("""
        UPDATE covid_counties_cleaned
        SET is_cleaned = FALSE
        WHERE is_cleaned IS NULL
      """)
      print(f" Inserted {new_rows_from_source} new rows from source")
    #checks for manually inserted rows
    cursor.execute("""
      SELECT COUNT(*)
      FROM covid_counties_cleaned cln
      WHERE (cln.is_cleaned = FALSE OR cln.is_cleaned IS NULL)
    """)
    uncleaned_rows = cursor.fetchone()[0]
    if new_rows_from_source==0 and uncleaned_rows == 0:
      print(" No uncleaned rows found, all data is clean!")
      cursor.execute("SELECT COUNT(*) FROM covid_counties_cleaned")
      final_count = cursor.fetchone()[0]
      print(f"\n Total rows in cleaned table: {final_count:,}")
      cursor.close()
      conn.close()
      return
    
    print(f"\nFound {uncleaned_rows} uncleaned rows")

  else:
    print("Creating a copy of the original table \n")
    cursor.execute("CREATE TABLE covid_counties_cleaned AS SELECT * FROM covid_counties;")
    cursor.execute("""
      ALTER TABLE covid_counties_cleaned 
      ADD COLUMN is_cleaned BOOLEAN DEFAULT FALSE
    """)
    cursor.execute("SELECT COUNT(*) FROM covid_counties_cleaned")
    initial_count = cursor.fetchone()[0]
    print(f"Created table with {initial_count:,} rows")
  conn.commit()

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

  print("Fixing Consistency - Recalculating popultion density\n")
  cursor.execute("""
    SELECT COUNT(*)
    FROM covid_counties_cleaned 
    WHERE pop_estimate_2018 IS NOT NULL 
    AND area_in_square_miles_land_area IS NOT NULL 
    AND area_in_square_miles_land_area > 0
    AND density_per_square_mile_of_land_area_population IS NOT NULL
    AND ABS(density_per_square_mile_of_land_area_population - 
    (pop_estimate_2018::float/area_in_square_miles_land_area)) > 1
  """)
  inconsistent_count = cursor.fetchone()[0]
  if inconsistent_count > 0:
    print(f"Found {inconsistent_count} rows with inconsistent population density")
    cursor.execute("""
      UPDATE covid_counties_cleaned
      SET density_per_square_mile_of_land_area_population = 
        ROUND((pop_estimate_2018::float / area_in_square_miles_land_area)::numeric, 2)
      WHERE pop_estimate_2018 IS NOT NULL 
      AND area_in_square_miles_land_area IS NOT NULL
      AND area_in_square_miles_land_area > 0
      AND density_per_square_mile_of_land_area_population IS NOT NULL
      AND ABS(density_per_square_mile_of_land_area_population - (pop_estimate_2018::float/area_in_square_miles_land_area)) > 1
    """)
    updated_count = cursor.rowcount

    cursor.execute("""
      SELECT COUNT(*) 
      FROM covid_counties_cleaned 
      WHERE pop_estimate_2018 IS NOT NULL 
      AND area_in_square_miles_land_area IS NOT NULL 
      AND area_in_square_miles_land_area > 0
      AND density_per_square_mile_of_land_area_population IS NOT NULL
      AND ABS(density_per_square_mile_of_land_area_population - 
        (pop_estimate_2018::float / area_in_square_miles_land_area)) > 1
    """)
    remaining_inconsistent = cursor.fetchone()[0]
    print(f"Recalculated density for {updated_count} rows")
    print(f"Inconsistent rows: {inconsistent_count} -> {remaining_inconsistent}")
  else:
    print("No inconsistent density values found")

  cursor.execute("""
    UPDATE covid_counties_cleaned
    SET is_cleaned = TRUE
    WHERE is_cleaned = FALSE OR is_cleaned IS NULL
  """)
  marked_count = cursor.rowcount
  print(f" Marked {marked_count} rows as cleaned")

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