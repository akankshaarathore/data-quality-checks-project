import os
import re
import pandas as pd
import psycopg2
from datetime import datetime
from kaggle.api.kaggle_api_extended import KaggleApi

DATASET_NAME = os.getenv('KAGGLE_DATASET', 'jieyingwu/covid19-us-countylevel-summaries')
FILE_NAME = "counties.csv"

#Testing file
USE_TEST_FILE = os.getenv('USE_TEST_FILE', 'false').lower()=='true'
TEST_FILE_PATH = os.getenv('TEST_FILE_PATH', 'counties_test.csv')

#Database Configuration
DB_CONFIG = {
  'host' : os.getenv('DB_HOST', 'localhost'),
  'port' : os.getenv('DB_PORT', '5432'),
  'database' : os.getenv('DB_NAME', 'counties_db'),
  'user' : os.getenv('DB_USER', 'postgres'),
  'password' : os.getenv('DB_PASSWORD','Qazokn@123')
}

print("covid-19 county data ingestion pipeline started")

#Modified download section
if USE_TEST_FILE:
  print("\n Using local test file")
  print(f"Test file: {TEST_FILE_PATH}")

  FILE_NAME = TEST_FILE_PATH
  print(f"Using File: {FILE_NAME}")

else:
  print("\n Downloading our dataset from Kaggle")
  print(f"Dataset: {DATASET_NAME}")

#Kaggle API Initialization
  try:
    api=KaggleApi()
    api.authenticate()
    print("Kaggle authentication successfull")

    api.dataset_download_files(DATASET_NAME, path='data',unzip=True)
    print("Downloaded and extracted dataset")

    import glob
    csv_files = glob.glob('data/*.csv')
    print(f"Found CSV Files: {csv_files}")

    TARGET_FILE = "counties.csv"

    matching_files = [f for f in csv_files if os.path.basename(f) == TARGET_FILE]

    if matching_files:
      FILE_NAME=matching_files[0];
      print(f"Using file: {FILE_NAME}")

    else:
      print(f"{TARGET_FILE} not found in dataset")
      exit(1)

  except Exception as e:
    print(f"Error downloading from Kaggle: {e}")
    print("Make sure KAGGLE_USERNAME and KAGGLE KEY are set coorectly")
    exit(1)

print("\n Reading CSV Files")

#Database Overview
try:
  df=pd.read_csv(FILE_NAME)
  print("CSV loaded successfully")
  print(f"Rows: {len(df):,}")
  print(f"Columns: {len(df.columns)}")
  print(f"Coumn names: {list(df.columns)[:5]}")

  print("\n Data types preview:")
  for col in df.columns[:5]:
    print(f"{col}: {df[col].dtype}")

except Exception as e:
  print(f"Error reading CSV: {e}")
  exit(1)

print("\n Validating Data")

#Basic Vaildation check on dataset
try:
  if df.empty:
    print("Dataset is empty")
    exit(1)

  if len(df.columns) == 0:
    print("Dataset has no columns")
    exit(1)

  if df.isnull().all().all():
    print("All values in dataset are NULL")
    exit(1)

  print("Dataset contains valid data") 

except Exception as e:
  print(f"Error validating data: {e}")
  exit(1)

#Establishing Connection with PostgreSQL Database
print("\n Connecting to PostgreSQL")
print(f"Host: {DB_CONFIG['host']}")
print(f"Database: {DB_CONFIG['database']}")

try:
  conn = psycopg2.connect(**DB_CONFIG)
  cursor = conn.cursor()

  cursor.execute("SELECT version();")
  version = cursor.fetchone()[0]
  print("Connected to PostgreSQL")
  print(f"Version: {version.split(',')[0]}")

except Exception as e:
  print(f"Database connection failed: {e}")
  exit(1)

#Clean Column Names
print("\nPreparing the data schema")

try:
  cleaned_columns = []
  for col in df.columns:
    clean_col = re.sub(r"[^a-z0-9_]", "",
                col.lower().replace(' ','_')
                  .replace('-','_')
                  .replace('.','_')
                  .replace('(','')
                  .replace(')','')
                  .replace('/','_')
                  .replace('%','pct')
                )
    clean_col = re.sub(r'_+','_',clean_col).strip('_')

    if len(clean_col) > 60:
      clean_col = clean_col[:60]  

    original_clean_col = clean_col
    counter=1
    while clean_col in cleaned_columns:
      clean_col = f"{original_clean_col}_{counter}"
      counter+=1

    cleaned_columns.append(clean_col)
              
  df.columns = cleaned_columns
  print(f"Cleaned {len(df.columns)} column names")

except Exception as e:
    print(f"Error cleaning columns: {e}")
    exit(1)

#Setting Unique Indentifiers:
unique_col = 'fips'
print(f"Using unique column: '{unique_col}'")

#Checking Table existence/Creating Table
print("Checking Table Existence")
try:
  cursor.execute(""" SELECT EXISTS(
               SELECT FROM information_schema.tables WHERE table_name = 'covid_counties'
               )
              """)
  table_exists = cursor.fetchone()[0]

  if table_exists:
    print("Table exists- checking for schema changes")
    cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'covid_counties'
  """)
    existing_cols = {row[0] for row in cursor.fetchall()}

    new_cols = [col for col in df.columns if col not in existing_cols]

    if new_cols:
      for col in new_cols:
        dtype = df[col].dtype

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

        cursor.execute(f"ALTER TABLE covid_counties ADD COLUMN IF NOT EXISTS {col} {sql_type}")
        print(f"Added new column: {col} ({sql_type})")
      conn.commit()
    else:
      print("No new columns to add")
    
    cursor.execute("""
                   ALTER TABLE covid_counties
                   ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP""")
    conn.commit()

  else:
    print("Table not found creating a new one")
    create_columns = []
    for col in df.columns:
      dtype = df[col].dtype

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
      CREATE TABLE covid_counties (
      id SERIAL PRIMARY KEY,
      {', '.join(create_columns)},
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    """

    cursor.execute(create_table_sql)
    conn.commit()
    print("New table 'covid_counties' created")

  cursor.execute(f""" 
              CREATE UNIQUE INDEX IF NOT EXISTS idx_covid_{unique_col} ON covid_counties ({unique_col})""")
  conn.commit()
  print(f"unique index exists on column: {unique_col}")

