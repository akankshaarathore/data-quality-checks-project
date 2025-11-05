import pandas as pd
import os
from kaggle.api.kaggle_api_extended import KaggleApi

DATASET_NAME = os.getenv('KAGGLE_DATASET', 'jieyingwu/covid19-us-countylevel-summaries')
FILE_NAME = "counties.csv"
DATA_DIR = 'data'
FILE_NAME = 'counties.csv'
FILE_PATH = os.path.join(DATA_DIR, FILE_NAME)

os.makedirs(DATA_DIR, exist_ok=True)

if not os.path.exists(FILE_PATH):
    print(f"{FILE_PATH} not found — downloading from Kaggle...")
    api = KaggleApi()
    api.authenticate()
    api.dataset_download_files(DATASET_NAME, path=DATA_DIR, unzip=True)
    print("Download complete.\n")
else:
    print(f"Found existing file: {FILE_PATH}\n")

df = pd.read_csv('data/counties.csv')
print(f"Loaded original CSV")
print(f"Total rows: {len(df):,}")
print(f"Total columns: {len(df.columns)}")

#Unique column range:
print(f"\n  Current fips range: {df['FIPS'].min()} to {df['FIPS'].max()}")

#testing with 5 rows by copying them and changing fips value
num_test_rows = 5
test_rows = df.head(num_test_rows).copy()

# Generate new unique fips values 
new_fips_values = [99001, 99002, 99003, 99004, 99005]
test_rows['FIPS'] = new_fips_values

#Modifying some other rows:
test_rows['county'] = ['Test County 1', 'Test County 2', 'Test County 3', 'Test County 4', 'Test County 5']
test_rows['State'] = ['Test State'] * num_test_rows

print(f"\n Created {num_test_rows} test rows")
print(f" New fips values: {new_fips_values}")

# Combine original data with test rows
df_test = pd.concat([df, test_rows], ignore_index=True)

print(f"\n Combined data:")
print(f" Original rows: {len(df):,}")
print(f" Test rows added: {num_test_rows}")
print(f" Total rows in test file: {len(df_test):,}")

# Save as test file
df_test.to_csv('counties_test.csv', index=False)

print(f"\nTest file saved as: counties_test.csv")
print(f"\nTest rows details:")
print(test_rows[['FIPS', 'county', 'State']].to_string(index=False))