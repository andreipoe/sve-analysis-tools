#!/usr/bin/env python3

import re
import subprocess as sp
import sys

from dataclasses import dataclass

@dataclass
class Instruction:
  opcode: str
  arguments: str
  count: int = 0
  is_vector: bool = False
  is_q: bool = False

# Runs objdump to disassemble the given binary
def disassemble_binary(binary):
  return sp.check_output(f"objdump -d -j .text {binary}".split(), universal_newlines=True).split('\n')

# Returns a mapping address -> Instruction for the given disassembly code
def parse_disassembly(disas):
  code = {}

  for line in disas:
    if not re.match(r' {0,2}[0-9a-z]{6,}:', line):
      continue

    line    = line.strip()
    parts   = re.split(r'\s+', line)
    address   = parts[0][:-1]
    arguments = ' '.join(parts[3:])
    arguments = re.sub('//.*', '', arguments)
    is_vector = True if re.match(r'v[0-9]{1,2}\.[0-9]{1,2}[a-z]', arguments) else False
    is_q      = True if re.match(r'q[0-9]{1,2}', arguments) else False

    code[address] = Instruction(opcode=parts[2], arguments=arguments, count=0, is_vector=is_vector, is_q=is_q)

  return code

# Parses an oprecord trace and undoes the map from addresses to instruction
def process_trace(code, trace):
  total, outside_binary, vector, q = 0, 0, 0, 0

  with open(trace, 'r') as f:
    lines = f.readlines()

  for line in lines:
    count, address = line.strip().replace(' ', '').split(':')
    address        = address[2:].lstrip('0')
    count          = int(count)

    total += count
    if address in code:
      instr = code[address]
      instr.count += count

      if instr.is_vector:
        vector += count
      elif instr.is_q:
        q += count
    else:
      outside_binary += count

  return total, vector, q, outside_binary


def main():
  if len(sys.argv) < 3 or '-h' in sys.argv or '--help' in sys.argv:
    print("Usage: count-neon.py <binary> <oprecord-trace>")
    sys.exit(1)

  disas = disassemble_binary(sys.argv[1])
  with open("disas.out", 'w') as f:
    f.write("\n".join(disas))
  code = parse_disassembly(disas)
  total, vector, q, outside_binary = process_trace(code, sys.argv[2])

  print(f'Total instructions: {total:,}')
  print(f'Vector instructions (v only): {vector:,} ({vector/total*100:.2f}%)')
  print(f'Vector instructions (v and q): {(vector+q):,} ({(vector+q)/total*100:.2f}%)')
  print(f'Instructions outside binary: {outside_binary:,} ({outside_binary/total*100:.2f}%)')

if __name__ == '__main__':
  main()
