#!/bin/bash

set -u
set -o pipefail

script_dir="$(realpath "$(dirname "$(realpath "$0")")")"

if [ $# -lt 1 ]; then
    echo "Usage: run-instrace-tools <results> [<sve-width>"]
    exit 1
fi

results_dir="$1"

if [ $# -ge 2 ]; then
    sve_width="$2"
    echo "Using SVE width from command line: $sve_width"
else
    if [ ! -f "$results_dir/run.cfg" ]; then
        "$script_dir/utils/add-run-cfg.py" "$results_dir"
        echo "Added missing run.cfg"
    fi

    sve_width="$(awk -F= '/svewidth/ {print $2}' "$results_dir/run.cfg" | tr -d ' ')"
    echo "Using SVE width from run.cfg: $sve_width"
fi

INSTRACE_TOOLS="${INSTRACE_TOOLS:-$script_dir/instrace-tools}"
NTHREADS="${NTHREADS:-8}"

if [ ! -d "$results_dir" ] || [ ! -s "$results_dir/binaries.lst" ]; then
    echo "There don't seem to be any results in $results_dir."
    exit 2
fi

for tool in merger/bin/merge analyzer/bin/analyze bundle/bin/bundle; do
    if [ ! -x "$INSTRACE_TOOLS/sve-scripts/memtrace_$tool" ]; then
        echo "Cannot find '${tool##*/}' at: $INSTRACE_TOOLS/sve-scripts/memtrace_$tool."
        echo "Make sure the instrace-tools are built first."
        echo "You can set INSTRACE_TOOLS to use a custom path."
        echo "Stop."
        exit 3
    fi
done


function run_merge () {
    local binary="$1" tool="$INSTRACE_TOOLS/sve-scripts/memtrace_merger/bin/merge"

    if [ ! -x "$tool" ]; then
        echo -n "Not available"
        return
    fi

    "$tool" -o "merged-memtrace.$binary.log" "memtrace.$binary"*.log "sve-memtrace.$binary"*.log
}

function run_analyse () {
    local binary="$1" tool="$INSTRACE_TOOLS/sve-scripts/memtrace_analyzer/bin/analyze"

    if [ ! -x "$tool" ]; then
        echo -n "Not available"
        return
    fi

    "$tool" -t "$NTHREADS" -v "$sve_width" -o "analyze.$binary.log" "merged-memtrace.$binary"*.log
}

function run_bundle () {
    local binary="$1" tool="$INSTRACE_TOOLS/sve-scripts/memtrace_bundle/bin/bundle"

    if [ ! -x "$tool" ]; then
        echo -n "Not available"
        return
    fi

    "$tool" -t "$NTHREADS" -v "$sve_width" -o "bundle.$binary.log" "merged-memtrace.$binary"*.log
}


# set -x
cd "$results_dir" || exit

while IFS= read -r binary; do
    echo -n "$binary: "

    echo -n "Merge... "
    t="$(time (run_merge "$binary") 2>&1)"
    if grep -q "Not available" <<<"$t"; then
        echo -n "Not available; "
    else
        echo -n "$(awk '/real/ {print $2}' <<<"$t"); "
    fi

    echo -n "Analyze... "
    t="$(time (run_analyse "$binary") 2>&1)"
    if grep -q "Not available" <<<"$t"; then
        echo -n "Not available; "
    else
        echo -n "$(awk '/real/ {print $2}' <<<"$t"); "
    fi

    echo -n "Bundle... "
    t="$(time (run_bundle "$binary") 2>&1)"
    if grep -q "Not available" <<<"$t"; then
        echo -n "Not available; "
    else
        echo -n "$(awk '/real/ {print $2}' <<<"$t"). "
    fi

    echo "Done."
done < <(tail -n +2 "binaries.lst"); # Skip the first line because that's the common prefix

