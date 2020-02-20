# Custom DynamoRIO Client

This folder contains custom instrumentation clients for use with ArmIE.

## Building

1. Place these files in the ArmIE `samples` directory.
2. Add them to the `CMakeLists.txt` script:
    ```
    add_sample_client(inscount_emulated_armrs "inscount_emulated_armrs.cpp" "drmgr;droption")
    add_sample_client(opcodes_emulated_roi     "opcodes_emulated_roi.cpp"   "drmgr;drreg;droption")
    add_sample_client(oprecord_emulated       "oprecord_emulated.cpp"       "drmgr;drreg;droption")
    add_sample_client(oprecord_emulated_apponly       "oprecord_emulated_apponly.cpp"       "drmgr;drreg;droption")
    ```
3. Build using `cmake . && make`.
4. Copy the generated libraries to the `bin64` folder.

More detailed instructions [this Arm Developer page](https://developer.arm.com/tools-and-software/server-and-hpc/arm-architecture-tools/arm-instruction-emulator/building-an-emulation-aware-instrumentation-client).
