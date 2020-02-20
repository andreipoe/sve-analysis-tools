#!/bin/bash

set -u
set -o pipefail

if [ "${BASH_VERSINFO[0]}" -lt 4 ]; then
    echo "This script requires Bash version 4 or later."
    echo "You are running Bash $BASH_VERSION"
    echo "Stop."
    exit 3
fi

if [ $# -lt 2 ]; then
    echo "Usage: armie-wrapper <sve-width> <binaries>"
    exit 1
fi

armie="$(which armie 2>/dev/null)"
if [ -z "${armie:-}" ]; then
    echo "'armie' command not found."
    echo "Have you loaded the right modules?"
    echo "Stop."
    exit 2
fi

if [ -z "${LLVM_MC:-}" ]; then
    echo "LLVM_MC environment variable not set."
    echo "This is required for decoding SVE instructions."
    echo "Stop."
    exit 6
fi

if [ "$(python3 -c 'import sys; print(sys.version_info[0])')" -lt 3 ] || [ "$(python3 -c 'import sys; print(sys.version_info[1])')" -lt 7 ]; then
    echo "Your Python version is: $(python3 --version)"
    echo "Python 3.7+ is required for decoding AArch64 instructions."
    echo "Stop."
    exit 8
fi


script_dir="$(realpath "$(dirname "$(realpath "$0")")")"


function run_opcodes () {
    local binary dir output launcher
    binary="$1"
    dir="$2"

    launcher=""
    if readelf -d "$binary" | grep -qi 'libmpi.*\.so' || nm "$binary" | grep -qi mpi; then
        if env | grep -q '^CRAY.*='; then
            launcher="aprun -b -n 1"
        else
            launcher="mpirun -np 1"
        fi
    fi
    client="liboprecord_emulated.so"
    if [ "$app_only" = yes ]; then
        client="liboprecord_emulated_apponly.so"
    fi

    output="$($launcher armie -msve-vector-bits="$svewidth" -i "$client" -- "$(realpath "$binary")" ${args[@]+"${args[@]}"} |& tee "${dir}/opcodes_${binary}.out")"
    mv undecoded.txt "$dir/undecoded_${binary}.txt"
    mv a64-undecoded.txt "$dir/a64-undecoded_${binary}.txt"

    awk '{print $3}' "${dir}/undecoded_${binary}.txt" | "${armie_dir}/bin64/enc2instr.py" > "${dir}/decoded_${binary}.txt"

    "${script_dir}/count-neon.py" "$binary" "${dir}/a64-undecoded_${binary}.txt" > "${dir}/a64-count_${binary}.txt"
    mv disas.out "${dir}/disas_${binary}.out"
}

function run_memtrace () {
    local binary dir output memtrace svememtrace launcher
    binary="$1"
    dir="$2"

    launcher=""
    if readelf -d "$binary" | grep -qi 'libmpi.*\.so'; then
        if env | grep -q '^CRAY.*='; then
            launcher="aprun -n 1"
        else
            launcher="mpirun -np 1"
        fi
    fi

    output="$($launcher armie -e libmemtrace_sve_"$svewidth".so -i libmemtrace_simple.so -- "$(realpath "$binary")" ${args[@]+"${args[@]}"} |& tee "${dir}/memtrace_${binary}.out")"
    memtrace="$(basename "$(awk 'NR==1 {print $3}' <<<"$output")")"
    mv "$memtrace" "$dir/."

    svememtrace="sve-${memtrace%.*.log}.log"
    mv "$svememtrace" "$dir/."
}


ts="$(date "+%Y-%m-%d_%H-%M-%S")"

(armie_dir="$(dirname "$(dirname "$armie")")"
echo "ArmIE is installed in: $armie_dir"

inscount_only=no
memtrace_only=no
app_only=no

while getopts ":aoim" opt; do
    case "$opt" in
        o|i)
            inscount_only=yes
            ;;
        m)
            memtrace_only=yes
            ;;
        a)
            app_only=yes
            ;;
        \?)
            echo "Invalid option: -$OPTARG"
            exit 7
            ;;
    esac
done

shift $(( $OPTIND -1 ))

if [ "$1" -lt 128 ] || [ "$1" -gt 2048 ]; then
    echo "Invalid SVE width: $1"
    echo "Valid options are multiples of 128 between 128 and 2048."
    exit 4
fi
svewidth="$1"
echo "Selected SVE width: $svewidth"

prefix="$2"
mapfile -t binaries < <(ls "$prefix"*)
echo "Binaries to run: ${binaries[*]}"

shift 2
args=( $@ )
[ ${#args[@]} -ne 0 ] && echo "Arguments: ${args[*]}"

results="results_${prefix}_sve${svewidth}_${ts}"
if [ -d "$results" ]; then
    echo "Directory already exists: $results"
    echo "Something went wrong."
    echo "Stop."
    exit 5
else
    mkdir "$results"
    echo "Results directory: $results"
fi
[ "$app_only" = yes ] && echo "Counting app instructions only"

echo "$prefix" > "$results/binaries.lst"
echo "svewidth = $svewidth" >> "$results/run.cfg"
echo "time = $ts" >> "$results/run.cfg"

echo
for b in "${binaries[@]}"; do
    echo -n "$(basename "$b"): "
    basename "$b" >> "$results/binaries.lst"

    if [ "$memtrace_only" = no ]; then
        echo -n "inscount... "
        t="$(time (run_opcodes "$b" "$results") 2>&1)"
        echo -n "$(awk '/real/ {print $2}' <<<"$t") "
    fi

    if [ "$inscount_only" = no ]; then
        echo -n "memtrace... "
        t="$(time (run_memtrace "$b" "$results") 2>&1)"
        echo -n "$(awk '/real/ {print $2}' <<<"$t") "
    fi

    echo "Done."
done

# If we've collected a memory trace, process it using the instrace tools
if [ "$inscount_only" = no ]; then
    "$script_dir/run-instrace-tools.sh" "$results" "$svewidth"
    "$script_dir/utils/clean-instrace-tools-output.sh" "$results"
fi

echo "All done."

) |& tee "wrapper_${ts}.log"
