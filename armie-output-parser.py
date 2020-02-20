#!/usr/bin/env python3

import argparse
import glob
import itertools
import os
import os.path
import re
import sys

from collections import OrderedDict

def parse_args():
  parser = argparse.ArgumentParser()

  # Mode choice
  mode_group = parser.add_mutually_exclusive_group()
  mode_group.add_argument('-l', '--list', action='append_const', dest='mode', const='list',
                      help='list binaries for which results have been collected')
  mode_group.add_argument('--op-count', action='append_const', dest='mode', const='op-count',
                          help='count executed ops')
  mode_group.add_argument('--mem-count',action='append_const', dest='mode', const='mem-count',
                          help='count memory operations')

  # Common options
  parser.add_argument('-n', type=int, default=8, metavar='N',
                      help='show %(metavar)s item in top summaries (default: %(default)s')
  parser.add_argument('-i', '--isa', choices=['a64','sve','both'], default='sve',
                      help='instruction set(s) to consider (default: %(default)s)')
  parser.add_argument('-g', '--graph', action='store_true',
                      help='plot the results')
  parser.add_argument('-e', '--export', action='store_true',
                      help='export the results to csv and DataFrame pickle')

  # Op Count options
  op_count_group = parser.add_argument_group('op-count options')
  op_count_group.add_argument('--highlight', action='store_true',
                              help='compare pairs of results to find opcodes that are more common in one than in the other; use with --threshold and --min-count')
  op_count_group.add_argument('-t', '--threshold', type=int, default=20, metavar='T',
                              help='highlight opcodes only when differences are above %(metavar)s%% (default: %(default)s)')
  op_count_group.add_argument('--min-count', type=int, default=1000, metavar='N',
                              help='highlight opcodes only they appear at least %(metavar)s times (default: %(default)s)')

  # Positional
  parser.add_argument('results', help='path to a results directory')

  return parser.parse_args()

# Gets a list of binaries for which results have been collected in a given directory
# Assumes that the wrapper script has generated binaries.lst
# Retuns 1) the actual file names, 2) the patters used to invoke the wrapper script, 3) the readable name of each version
def get_binaries(results):
  with open('/'.join((results,'binaries.lst'))) as f:
    root     = f.readlines(1)[0].strip()
    binaries = [b.strip() for b in f.readlines()]
    versions = [b.replace(root, '')[1:] for b in binaries]

  return binaries, root, versions


###### opcodes ######
class Ops:
  def __init__(self):
    self.opcodes     = {}
    self.opcounts    = None
    self.top_ops     = None
    self.top_counts  = None
    self.total_ops   = 0
    self.unique_ops  = 0

    self.total_a64  = 0
    self.min_a64    = 0 # Legacy
    self.total_neon = 0

  # Parses decoded.txt, undecoded.txt, and a64-count.tx (if available) to obtain instruction counts
  @classmethod
  def for_binary(cls, binary):
    ops = Ops()

    undecoded_file = 'undecoded_'+binary+'.txt'
    if os.path.exists(undecoded_file):
      # Parse decoded.txt to map instruction words to ops
      inst_to_op = {}
      with open('decoded_'+binary+'.txt', 'r') as decoded:
        for line in decoded:
          parts            = re.split(r'\s+', line.strip())
          inst, op         = parts[0], parts[2]
          inst_to_op[inst] = op

      # Parse undecoded.txt to count insutrctions
      with open('undecoded_'+binary+'.txt', 'r') as undecoded:
        for line in undecoded:
          count, inst = line.strip().replace(' ', '').split(':')
          count       = int(count)
          op          = inst_to_op[inst]

          ops.opcodes[op]  = ops.opcodes.get(op, 0) + count
          ops.total_ops   += count

    # Make an ordered inverse mapping (from counts to ops), so that it's easy to get top N
    if ops.total_ops > 0:
      ops.top_ops, ops.top_counts = zip(*sorted(ops.opcodes.items(), key=lambda x: x[1], reverse=True))
    else:
      ops.top_ops, ops.top_counts = (), ()
    ops.total_ops  = sum(ops.top_counts)
    ops.unique_ops = len(ops.top_counts)

    a64_count_file = 'a64-count_'+binary+'.txt'
    if os.path.exists(a64_count_file):
      # Get the total number of scalar A64 and NEON instructions from a64-count, if available
      with open(a64_count_file, 'r') as out:
        for line in out:
          if line.startswith('Total instructions:'):
            ops.total_a64 = int(line.split(' ')[-1].replace(',', ''))
          elif line.startswith('Vector instructions (v and q):'):
            ops.total_neon = int(line.split(' ')[-2].replace(',', ''))
    else:
      # Get the approximate total number of A64 instructions from the opcodes client
      with open('opcodes_'+binary+'.out', 'r') as out:
        lines = out.read().splitlines()
        start = lines.index('Opcode execution counts in AArch64 mode:')
        end   = [idx for idx,s in enumerate(lines) if 'unique emulated instructions written to undecoded.txt' in s][0]
        lines = lines[start+1:end]

        ops.min_a64 = int(lines[0].strip().split(' ')[0])
        for line in lines:
          parts = re.split(r'\s+', line.strip())
          count, op = int(parts[0]), parts[2]

          ops.total_a64 += count

    return ops

  def get_nth_most_used(self, n):
    return self.top_ops[n-1], self.top_counts[n-1]

  def get_total(self):
    return self.total_ops

  def get_unique_ops_count(self):
    return self.unique_ops

  def get_op_count(self, op):
    return self.opcodes.get(op, 0)

  def get_a64_count(self):
    return self.total_a64, self.min_a64

  def get_neon_count(self):
    return self.total_neon

  def get_scalar_count(self):
    return self.total_a64 - self.total_neon

