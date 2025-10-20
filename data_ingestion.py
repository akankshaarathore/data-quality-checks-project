import os
import pandas as pd
import psycopg
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
