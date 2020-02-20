# Emulated SVE Analysis Tools

This repository contains a collection of scripts used to characterise performance of applications using the [Arm Instruction Emulator (ArmIE)](https://developer.arm.com/tools-and-software/server-and-hpc/compile/arm-instruction-emulator).

## Requirements

* ArmIE 19.2
* A compiler capable of generating SVE binaries, e.g. GCC 8+ or the Arm HPC Compiler
* Python 3.7+
  * Matplotlib
  * PANDAS
  * Altair
  * Seaborn
  * Plotly

## Workflow

Use the scripts in the [`graphs`](graphs/) directory to generate plots using data collected from emulation experiments.
The visualisations currently supported are:

* [Op counts](graphs/ops.py) – a stacked bar chart of instruction types, clustered by SVE width
* [Active SVE lanes](graphs/mem-bundle.py) – a facet of histograms showing SVE lanes utilisation at each vector width
* [Memory accesses](graphs/mem-analyze.py) – a Sankey diagram of relative counts of different memory access types

The scripts expect the input data in a [PANDAS](https://pandas.pydata.org/) DataFrame.
You can generate these data frames manually (examples are given for [op counts](docs/df-ops.txt), [active lanes](docs/df-mem-bundle.txt), and [memory accesses](docs/df-mem-analyze.txt)), or you can use the wrapper script described below.
If the data frames include data for more than one SVE width or compiler, the graphs will include all combinations of those.

## ArmIE Wrapper

This script runs ArmIE on a set of similar (SVE) binaries and presents the results in an easy-to-read comparison.
One use case is comparing binaries produced from the same code by different compilers.

### Usage

First, name the binaries you want to compare using the same prefix, e.g.:

```
stream.gcc8.2
stream.arm19.2
...
```

Make sure that `armie` is in your `PATH`.
Set `LLVM_MC` to point to the Arm compiler's binary, for SVE decoding.

Then, run the wrapper script using the binaries' prefix as an argument:

```bash
./armie-wrapper.sh stream
```

Use `-h` to show the help.
There are options to set the emulated SVE width, to include or exclude library code from tracing, and to limit collection of data to only instruction or memory traces.

A typical experiment, e.g. to look at instruction trace data, is run as follows:

1. Build your applications with dynamic linking
2. Collect the data:
    ```
    ./armie-wrapper.sh -a -i ...
    ```
4. Export the ops:
    ```
    for d in results_*; do
      ./armie-output-parser.py --op-count --export "$d"
    done
    ```
5. _(Optional)_ Merge the data from all the results folder into a single file:
    ```
    ./utils/result-merge.py results_*
    ```
6. Use a workaround to "fix" the `svewidth` parameters for plain A64 (non-SVE) runs, if you have any:
    ```
    ./utils/fix-neon.py merged_ops.pickle
    ```
7. Split ops intro groups:
    ```
    ./utils/update-op-type.py  merged_ops.pickle
    ```
8. Generate the graph:
  ```
  ./graphs/ops.py merged_ops.pickle
  ```

The sections below give more detail for some of these steps.

**Note**: All the graphing libraries used have Jupyter plugins. For quick prototyping, loading the code in [Jupyter Lab](https://jupyterlab.readthedocs.io/en/stable/) will allow you to use interactive features, e.g. to move around the elements of Sankey diagrams.

#### Output Parser

Run the custom parser after your have obtained the results from the instrumentation clients using the wrapper:

```
./armie-output-parser.py --export <results-folder>
```

This will export the data to a CSV file, which can be read direcly by PANDAS.
Pass `-h` for more options.

**Note**: It is strongly suggested to use the parser only to export data to CSV and perform all analysis using PANDAS. Other functionality may still be present, but it should be considered deprecated.

#### Merging

After exporting, use `result-merge.py` to combine several sets of results into a single DataFrame/CSV file:

```
./utils/result-merge.py <results-folder-1> <results-folder-2> ...
```

This is useful to merge results for all SVE widths into a single dataset.

#### NEON Counting

You can count NEON instructions using a combination of the custom DynamoRIO `oprecord_emulated` client and a disassembled binary.
First, compile your binary and run it under `armie -i liboprecord_emulated.so`.
This will produce a file called `a64-undecoded.txt` containing a mapping between A64 insutrctions addresses and their dynamic count.
Then, run `count-neon.py <binary> <oprecord-file>`.

Results collected for NEON and scalar (no-vec) version don't have a meaningful svewidth.
We use this value to help with drawing graphs by setting it to made-up value.
The script `fix-neon.py` takes a (merged) dataframe and prepares the NEON and no-vec results for graphing.

**Note**: Run `fix-neon.py` before `update-op-type.py`. Otherwise, some information may be lost.

#### Op Groups

The script `update-op-type.py` assigns a category to each instructions.
These categories are read by the opcount graph script to produce stacked bars.
To adjust the categories, simply edit `catmap`, the mapping between instructions an categories, at the top of the script.

### Instrace Tools

If you have the Arm Research Instrace Tools, you can run them all in one go and collect the results.
First, set `INSTRACE_TOOLS` to the root directory of the tools.
Then, run the wrapper script with the results folder as an argument:

```
./run-instrace-tools.sh <results-folder>
```

### Custom Instrumentation Clients

Modified instrumentation clients that may be useful for some collection experiments can be found in [`dr-clients`](dr-clients/).

## Example Applications

[Build and run instructions](docs/build-run.md) are given for a representative set of HPC mini-apps:

* STREAM
* BUDE
* TeaLeaf
* CloverLeaf
* MegaSweep
* Neutral
* MiniFMM
