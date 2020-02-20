/* ******************************************************************************
 * Copyright (c) 2014-2018 Google, Inc.  All rights reserved.
 * Copyright (c) 2011 Massachusetts Institute of Technology  All rights reserved.
 * Copyright (c) 2008 VMware, Inc.  All rights reserved.
 * ******************************************************************************/

/*
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * * Redistributions of source code must retain the above copyright notice,
 *   this list of conditions and the following disclaimer.
 *
 * * Redistributions in binary form must reproduce the above copyright notice,
 *   this list of conditions and the following disclaimer in the documentation
 *   and/or other materials provided with the distribution.
 *
 * * Neither the name of VMware, Inc. nor the names of its contributors may be
 *   used to endorse or promote products derived from this software without
 *   specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL VMWARE, INC. OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
 * SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 * CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 * LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
 * OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
 * DAMAGE.
 */

/* Code Manipulation API Sample:
 * opcodes_emulated.cpp
 *
 * Reports the dynamic count of the total number of instructions executed
 * broken down by opcode. Writes encoding of emulated instructions to file
 * undecoded.txt.
 *
 * based on api/samples/opcodes.c
 *
 * The runtime options for this client include:
 *   -noROI  Count instructions outside regions on interest.
 * The options are handled using the droption extension.
 */
#include "dr_api.h"
#include "drmgr.h"
#include "droption.h"
#include <map>
#include <cstdio>
#include <stdlib.h> /* qsort */

#define START_TRACE_INSTR 0x2520e020
#define STOP_TRACE_INSTR  0x2520e040

#define SHOW_RESULTS 1

#ifdef WINDOWS
# define DISPLAY_STRING(msg) dr_messagebox(msg)
#else
# define DISPLAY_STRING(msg) dr_printf("%s\n", msg);
#endif

#define NULL_TERMINATE(buf) buf[(sizeof(buf)/sizeof(buf[0])) - 1] = '\0'

static unsigned long long count[OP_LAST + 1];
#define NUM_COUNT OP_LAST+1
#define NUM_COUNT_SHOW 15

static droption_t<bool> noROI
(DROPTION_SCOPE_CLIENT, "noROI", false,
 "Count instructions outside the region-of-interest",
 "Count all app instructions, disregarding the region-of-interest");

using namespace std;

static FILE *file;
static map<uint,long> emulated;
static multimap<long,uint> ranks;

static int compare_counts(const void *, const void *);
static void event_exit(void);
static dr_emit_flags_t event_basic_block(void *drcontext, void *tag, instrlist_t *bb,
                                         bool for_trace, bool translating);

static bool enable_inscount = false;

/* Function to enable instruction count inside a region-of-interest.
 * It will be planted by a clean call at the marker instructions in the code.
 */
static void enableROI(bool en)
{
    if(en)
        enable_inscount = true;
    else
        enable_inscount = false;
}

DR_EXPORT void
dr_client_main(client_id_t id, int argc, const char *argv[])
{
    dr_set_client_name("DynamoRIO Sample Client 'opcodes_emulated'",
                       "http://dynamorio.org/issues");
    /* Options */
    if (!droption_parser_t::parse_argv(DROPTION_SCOPE_CLIENT, argc, argv, NULL, NULL))
        DR_ASSERT(false);

    /* Count all instructions if no region-of-interest flag is set */
    if (noROI.get_value())
        enable_inscount = true;

    if (!drmgr_init())
        DR_ASSERT(false);

    /* Register events: */
    dr_register_exit_event(event_exit);
    if (!drmgr_register_bb_app2app_event(event_basic_block, NULL))
        DR_ASSERT(false);

    /* Make it easy to tell from the log file which client executed. */
    dr_log(NULL, DR_LOG_ALL, 1, "Client 'opcodes_emulated' initializing\n");
#ifdef SHOW_RESULTS
    /* Also give notification to stderr. */
    if (dr_is_notify_on()) {
#    ifdef WINDOWS
        /* Ask for best-effort printing to cmd window.  Must be called at init. */
        dr_enable_console_printing();
#    endif
        dr_fprintf(STDERR, "Client opcodes_emulated is running\n");
    }
#endif
    file = fopen("undecoded.txt","w");
}