# Checks pairs of results for operands the appear predominantly in one side
def highlight_ops(binaries, ops, names, threshold, min_count, N):
  for b1,b2 in itertools.combinations(binaries,2):
    ops1, ops2   = ops[b1], ops[b2]
    name1, name2 = names[b1], names[b2]
    top_ops      = set()

    # Gather the top ops in both binaries
    for i in range(1, min(N, min(ops1.get_unique_ops_count(), ops2.get_unique_ops_count()))+1):
      top_ops.add(ops1.get_nth_most_used(i)[0])
      top_ops.add(ops2.get_nth_most_used(i)[0])

    print("\nOpcode highlights: {} / {}".format(name1, name2))

    # Check if they also appear in the other
    for op in top_ops:
      count1, count2 = ops1.get_op_count(op), ops2.get_op_count(op)

      if count1 == 0 and count2 >= min_count:
        print("  {:>8}: Only appears in {} ({:,})".format(op, name2, count2))
      elif count2 == 0 and count1 >= min_count:
        print("  {:>8}: Only appears in {} ({:,})".format(op, name1, count1))
      else:
        if count1 <= min_count and count2 <= min_count:
          continue

        diff = abs(count1 - count2) / min(count1, count2)
        if count1 >= count2 * ((100+threshold)/100):
          print("  {:>8}: {:>4.1f}x more common in {} ({:,}) than in {} ({:,})".format(op, 1+diff, name1,count1, name2,count2))
        elif count2 > count1 * ((100+threshold)/100):
          print("  {:>8}: {:>4.1f}x more common in {} ({:,}) than in {} ({:,})".format(op, 1+diff, name2,count2, name1,count1))

# Makes a histogram plot of opcodes used in a binary
def plot_ops(binaries, opsmap, namesmap, top_ops, app, fname):
  import matplotlib.pyplot as plt
  import pandas as pd

  top_ops_list = list(top_ops)
  counts = {op: [opsmap[b].get_op_count(op) / 1e6 for b in binaries] for op in top_ops_list}

  # Add all A64 instructions as a single (fake) op type
  top_ops_list.append('A64')
  counts['A64'] = [opsmap[b].get_a64_count()[0] / 1e6 for b in binaries]

  index = pd.Index([n.replace('-trace', '') for n in namesmap.values()], name='op')
  df    = pd.DataFrame(counts, index=index)
  ax    = df.plot(kind='bar', stacked=True, colormap='tab20b')

  plt.title(app)
  ax.set_xlabel('Version')
  ax.set_ylabel('Dynamic execution count (milllion instructions)')
  plt.xticks(rotation=30)

  plt.tight_layout()
  box = ax.get_position()
  ax.set_position([box.x0, box.y0, box.width * 0.8, box.height])
  ax.legend(loc='center left', bbox_to_anchor=(1, 0.5), title='Op')

  plt.savefig(fname)