except Exception as e:
  print(f"Error creating Table: {e}")
  conn.rollback()
  conn.close()
  exit(1)

#Delta Detection:
print("\n Performing Delta Detection")
try:
  if table_exists:
    print("Fetching existing unique keys from database")
    cursor.execute(f"SELECT {unique_col} FROM covid_counties")
    existing_keys = {row[0] for row in cursor.fetchall()}
    print(f"Found {len(existing_keys):,} existing rows in database")

    print("Identifying new rows")
    original_count = len(df)
    df = df[~df[unique_col].isin(existing_keys)]
    new_row_count = len(df)
    skipped_count = original_count - new_row_count

    print(f"Total rows: {original_count:,}")
    print(f"Existing rows (skipped) : {skipped_count:,}")
    print(f"New rows to insert: {new_row_count}")

    if new_row_count == 0:
      print("\n No new rows to insert")
      cursor.execute("SELECT COUNT(*) FROM covid_counties")
      count = cursor.fetchone()[0]
      print(f"\nCurrent database status:")
      print(f"  Total rows: {count:,}")

     #Cleanup:
      cursor.close()
      conn.close()
      print("\nDatabase connections closed")
      
      if os.path.exists(FILE_NAME):
        os.remove(FILE_NAME)
        print(f"Removed temporary file: {FILE_NAME}")
      
      print("\nData Ingestion Pipeline Completed")
      print(f"Dataset: {DATASET_NAME}")
      print("Table: covid_counties")
      print("Status: Success (No change needed)")
      exit(0)
  else:
    print("New Table with all rows to be inserted")

except Exception as e:
  print(f"Error during delta detection: {e}")
  conn.rollback()
  conn.close()
  exit(1)

#Insert Data in Tables
print("\n Inserting data into PostgreSQL")

try:
  total_rows = len(df)
  batch_size = 500
  inserted = 0
  actually_inserted = 0

  columns = df.columns.tolist()
  columns_str = ', '.join(columns)
  placeholders = ', '.join(['%s'] * len(columns))

  insert_sql = f"""INSERT INTO covid_counties ({columns_str}) VALUES ({placeholders}) ON CONFLICT ({unique_col}) DO NOTHING
  """
  print(f"Using ON CONFLICT DO NOTHING on column: {unique_col}")
  print(f"Inserting {total_rows:,} rows in batches of {batch_size}")

  for index, row in enumerate(df.itertuples(index=False), start=1):
    row_data = tuple(None if pd.isna(val) else val for val in row)
    cursor.execute(insert_sql, row_data)

    if cursor.rowcount>0:
      actually_inserted+=1
    
    inserted+=1

    if inserted % batch_size == 0:
      conn.commit()
      percentage = (inserted / total_rows) * 100
      print(f"Progress: {inserted:,}/{total_rows:,} rows ({percentage:.1f}%)")

  conn.commit()
  print(f"Successfully inserted all {total_rows:,} rows")

except Exception as e:
  print(f"Error inserting data: {e}")
  conn. rollback()
  conn.close()
  exit(1)

#Verifying Inserted Data
print("\n Verifying data in database")

try:
  cursor.execute("SELECT COUNT(*) FROM covid_counties")
  count = cursor.fetchone()[0]
  print("Verification successful")
  print(f"Total rows in database: {count:,}")

  cursor.execute("""
                 SELECT column_name, data_type
                 FROM information_schema.columns
                 WHERE table_name = 'covid_counties'
                 LIMIT 5
                 """)
  print(f"\n Database schema (first 5 columns): ")
  for col_name, data_type in cursor.fetchall():
    print(f" {col_name} : {data_type}")

  cursor.execute("SELECT * FROM covid_counties LIMIT 5")
  print("\n Sample data: ")
  sample_rows = cursor.fetchall()
  for i, row in enumerate(sample_rows, 1):
    print(f" Row {i}: {row[1:6]}")

  cursor.execute("SELECT MIN(id), MAX(id) FROM covid_counties")
  min_id, max_id = cursor.fetchone()
  print(f"\n Record IDs range: {min_id} to {max_id}")

except Exception as e:
  print(f"Error Verifying data: {e}")
  exit(1)

#Cleanup
print("\n Cleaning up")

try:
  cursor.close()
  conn.close()
  print("Database connections closed")

  csv_path = os.path.join("data", FILE_NAME)
  if os.path.exists(csv_path):
    os.remove(csv_path)
    print(f"Removed temporary file: {csv_path}")

  for zip_file in glob.glob(os.path.join("data", "*.zip")):
    os.remove(zip_file)
    print(f"Removed leftover zip file: {zip_file}")

except Exception as e:
  print(f"Cleanup warning: {e}")
  exit(1)

#Summary
print("Data Ingestion Pipeline Completed")
print(f"\n Dataset: {DATASET_NAME}")
print("Table: covid_counties")
print(f"Total records: {total_rows:,}")
print("Status: Success")
