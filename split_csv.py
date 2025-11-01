import os
import pandas as pd
from datetime import datetime, timedelta

def split_csv_by_date(input_file, output_dir, start_date='2025-10-26', days_to_split=3):
  print("Splitting into multiple CSVs\n")
  os.makedirs(output_dir, exist_ok=True)
  print(f"Reading original CSV File: {input_file}\n")
  df = pd.read_csv(input_file, low_memory=False)
  total_rows = len(df)
  print(f"Total rows in original file: {total_rows:,}\n")
  rows_per_file = total_rows//days_to_split
  print(f"Rows per file: {rows_per_file:,}\n")
  start = datetime.strptime(start_date, '%Y-%m-%d')

  for day in range(days_to_split):
    current_date = start + timedelta(days=day)
    date_str = current_date.strftime('%Y-%m-%d')

    start_idx = day * rows_per_file
    if day == days_to_split - 1:
      end_idx = total_rows
    else:
      end_idx = (day+1) * rows_per_file

    batch = df.iloc[start_idx:end_idx].copy()
    batch.insert(0,'data_date', date_str) #adding the date col
    output_file = os.path.join(output_dir, f'counties_{date_str}.csv')
    batch.to_csv(output_file, index=False)

    print(f"Created: {output_file}\n")
    print(f"Date: {date_str}\n")
    print(f"Rows: {len(batch):,}\n")
    print(f"File split into {days_to_split} files\n")
    print(f"Files saved in {output_dir}\n")

if __name__ == "__main__":
  input_file = 'data/counties.csv'
  output_dir = 'data/split_files'
  start_date = '2025-10-26'
  days = 3

  split_csv_by_date(input_file, output_dir, start_date, days)