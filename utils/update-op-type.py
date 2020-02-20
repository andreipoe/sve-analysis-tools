#!/usr/bin/env python3

import sys

import pandas as pd

def get_op_category(op):
  catmap = {
    'arithmetic': ['fmla','fmul','fsub','fcmlt','fsqrt','fcmgt','fmls','fmad','cmpne','and','fabs','addvl','fadd','cntp','cntw','fnmsb','fcvtzs','fcmeq','frinta','orr','cmpeq','fnmls','fneg','fcmge','fmsb','incb','fdiv','incd','fdivr','fcmle','cmpgt','add','sub','mul','faddv','fcvt','scvtf','fminnm','mla','mad','fmaxnm','fminnmv','sdiv','cntd','decd','cnth','not','cmphi','cntb','cmpls','sdivr','fadda','frecpe','lastb','tbl','sminv','smax','smin','uunpkhi','uunpklo','uqdecd','punpkhi','punpklo','index','sxtw','eor'],
    'control': ['incw','whilelo','sel','ptrue','bic','pfalse','incp','ptest','rdvl','zip2','zip1','uzp1','rev'],
    'mem-read': ['ld1rw','ld1w','ldr','ld1d','ld1rd','ld1b','ld1sw'],
    'mem-write': ['st1w','str','st1b','st1d'],
    'move': ['movprfx','mov','lsl','fmov'],
    'A64': ['A64'],
    'NEON': ['NEON'],
    'other': ['UNKNOWN']
  }

  for (type, ops) in catmap.items():
    if op in ops:
      return type

  return 'other'


def print_help():
  print('Usage: update-op-type.py [-h] [results ...]')
  sys.exit()

def main():
  if len(sys.argv) < 2 or sys.argv[1] == '-h' or sys.argv[1] == '--help':
    print_help()

  fname = sys.argv[1]
  if fname.endswith('.csv'):
    df = pd.read_csv(fname)
  else:
    df = pd.read_pickle(fname)

  df['optype'] = df.op.apply(get_op_category)

  if fname.endswith('.csv'):
    df.to_csv(fname, index=False)
  else:
    df.to_pickle(fname)


if __name__ == '__main__':
  main()
