#!/usr/bin/env python3

import argparse
import sys

from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import altair as alt

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

  if appdata[appdata.svewidth == 0].groupby('version').sum()['count'].max() >= 1e9:
    scale = 'billion'
    appdata.loc[:, 'count'] /= 1e9
  else:
    scale = 'million'
    appdata.loc[:, 'count'] /= 1e6

  fname = f'opcount-{appname}-all-clustered-stacked-group.png'

  alt.Chart(appdata).mark_bar().encode(x=alt.X('version', title='', axis=alt.Axis(labelAngle=-30)),
                                   y=alt.Y('sum(count)', title=f'Dynamic execution count ({scale} instructions)'),
                                   column='svewidth',
                                   color=alt.Color('optype', title='Op Group', scale=alt.Scale(scheme='set2')))\
                                .configure(background='white')\
                                .configure_title(anchor='middle', fontSize=14)\
                                .properties(title=appname)\
                                .save(fname, scale_factor='2.0')

  print(f'Saved plot for {appname} in {fname}.')


def main():
  args = parse_args()

  if args.data.endswith('csv'):
    df = pd.read_csv(args.data)
  else:
    df = pd.read_pickle(args.data)
  df['svewidth'] = pd.to_numeric(df.svewidth)

  applications = [args.application] if args.application else pd.unique(df['application'])

  with ThreadPoolExecutor() as executor:
    for a in applications:
      executor.submit(plot, df, a)

if __name__ == '__main__':
  main()
