#!/usr/bin/env python3

import argparse
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sea

def parse_args():
  parser = argparse.ArgumentParser()

  parser.add_argument('-a', '--application', help='Plot only the given application')

  parser.add_argument('data', help='The data to plot, in CSV or DataFrame pickle format')

  return parser.parse_args()

# Plots application `appname`
def plot(results, appname):
  appdata = results[results.application == appname]
  if len(appdata) == 0:
    print(f'No data to plot for {appname}.')
    return

  # The data has an entry for each active vector width
  # We split it into bins and plot a histogram
  bins       = [0]+list(range(127,1152,128))
  bin_labels = ['0-127'] + [f'{bins[i]+1}-{bins[i+1]}' for i in range(1, len(bins)-2)] + ['1024']
  binned      = appdata.groupby(['version', 'svewidth',pd.cut(appdata['active-bits'], bins=bins, labels=bin_labels)]).sum()

  hist = pd.DataFrame(binned).drop(columns='active-bits', errors='ignore').reset_index()
  hist['pct-accesses'].fillna(0, inplace=True)

  g = sea.FacetGrid(hist, row='version', col='svewidth', margin_titles=True)\
            .map(sea.barplot, "active-bits", "pct-accesses")\
            .set_axis_labels("Active bits", "Percentage of operations")

  _, labels = plt.xticks()
  g.set_xticklabels(labels, rotation=90)
  g.set(ylim=(0, 100))

  g.fig.suptitle(appname, size='xx-large', y=0.99)
  plt.tight_layout()
  plt.subplots_adjust(top=0.9)

  fname = f'memtrace-bundle-facet-{appname}.png'
  plt.savefig(fname)
  print(f'Saved plot for {appname} in {fname}.')


def main():
  args = parse_args()

  if args.data.endswith('csv'):
    df = pd.read_csv(args.data)
  else:
    df = pd.read_pickle(args.data)
  df['svewidth'] = pd.to_numeric(df.svewidth)

  applications = [args.application] if args.application else pd.unique(df['application'])

  sea.set(style='whitegrid')
  sea.set_palette(sea.color_palette('colorblind', 8))

  for a in applications:
    plot(df, a)


if __name__ == '__main__':
  main()
