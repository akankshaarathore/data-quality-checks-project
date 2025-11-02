import os
import re
import pandas as pd
import psycopg2
import glob
from datetime import datetime

DB_CONFIG = {
  'host': os.getenv('DB_HOST', 'localhost'),
  'port': os.getenv('DB_PORT', '5432'),
  'database': os.getenv('DB_NAME', 'counties_db'),
  'user': os.getenv('DB_USER', 'postgres'),
  'password': os.getenv('DB_PASSWORD', 'Qazokn@123')
}

SPLIT_FILES_PATH = "data/split_files/counties_*.csv"
UNIQUE_COL = 'fips'

print("Ingestion Pipeline Started")

print("Connecting to PostgreSQL")
try:
  conn = psycopg2.connect(**DB_CONFIG)
  cursor = conn.cursor()
  cursor.execute("SELECT version();")
  version = cursor.fetchone()[0]
  print("Connected to PostgreSQL")
  print(f"Version: {version.split(',')[0]}")
except Exception as e:
  print(f"Database Connection Failed: {e}")
  exit(1)

print("Scanning for CSV Files\n")
csv_files = sorted(glob.glob(SPLIT_FILES_PATH))
if not csv_files:
  print(f"No CSV files found at: {SPLIT_FILES_PATH}")
  cursor.close()
  conn.close()
  exit(1)
print(f"Found {len(csv_files)} CSV Files:")
for f in csv_files:
  print(f"{os.path.basename(f)}")

print("\nExtracting dates from filenames\n")
file_dates = {}
for file_path in csv_files:
  try:
    base = os.path.basename(file_path)
    date_str = base.replace('counties_', '').replace('.csv', '')
    date = pd.to_datetime(date_str).date()
    file_dates[file_path] = date
    print(f"{os.path.basename(file_path)} -> {date}")
  except:
    print(f"Could not extract date from {os.path.basename(file_path)}")
if not file_dates:
  print("No valid dates found in filenames")
  cursor.close()
  conn.close()
  exit(1)

print("\nChecking table existence\n")
cursor.execute("""
  SELECT EXISTS(
    SELECT FROM information_schema.tables 
    WHERE table_name = 'covid_counties_2'
  )
""")
table_exists = cursor.fetchone()[0]
if table_exists:
  print("Table 'covid_counties_2' exists\n")  
  print("Checking already ingested data\n")
  cursor.execute("SELECT DISTINCT data_date FROM covid_counties_2 ORDER BY data_date")
  ingested_dates = [pd.to_datetime(row[0]).date() if isinstance(row[0], str) else row[0] for row in cursor.fetchall()]
  
  if ingested_dates:
    print(f"Found {len(ingested_dates)} already ingested dates:")
    for date in ingested_dates:
      print(f"{date}")  
    pending_dates = [date for date in file_dates.values() if date not in ingested_dates]
    
    if not pending_dates:
      print("\nAll files already ingested\n")
      cursor.execute("SELECT COUNT(*) FROM covid_counties_2")
      total_rows = cursor.fetchone()[0]
      cursor.execute(f"SELECT COUNT(DISTINCT {UNIQUE_COL}) FROM covid_counties_2")
      distinct_fips = cursor.fetchone()[0]      
      print(f"Total rows: {total_rows:,}")
      print(f"Unique fips: {distinct_fips:,}")      
      cursor.close()
      conn.close()
      print("\nDatabase connection closed")
      print("Pipeline Completed")
      exit(0)
    else:
      print(f"\nFound {len(pending_dates)} new dates to process:")
      for date in pending_dates:
        print(f"{date}")
      csv_files = [f for f, d in file_dates.items() if d in pending_dates]
  else:
    print("No data ingested yet\n")
    ingested_dates = []
else:
  print("Table 'covid_counties_2' does not exist\n")
  ingested_dates = []

print("\nReading first CSV to determine schema\n")
first_file = csv_files[0]
df_schema = pd.read_csv(first_file, nrows=5)
print(f"Sample file: {os.path.basename(first_file)}")
print(f"Columns found: {len(df_schema.columns)}\n")

print("Cleaning column names\n")
cleaned_columns = []
for col in df_schema.columns:
  clean_col = re.sub(r"[^a-z0-9_]", "",
    col.lower().replace(' ', '_')
      .replace('-', '_')
      .replace('.', '_')
      .replace('(', '')
      .replace(')', '')
      .replace('/', '_')
      .replace('%', 'pct')
  )
  clean_col = re.sub(r'_+', '_', clean_col).strip('_')
  if len(clean_col) > 60:
    clean_col = clean_col[:60]
  original_clean_col = clean_col
  counter = 1
  while clean_col in cleaned_columns:
    clean_col = f"{original_clean_col}_{counter}"
    counter += 1
  cleaned_columns.append(clean_col)
df_schema.columns = cleaned_columns
print(f"Cleaned {len(cleaned_columns)} column names\n")

