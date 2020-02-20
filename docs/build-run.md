# Build and Run Instructions

## DR Clients

**Important**: If using `oprecord`, use `_apponly` for applications which build with OpenMP or MPI. For the Cray compiler, set `CRAYPE_LINK_TYPE=dynamic`

## STREAM

Use plain McCalpin STREAM: <https://www.cs.virginia.edu/stream/FTP/Code/stream.c>.

### Compile

    gcc -march=armv8.1-a+sve -O3 -ffast-math -DSTREAM_ARRAY_SIZE=4194304 -DNTIMES=2 -fno-openmp
    armclang -march=armv8.1-a+sve -O3 -fsimdmath -DSTREAM_ARRAY_SIZE=4194304 -DNTIMES=2 -fno-openmp
    cc -hnoomp -DSTREAM_ARRAY_SIZE=4194304 -DNTIMES=2

### Run

    ./stream


## BUDE

Use <https://github.com/UoB-HPC/bude-benchmark>, `armv8` branch.

### Compile

    gcc -std=c99 -Wall -Ofast -ffast-math -mcpu=thunderx2t99+sve bude.c vec-pose-inner.c -DWGSIZE=64 -fopenmp
    armclang -std=c99 -Wall -Ofast -ffast-math -mcpu=thunderx2t99+sve -fsimdmath bude.c vec-pose-inner.c -DWGSIZE=64 -fopenmp
    cc -hstd=c99 -homp bude.c vec-pose-inner.c -DWGSIZE=64

### Run

    OMP_NUM_THREADS=1 ./bude -n 1024 -i 1


## TeaLeaf

Use <https://github.com/UoB-HPC/TeaLeaf>, `2d` folder.

### Compile

    make -B CC=armclang CPP=armclang++ OPTIONS='-DNO_MPI -mcpu=thunderx2t99+sve -fno-openmp'
    make -B CC=gcc CPP=g++ OPTIONS='-DNO_MPI -mcpu=thunderx2t99+sve -fno-openmp'
    make -B CC=cc CPP=CC COMPILER=CRAY OPTIONS='-DNO_MPI -hnoomp'

### Run

Use `tea_bm_1.in` input.

    ./tealeaf


## CloverLeaf

Use <https://github.com/UK-MAC/CloverLeaf_ref>.

### Compile

    make -B COMPILER=GNU MPI_COMPILER=mpifort C_MPI_COMPILER=mpicc CFLAGS_GNU="-Ofast -ffast-math -ffp-contract=fast -mcpu=thunderx2t99+sve -funroll-loops" FLAGS_GNU="-Ofast -ffast-math -ffp-contract=fast -mcpu=thunderx2t99+sve -funroll-loops"
    make -B COMPILER=GNU MPI_COMPILER=mpifort C_MPI_COMPILER=mpicc CFLAGS_GNU="-Ofast -ffast-math -ffp-contract=fast -mcpu=thunderx2t99+sve -funroll-loops" FLAGS_GNU="-Ofast -ffast-math -ffp-contract=fast -mcpu=thunderx2t99+sve -funroll-loops"

    make -B COMPILER=CRAY C_MPI_COMPILER=cc MPI_COMPILER=ftn
    make -B COMPILER=CRAY C_MPI_COMPILER=cc MPI_COMPILER=ftn CFLAGS_CRAY="-Ofast -ffast-math -ffp-contract=fast -mcpu=thunderx2t99 -funroll-loops -fopenmp -fno-vectorize -fno-slp-vectorize" FLAGS_CRAY='-homp -hvector0 -hfp1' # for no-vec

### Run

Use the small (default) `clover.in`, but remove `profiler_on` and reduce `end_stepr=4`.

    ./clover_leaf


## MegaSweep

Use <https://github.com/UK-MAC/mega-stream/>, `sweep3d` folder.

### Compile

     make -B COMPILER=GNU FFLAGS_GNU='-O3 -ffree-line-length-none -mcpu=thunderx2t99+sve'
     make -B COMPILER=CRAY FFLAGS_CRAY='-homp'
     make -B COMPILER=CRAY FFLAGS_CRAY='-homp -hvector0 -hfp1' # for no-vec

### Run

Either set the parameters in `mega-sweep3d.f90` before compiling of use CLI args (run with `-h` to list them):

```
nx = 16
ny = 16
nz = 16
ng = 16
nang = 136
nsweeps = 8
chunk = 16
ntimes = 2
```

For memtrace or oprecord, use:

```
nx = 4
ny = 4
nz = 4
chunk = 4
ntimes = 1
```

    ./mega-sweep3d
    ./mega-sweep3d-sve-gcc8.2 --ntimes 1 --prof --nx 4 --ny 4 --nz 4 --chunk 4


## Neutral

### Compile

    git clone https://github.com/UoB-HPC/arch
    cd arch
    git checkout f19d9325d9

    git clone https://github.com/UoB-HPC/neutral
    cd neutral
    git checkout d983598634

    sed -i '/defined(__powerpc__)$/s/$/ \&\& !defined(__aarch64__)/' $SRC_DIR/Random123/features/gccfeatures.h

    make COMPILER=GCC ARCH_COMPILER_CC=gcc ARCH_COMPILER_CPP=g++ CFLAGS_GCC="-std=gnu99 -Wall -fopenmp -Ofast -mcpu=thunderx2t99+sve -ffast-math -ffp-contract=fast
    COMPILER=CRAY ARCH_COMPILER_CC=cc ARCH_COMPILER_CPP=CC CFLAGS_CRAY=-hfp2

### Run

Edit the following in `problems/csp.params` (or make a copy), leaving everything else the same:

```
nx                400
ny                400
iterations        1
```

    ./neutral-omp3 problems/csp-small.params


## MiniFMM

Use <https://github.com/uob-hpc/minifmm-cpp>.

### Compile

    make ARCH=thunderx2t99+sve
    make ARCH=thunderx2t99+sve CC_GNU=armclang++

### Run

    ./fmm.omp -n 50000 -m 1000 -e 0.5 -t 4 -c 32 # For instrace
    ./fmm.omp -n 10000 -m 0 -e 0.5 -t 3 -c 32 # For memtrace, smaller problem
    ./fmm.omp -i inputs/small.in # where the flags above go in *.in, one per line
