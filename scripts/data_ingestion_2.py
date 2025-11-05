import os
import re
import sys
import pandas as pd
import psycopg2
import glob
from datetime import datetime

if len(sys.argv) < 2:
  print("Usage: python script.py YYYY-MM-DD")
  exit(1)

input_date = sys.argv[1]
try:
  date_obj = datetime.strptime(input_date, '%Y-%m-%d').date()
except ValueError:
  print(f"Invalid date format: {input_date}")
  exit(1)

DB_CONFIG = {
  'host': os.getenv('DB_HOST', 'localhost'),
  'port': os.getenv('DB_PORT', '5432'),
  'database': os.getenv('DB_NAME', 'counties_db'),
  'user': os.getenv('DB_USER', 'postgres'),
  'password': os.getenv('DB_PASSWORD', 'Qazokn@123')
}

SPLIT_FILES_PATH = f"/mnt/dq_persistent/data/split_files/counties_{input_date}.csv"
UNIQUE_COL = 'fips'

print(f"Ingestion Pipeline Started for date: {input_date}")

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

print(f"Looking for CSV file: {SPLIT_FILES_PATH}")
if not os.path.exists(SPLIT_FILES_PATH):
  print(f"Error: file not found at: {SPLIT_FILES_PATH}")
  cursor.close()
  conn.close()
  exit(1)

csv_files = [SPLIT_FILES_PATH]
print(f"Found file: {os.path.basename(SPLIT_FILES_PATH)}")

print("\nExtracting dates from filenames\n")
file_dates = {}
try:
  base = os.path.basename(SPLIT_FILES_PATH)
  date_str = base.replace('counties_', '').replace('.csv', '')
  date = pd.to_datetime(date_str).date()
  file_dates[SPLIT_FILES_PATH] = date
  print(f"{os.path.basename(SPLIT_FILES_PATH)} -> {date}")
except:
  print(f"Could not extract date from {os.path.basename(SPLIT_FILES_PATH)}")
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
  cursor.execute("SELECT DISTINCT input_date FROM covid_counties_2 ORDER BY input_date")
  ingested_dates = [pd.to_datetime(row[0]).date() if isinstance(row[0], str) else row[0] for row in cursor.fetchall()]
  
  if ingested_dates:
    print(f"Found {len(ingested_dates)} already ingested dates:")
    for date in ingested_dates:
      print(f"{date}")  
    
    if date_obj in ingested_dates:
      print(f"Warning: Date {date_obj} is already ingested")
      print("The pipeline will skip duplicate FIPS codes but may add new counties\n")
    else:
      print(f"\nDate {date_obj} is new and will be ingested\n")
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

    if 'input_date' not in df.columns:
      print(f"Error: 'input_date' column not found - skipping file\n")
      cursor.close()
      conn.close()
      exit(1)
    
    file_data_date = pd.to_datetime(df['input_date'].iloc[0]).date()
    print(f"Data date: {file_data_date}\n")
    
    if UNIQUE_COL not in df.columns:
      print(f"Error: '{UNIQUE_COL}' column not found - skipping file\n")
      cursor.close()
      conn.close()
      exit(1)
    
    original_count = len(df)
    df_new = df[~df[UNIQUE_COL].isin(existing_fips)]
    new_row_count = len(df_new)
    skipped_row_count = original_count - new_row_count
    
    print(f"New rows to insert: {new_row_count:,}")
    print(f"Duplicate rows (skipped): {skipped_row_count:,}\n")    
    total_rows_skipped += skipped_row_count
    
    if new_row_count == 0:
      print(f"No new rows to insert from this file\n")
      print(f"All {original_count:,} FIPS codes already exist in database\n")
      cursor.close()
      conn.close()
      print("Database connection closed")
      print("Pipeline Completed")
      exit(0)
    
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

    total_rows_inserted += inserted_count
    
  except Exception as e:
    print(f"Error processing file: {e}\n")
    conn.rollback()
    continue
print(f"Rows inserted: {total_rows_inserted:,}")
print(f"Rows skipped (duplicates): {total_rows_skipped:,}\n")

cursor.close()
conn.close()
print("Database connection closed")
print("Pipeline Completed Successfully")