if table_exists:
  print("Checking for schema changes\n")
  cursor.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'covid_counties_2'
  """)
  existing_cols = {row[0] for row in cursor.fetchall()}
  
  new_cols = [col for col in df_schema.columns if col not in existing_cols]
  
  if new_cols:
    print(f"Found {len(new_cols)} new columns to add\n")
    for col in new_cols:
      dtype = df_schema[col].dtype
      if dtype == 'int64':
        sql_type = 'INTEGER'
      elif dtype == 'float64':
        sql_type = 'NUMERIC'
      elif dtype == 'bool':
        sql_type = 'BOOLEAN'
      elif dtype == 'datetime64[ns]':
        sql_type = 'TIMESTAMP'
      else:
        sql_type = 'TEXT'
      cursor.execute(f"ALTER TABLE covid_counties_2 ADD COLUMN IF NOT EXISTS {col} {sql_type}")
      print(f"Added column: {col} ({sql_type})")
    conn.commit()
  else:
    print("No new columns to add\n")
else:
  print("Creating new table\n")
  create_columns = []
  for col in df_schema.columns:
    dtype = df_schema[col].dtype
    if dtype == 'int64':
      sql_type = 'INTEGER'
    elif dtype == 'float64':
      sql_type = 'NUMERIC'
    elif dtype == 'bool':
      sql_type = 'BOOLEAN'
    elif dtype == 'datetime64[ns]':
      sql_type = 'TIMESTAMP'
    else:
      sql_type = 'TEXT'
    create_columns.append(f"{col} {sql_type}")
  
  create_table_sql = f"""
    CREATE TABLE covid_counties_2 (
      id SERIAL PRIMARY KEY,
      {', '.join(create_columns)}
    )
  """
  cursor.execute(create_table_sql)
  conn.commit()
  print(f"Created table 'covid_counties_2' with {len(create_columns)} columns\n")

print(f"Creating unique index on '{UNIQUE_COL}'\n")
cursor.execute(f"""
  CREATE UNIQUE INDEX IF NOT EXISTS idx_{UNIQUE_COL}
  ON covid_counties_2 ({UNIQUE_COL})
""")
conn.commit()
print(f"Unique index exists on column: {UNIQUE_COL}\n")

print(f"Fetching existing {UNIQUE_COL} codes\n")
cursor.execute(f"SELECT {UNIQUE_COL} FROM covid_counties_2")
existing_fips = {row[0] for row in cursor.fetchall()}
print(f"Found {len(existing_fips):,} existing fips codes in database\n")

print("Processing Files\n")
total_files_processed = 0
total_files_skipped = 0
total_rows_inserted = 0
total_rows_skipped = 0

for file_path in csv_files:
  file_name = os.path.basename(file_path)
  print(f"Processing: {file_name}\n")  
  try:
    df = pd.read_csv(file_path)
    print(f"Rows in file: {len(df):,}\n")    
    cleaned_columns = []
    for col in df.columns:
      clean_col = re.sub(r"[^a-z0-9_]", "",
        col.lower().replace(' ', '_')
          .replace('-', '_')
          .replace('.', '_')
          .replace('(', '')
          .replace(')', '')
          .replace('/', '_')
          .replace('%', 'pct')
      )
      clean_col = re.sub(r'_+', '_', clean_col).strip('_')
      if len(clean_col) > 60:
        clean_col = clean_col[:60]
      original_clean_col = clean_col
      counter = 1
      while clean_col in cleaned_columns:
        clean_col = f"{original_clean_col}_{counter}"
        counter += 1
      cleaned_columns.append(clean_col) 

    df.columns = cleaned_columns    

    if 'data_date' not in df.columns:
      print(f"Error: 'data_date' column not found - skipping file\n")
      total_files_skipped += 1
      continue
    
    file_data_date = pd.to_datetime(df['data_date'].iloc[0]).date()
    print(f"Data date: {file_data_date}\n")
    
    if file_data_date in ingested_dates:
      print(f"Skipped - This date is already fully ingested\n")
      total_files_skipped += 1
      continue
    
    if UNIQUE_COL not in df.columns:
      print(f"Error: '{UNIQUE_COL}' column not found - skipping file\n")
      total_files_skipped += 1
      continue
    
    original_count = len(df)
    df_new = df[~df[UNIQUE_COL].isin(existing_fips)]
    new_row_count = len(df_new)
    skipped_row_count = original_count - new_row_count
    
    print(f"New rows to insert: {new_row_count:,}")
    print(f"Duplicate rows (skipped): {skipped_row_count:,}\n")    
    total_rows_skipped += skipped_row_count
    
    if new_row_count == 0:
      print(f"No new rows to insert from this file\n")
      total_files_skipped += 1
      continue
    
    print(f"Inserting {new_row_count:,} rows\n")    
    columns = df_new.columns.tolist()
    columns_str = ', '.join(columns)
    placeholders = ', '.join(['%s'] * len(columns))
    
    insert_sql = f"""
      INSERT INTO covid_counties_2 ({columns_str}) 
      VALUES ({placeholders})
      ON CONFLICT ({UNIQUE_COL}) DO NOTHING
    """  
    inserted_count = 0
    batch_size = 500
    
    for index, row in enumerate(df_new.itertuples(index=False), start=1):
      row_data = tuple(None if pd.isna(val) else val for val in row)
      cursor.execute(insert_sql, row_data)
      
      if cursor.rowcount > 0:
        inserted_count += 1
      
      if index % batch_size == 0:
        conn.commit()
        percentage = (index / new_row_count) * 100
        print(f"Progress: {index:,}/{new_row_count:,} ({percentage:.1f}%)")
    
    conn.commit()
    print(f"Successfully inserted {inserted_count:,} rows\n")
    
    total_files_processed += 1
    total_rows_inserted += inserted_count
    ingested_dates.append(file_data_date)
    
    new_fips_from_file = set(df_new[UNIQUE_COL].dropna())
    existing_fips.update(new_fips_from_file)
    
  except Exception as e:
    print(f"Error processing file: {e}\n")
    conn.rollback()
    continue

print(f"\nFiles processed: {total_files_processed}")
print(f"Files skipped: {total_files_skipped}")
print(f"Rows inserted: {total_rows_inserted:,}")
print(f"Rows skipped (duplicates): {total_rows_skipped:,}\n")

cursor.close()
conn.close()
print("Database connection closed")
print("Pipeline Completed Successfully")