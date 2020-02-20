#!/usr/bin/env python3

import os.path
import re
import sys

from datetime import datetime

import pandas as pd

# Reads the run configuration from a results directory
def read_config(result):
  cfg_path = os.path.join(result, 'run.cfg')

  if not os.path.exists(cfg_path):
    print(result + ':', "Could not read configuration from run.cfg")
    return None

  cfg     = {}
  options = ['svewidth', 'time']
  with open(cfg_path, 'r') as f:
    for line in f:
      for opt in options:
        if opt in line:
          cfg[opt] = re.split(r'[=\s]+', line)[1]
          break

  # Change the name of some keys
  cfg['timestamp'] = cfg.pop('time')

  return cfg

# Reads an existing DataFrame from the results directory.
# Type is {ops, mem-analyze, mem-bundle}, corresponding to the different types of results we can collect
def read_df(result, type):
  pickle_path = os.path.join(result, type + '.pickle')
  csv_path    = os.path.join(result, type + '.csv')

  if os.path.exists(pickle_path):
    df = pd.read_pickle(pickle_path)
  elif os.path.exists(csv_path):
    df = pd.read_csv(csv_path)
  else:
    print(f"{result}: Could not find either {type}.pickle or {type}.csv")
    return None

  runcfg = read_config(result)
  if runcfg is None:
    return None

  df['svewidth']  = runcfg['svewidth']
  df['timestamp'] = runcfg['timestamp']

  return df


def merge(results, type):
  dfs = [read_df(r, type) for r in results]
  if all(df is None for df in dfs):
    return None

  print(len(dfs), [len(df) for df in dfs])

  merged_df = pd.concat(dfs, ignore_index=True)[dfs[0].columns] # The indexing is so that the column order is kept
  print(merged_df)
  return merged_df

def save(df, type, fname):
  df.to_pickle(fname + '.pickle')
  df.to_csv(fname + '.csv', index=False)
  print("Merged", type, "in", fname+'.pickle', "and", fname+'.csv')



def print_help():
  print('Usage: result-merge.py [-h] [results ...]')
  sys.exit()

def main():
  if len(sys.argv) < 2 or sys.argv[1] == '-h' or sys.argv[1] == '--help':
    print_help()

  for result_type in ['ops', 'mem-analyze', 'mem-bundle']:
    merged_df = merge(sys.argv[1:], result_type)

    if merged_df is not None:
      save(merged_df, result_type, f'merged_{result_type}_' + datetime.now().strftime('%Y-%m-%d_%H-%M-%S'))
    else:
      print("Found no results to merge for type:", result_type)

if __name__ == '__main__':
  main()
