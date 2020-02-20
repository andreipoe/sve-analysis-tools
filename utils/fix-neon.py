#!/usr/bin/env python3

import sys

import pandas as pd

# Replaces the names of all versions of an app with just the basename
def rename_versions(df, app):
  variations = [a for a in df.application.unique() if a.startswith(f'{app}-')]
  print("Renaming", variations, f"to '{app}'")
  df.loc[df.application.str.startswith(f'{app}-'), 'application'] = app

# Sets a bogus SVE width for scalar results to make plotting easier
def fix_novec(df):
  novec_svewidth = 0
  print(f"novec: Setting svewidth = {novec_svewidth}")
  df.loc[df.application.str.endswith(f'-novec'), 'svewidth'] = novec_svewidth

# Sets a bogus SVE width for NEON results to make plotting easier
def fix_neon(df):
  neon_svewidth = 1
  print(f"neon: Setting svewidth = {neon_svewidth}")
  df.loc[df.application.str.endswith(f'-neon'), 'svewidth'] = neon_svewidth


def main():
  if len(sys.argv) < 2 or '-h' in sys.argv or '--help' in sys.argv:
    print("Usage: fix-neon.py <pickle/csv>")
    sys.exit(1)

  filename = sys.argv[1]
  if filename.endswith('.csv'):
    df = pd.read_csv(filename)
  else:
    df = pd.read_pickle(filename)
  original_records = len(df)
  print(f"Read {original_records} records")

  fix_novec(df)
  fix_neon(df)

  apps = [a.replace('-sve', '') for a in df.application.unique() if a.endswith('-sve')]
  for app in apps:
    rename_versions(df, app)

  new_records = len(df)
  if new_records == original_records:
    basename = filename[:filename.rfind('.')]
    df.to_pickle(basename + '.pickle')
    df.to_csv(basename + '.csv', index=False)
    print(f"Wrote {new_records} records")
  else:
    print(f"Refusing to write {new_records} records. Something went wrong")
    sys.exit(2)

if __name__ == "__main__":
    main()