static void
event_exit(void)
{
#ifdef SHOW_RESULTS
    char msg[(NUM_COUNT_SHOW + 2) * 80];
    int len, i;
    size_t sofar = 0;
    /* First, sort the counts */
    uint indices[NUM_COUNT];
    /* Initialise indices */
    for (i = 0; i < NUM_COUNT; i++)
        indices[i] = i;
    qsort(indices, NUM_COUNT, sizeof(indices[0]), compare_counts);

    len = dr_snprintf(msg, sizeof(msg) / sizeof(msg[0]),
                      "Opcode execution counts in AArch64 mode:\n");
    DR_ASSERT(len > 0);
    sofar += len;
    for (i = OP_LAST - 1 - NUM_COUNT_SHOW; i <= OP_LAST; i++) {
        if(count[indices[i]] != 0) {
            len = dr_snprintf(msg + sofar, sizeof(msg) / sizeof(msg[0]) - sofar,
                              "  %9lu : %-15s\n", count[indices[i]],
                              decode_opcode_name(indices[i]));
            DR_ASSERT(len > 0);
            sofar += len;
        }
    }
    len = dr_snprintf(msg + sofar, sizeof(msg) / sizeof(msg[0]) - sofar,
          "%u unique emulated instructions written to undecoded.txt\n",
           emulated.size());
    DR_ASSERT(len > 0);
    sofar += len;
    NULL_TERMINATE(msg);
    DISPLAY_STRING(msg);
#endif /* SHOW_RESULTS */
    map<uint,long>::iterator iter;
    multimap<long,uint>::reverse_iterator iter2;

    for(iter=emulated.begin(); iter!=emulated.end();++iter) {
        ranks.insert(make_pair(iter->second,iter->first));
    }

    for(iter2=ranks.rbegin(); iter2!=ranks.rend(); ++iter2) {
        fprintf(file, "%9lu : 0x%08x\n", iter2->first, iter2->second);
    }

    fclose(file);
    emulated.clear();

    if (!drmgr_unregister_bb_app2app_event(event_basic_block))
      DR_ASSERT(false);
    drmgr_exit();
}

static int
compare_counts(const void *a_in, const void *b_in)
{
    const uint a = *(const uint *)a_in;
    const uint b = *(const uint *)b_in;
    if (count[a] > count[b])
        return 1;
    if (count[a] < count[b])
        return -1;
    return 0;
}

static void
record_emulated_inst(uint code)
{
    if(enable_inscount)
        emulated[code]++;
}

static void
opcount(uint opcode)
{
    if(enable_inscount)
        count[opcode]++;
}

static bool is_emulation = false;

static dr_emit_flags_t
event_basic_block(void *drcontext, void *tag, instrlist_t *bb,
                  bool for_trace, bool translating)
{
    instr_t *instr;

    for (instr = instrlist_first(bb);
         instr != NULL;
         instr = instr_get_next(instr)) {

        if (drmgr_is_emulation_start(instr)) {
            is_emulation = true;

            emulated_instr_t emulated;
            drmgr_get_emulated_instr_data(instr, &emulated);

            /* When instrumenting a region-of-interest, enable the counting
             * at the markers in the code, through a clean call.
             */
            if (!noROI.get_value()){
                if (instr_get_raw_word(emulated.instr, 0) == START_TRACE_INSTR){
                    dr_insert_clean_call(drcontext, bb, instr,
                                        (void *)enableROI, false /* save fpstate */, 1,
                                        OPND_CREATE_INT8(true));
                    continue;
                }
                if (instr_get_raw_word(emulated.instr, 0) == STOP_TRACE_INSTR){
                    dr_insert_clean_call(drcontext, bb, instr,
                                        (void *)enableROI, false /* save fpstate */, 1,
                                        OPND_CREATE_INT8(false));
                    continue;
                }
            }

            dr_insert_clean_call(drcontext, bb, instr,
                                 (void *)record_emulated_inst, false, 1,
                                 OPND_CREATE_INT32(instr_get_raw_word(emulated.instr, 0)));
        }
        if (drmgr_is_emulation_end(instr))
            is_emulation = false;
        if (is_emulation)
            continue;
        if (!instr_is_app(instr))
            continue;

        dr_insert_clean_call(drcontext, bb, instr,
                             (void *)opcount, false, 1,
                             OPND_CREATE_INT32(instr_get_opcode(instr)));
    }

    return DR_EMIT_DEFAULT;
}