def export_ops(binaries, opsmap, namesmap, app, fname):
  import pandas as pd

  data  = [{'application': app, 'version': namesmap[b], 'op': op, 'count': count}  for b in binaries for op, count in opsmap[b].opcodes.items()]
  data += [{'application': app, 'version': namesmap[b], 'op': 'A64', 'count': opsmap[b].get_scalar_count()} for b in binaries]
  data += [{'application': app, 'version': namesmap[b], 'op': 'NEON', 'count': opsmap[b].get_neon_count()} for b in binaries]

  df = pd.DataFrame(data)
  df.to_pickle(fname + '.pickle')
  df.to_csv(fname + '.csv', index=False, columns=['application', 'version', 'op', 'count'])
  print("Exported to", fname+'.pickle', "and", fname+'.csv')

# Shows the top N SVE opcodes used in a binary
def sve_count(binaries, highlight, threshold, min_count, graph, export, N, app, names=None):
  namesmap     = {b: name for b,name in zip(binaries, names if names else binaries)}
  opsmap       = {}
  all_top_ops = set()

  for b in binaries:
    ops         = Ops.for_binary(b)
    opsmap[b]   = ops
    total       = ops.get_total()

    a64_total, a64_error = ops.get_a64_count()

    print("Version:", namesmap[b])
    print("  Total A64 instructions executed: {:,} + O({:,})".format(a64_total, a64_error))
    print("  Total SVE instructions executed: {:,}".format(total))
    print("  Top ops executed:")

    for i in range(1, min(N, ops.get_unique_ops_count())+1):
      op, count = ops.get_nth_most_used(i)
      all_top_ops.add(op)
      print("    {:>8}: {:>11,} ({:.2f}%)".format(op, count, count/total*100))
    print()

  if highlight:
    highlight_ops(binaries, opsmap, namesmap, threshold, min_count, 2*N)

  if graph:
    fname = 'opcount.png'
    plot_ops(binaries, opsmap, namesmap, all_top_ops, app, fname)
    print("Plot saved to", fname)

  if export:
    fname = 'ops'
    export_ops(binaries, opsmap, namesmap, app, fname)


###### memtrace ######
class MemTrace:
  def __init__(self):
    self.total_mem_ops  = 0
    self.total_reads    = 0
    self.total_gathers  = 0
    self.read_sizes     = {}
    self.total_writes   = 0
    self.total_scatters = 0
    self.write_sizes    = {}
    # TODO: maybe do something with locations

  @classmethod
  def for_binary(cls, binary):
    mem = MemTrace()

    tracefiles = glob.glob('sve-memtrace.' + binary + '*.log')
    assert len(tracefiles) == 1
    with open(tracefiles[0], 'r') as f:
      for line in f:
        parts = line.strip().split(', ')
        bundle, is_write, size = (int(p) for p in parts[2:5])

        if size == 0 or int(parts[1]) < 0:
          # ArmIE sometimes outputs artifacts at the beginning and end of a trace; we skip over them
          continue
        if bundle >=2:
          # We don't currently do anything with the comprising parts of gathers and scatters
          # TODO: we may need to count inner elements to determine the total size of a g/s
          continue

        mem.total_mem_ops += 1
        if is_write:
          mem.total_writes += 1
          assert bundle in (0,3)
          if bundle == 3:
            mem.total_scatters += 1
          mem.write_sizes[size] = mem.write_sizes.get(size, 0) + 1
        else:
          mem.total_reads += 1
          assert bundle in (0,1)
          if bundle == 1:
            mem.total_gathers += 1
          mem.read_sizes[size] = mem.read_sizes.get(size, 0) + 1

    return mem


