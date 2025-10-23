import os
import re
import pandas as pd
import psycopg2
from datetime import datetime
from kaggle.api.kaggle_api_extended import KaggleApi

DATASET_NAME = os.getenv('KAGGLE_DATASET', 'jieyingwu/covid19-us-countylevel-summaries')
FILE_NAME = "counties.csv"

#Database Configuration
DB_CONFIG = {
  'host' : os.getenv('DB_HOST', 'localhost'),
  'port' : os.getenv('DB_PORT', '5432'),
  'database' : os.getenv('DB_NAME', 'counties_db'),
  'user' : os.getenv('DB_USER', 'postgres'),
  'password' : os.getenv('DB_PASSWORD','Qazokn@123')
}

print("covid-19 county data ingestion pipeline started")

print("\n Downloading our dataset from Kaggle")
print(f"Dataset: {DATASET_NAME}")

#Kaggle API Initialization
try:
  api=KaggleApi()
  api.authenticate()
  print("Kaggle authentication successfull")

  api.dataset_download_files(DATASET_NAME, path='.',unzip=True)
  print("Downloaded and extracted dataset")

  import glob
  csv_files = glob.glob('*.csv')
  print(f"Found CSV Files: {csv_files}")

  if csv_files:
    FILE_NAME=csv_files[0];
    print(f"Using file: {FILE_NAME}")

  else:
    print("No CSV Files found in dataset")
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
print("\nCreating Table")

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

#Detecting Unique Indentifiers:
print("Detecting a unique identifier column")
total_rows = len(df)
unique_col = None

for col in df.columns:
  if df[col].nunique() == total_rows and df[col].isnull().sum()==0:
    unique_col = col
    print(f"Unique identifier column: {col}")
    break;
  
  if not unique_col:
    print("No natural unique column found")
    unique_col = 'inserted_timestamp'
    df[unique_col] = pd.date_range(datetime.now(),  periods=len(df), freq='S')
    print(f"Created unique column: '{unique_col}'")

#Checking Table existence
print("Checking if the table of the same name exists")
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

  cursor.execute(f"""CREATE UNIQUE INDEX IF NOT EXISTS idx_covid_{unique_col} ON covid_counties ({unique_col})""")
  conn.commit()
  print(f"Table 'covid_counties' created successfully with unique index on: {unique_col}")

except Exception as e:
  print(f"Error creating Table: {e}")
  conn.rollback()
  conn.close()
  exit(1)

#Insert Data in Tables
print("\n Inserting data into PostgreSQL")

try:
  total_rows = len(df)
  batch_size = 500
  inserted = 0
  updated = 0

  columns = df.columns.tolist()
  columns_str = ', '.join(columns)
  placeholders = ', '.join(['%s'] * len(columns))

  update_set = ', '.join([f"{col} = EXCLUDED.{col}" for col in columns if col != unique_col])

  insert_sql = f"""INSERT INTO covid_counties ({columns_str}) VALUES ({placeholders}) ON CONFLICT ({unique_col}) DO UPDATE SET {update_set}, updated_at = CURRENT_TIMESTAMP
  """
  print(f"Using ON CONFLICT on column: {unique_col}")
  print(f"Inserting {total_rows:,} rows in batches of {batch_size}")

  for index, row in enumerate(df.itertuples(index=False), start=1):
    row_data = tuple(None if pd.isna(val) else val for val in row)
    cursor.execute(insert_sql, row_data)
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

  if os.path.exists(FILE_NAME):
    os.remove(FILE_NAME)
    print(f"Removed temporary file: {FILE_NAME}")

except Exception as e:
  print(f"Cleanup warning: {e}")
  exit(1)

#Summary
print("Data Ingestion Pipeline Completed")
print(f"\n Dataset: {DATASET_NAME}")
print("Table: covid_counties")
print(f"Total records: {total_rows:,}")
print("Status: Success")