# The memc-count functionality is deprecated. Use the instrace tools instead
def legacy_mem_count(binaries, N, names=None):
  for b,name in zip(binaries, names if names else binaries):
    memtrace      = MemTrace.for_binary(b)
    total         = memtrace.total_mem_ops
    reads, writes = memtrace.total_reads, memtrace.total_writes
    gath, scat    = memtrace.total_gathers, memtrace.total_scatters

    print("Version:", name)
    print("  Total SVE memory operations: {:,}".format(total))

    if total > 0:
      print("    Total SVE reads: {:,} ({:.2f}% of ops)".format(reads, reads/total*100))
      if reads > 0:
        print("      By size:", ', '.join("{}: {:,} ({}%)".format(s*8, n, n//reads*100) for s, n in sorted(memtrace.read_sizes.items())))
        print("      Total SVE gathers: {:,} ({:.2f}% of reads, {:.2f}% of ops)".format(
          gath, gath/reads*100, gath/total*100))

      print("    Total SVE writes: {:,} ({:.2f}% of ops)".format(writes, writes/total*100))
      if reads > 0:
        print("      By size:", ', '.join("{}: {:,} ({}%)".format(s*8, n, n//writes*100) for s, n in sorted(memtrace.write_sizes.items())))
        print("      Total SVE scatters: {:,} ({:.2f}% of writes, {:.2f}% of ops)".format(
          scat, scat/writes*100, scat/total*100))
    print()


def export_mem(binaries, namesmap, app, fname):
  import pandas as pd

  for instrace_tool in ['analyze', 'bundle']:
    df = pd.DataFrame()

    for b in binaries:
      df_b = pd.read_csv('.'.join([instrace_tool, b, 'csv']))
      df_b['version'] = namesmap[b]
      df = df.append(df_b, ignore_index=True)
    df['application'] = app

    fname_df = f"{fname}-{instrace_tool}"
    df.to_pickle(fname_df + '.pickle')
    df.to_csv(fname_df + '.csv', index=False)
    print(f"Exported {instrace_tool} data to {fname_df}.pickle and {fname_df}.csv")

def mem_count(binaries, export, N, app, names=None):
  if export:
    fname = 'mem'
    namesmap = {b: name for b,name in zip(binaries, names if names else binaries)}
    export_mem(binaries, namesmap, app, fname)
  else:
    print("Refusing to run the legacy mem-count parser.")
    print("Use the Arm Research instrace tools, which are orders of magnitude faster.")
    print()


if __name__ == '__main__':
  args = parse_args()

  if not os.path.isdir(args.results):
    print("Not a directory:", args.results)
    sys.exit(1)

  binaries, bin_root, bin_versions = get_binaries(args.results)
  if 'list' in args.mode:
    print("Binary name:", bin_root)
    print("  Versions:", ' '.join(bin_versions))
    sys.exit(0)

  # TODO: unimplemented options
  if args.isa != 'sve':
    print("Warning: instruction set '" + args.isa + "' not implemented.")

  os.chdir(args.results)

  assert len(args.mode) == 1
  if 'op-count' in args.mode:
    sve_count(binaries, args.highlight, args.threshold, args.min_count, args.graph, args.export, args.n, bin_root, bin_versions)
  elif 'mem-count' in args.mode:
    if args.highlight:
      print("Warning: --highlight is ignored in mem-count mode.")
    if args.graph:
      print("Warning: --graph is not implemented in mem-count mode.")
    mem_count(binaries, args.export, args.n, bin_root, bin_versions)

# TODO: Sample usage
#
# - [X] Show top SVE opcodes count:
#   ./armie-parser.py --sve-count results_xx
#   ./armie-parser.py --sve-count -n 10 results_xx
#   ./armie-parser.py --op-count -i sve results_xx
#
# - [ ] Compare top SVE opcodes between pairs:
#   ./armie-parser.py --sve-count --compare results_xx
#
# - [ ] Show/compare top A64 opcodes:
#   ./armie-parser.py --a64-count results_xx
#   ./armie-parser.py --a64-count --compare results_xx
#   ./armie-parser.py --op-count -i a64 results_xx
#
# - [X] Find opcodes only used in one version in a pair:
#   ./armie-parser.py --op-count --highlight results_xx
#   ./armie-parser.py --op-count --highlight --thresh 50 results_xx
#   ./armie-parser.py --op-count --highlight -i sve results_xx
#   ./armie-parser.py --op-count --highlight -i a64 results_xx
#   ./armie-parser.py --op-count --highlight -i both results_xx
#
# - [X] Draw a histogram:
#   ./armie-parser.py --op-count --graph results_xx
#
#
# - [X] Count memory accesses by width:
#   ./armie-parser.py --mem-count results_xx
#   ./armie-parser.py --mem-count --writes results_xx
#   ./armie-parser.py --mem-count --reads results_xx
#
# - [ ] Compare memory accesses between pairs:
#   ./armie-parser.py --mem-count --compare results_xx
#   ./armie-parser.py --mem-count --compare -i sve results_xx
#   ./armie-parser.py --mem-count --compare -i a64 results_xx
#   ./armie-parser.py --mem-count --compare -i both results_xx
#
#
# General notes:
#  - Focus on SVE first, leave NEON for later
#  - Add functionality to collect and decode undecoded NEON ops
#  - Use the Arm Research Instrace Tools for memory
