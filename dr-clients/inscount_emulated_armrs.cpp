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
 * inscount_emulated.cpp
 *
 * Reports the dynamic count of the total number of native and emulated
 * instructions executed.
 * Illustrates how to perform performant clean calls.
 * Demonstrates effect of clean call optimization and auto-inlining with
 * different -opt_cleancall values.
 *
 * The runtime options for this client include:
 *   -shared_libs  Count instructions in shared libraries.
 * The options are handled using the droption extension.
 */

#include "dr_api.h"
#include "drmgr.h"
#include "droption.h"
#include <string.h>
#include <atomic>

// #include "sve_client.h"
#define START_TRACE_INSTR 0x2520e020
#define STOP_TRACE_INSTR  0x2520e040


#define SHOW_RESULTS 1

#ifdef WINDOWS
# define DISPLAY_STRING(msg) dr_messagebox(msg)
#else
# define DISPLAY_STRING(msg) dr_printf("%s\n", msg);
#endif

#define NULL_TERMINATE(buf) buf[(sizeof(buf)/sizeof(buf[0])) - 1] = '\0'

static droption_t<bool> shared_libs
(DROPTION_SCOPE_CLIENT, "shared_libs", false,
 "count all app and lib instructions",
 "Count all instructions in the application itself, and  instructions in "
 "shared libraries.");

static droption_t<bool> noROI
(DROPTION_SCOPE_CLIENT, "noROI", false,
 "Count instructions outside the region-of-interest",
 "Count all app instructions, disregarding the region-of-interest");

/* Application module */
static app_pc exe_start;
/* There are two instruction counts: native and emulated instructions */
typedef struct counts {
    std::atomic<uint64> native_instrs{0};
    std::atomic<uint64> emulated_instrs{0};
} instr_counts;
static instr_counts global_counts;

static bool enable_inscount = false;

/* Function to enable instruction count inside a region-of-interest.
 * It will be planted by a clean call at the marker instructions in the code.
 */
static void enableROI(bool en, uint64 native_instrs, uint64 emulated_instrs)
{
    if(en){
        enable_inscount = true;
        global_counts.native_instrs = global_counts.native_instrs - native_instrs;
        global_counts.emulated_instrs = global_counts.emulated_instrs - emulated_instrs;
    }
    else{
        enable_inscount = false;
        global_counts.native_instrs = global_counts.native_instrs + native_instrs;
        global_counts.emulated_instrs = global_counts.emulated_instrs + emulated_instrs;
    }
}

/* This is the instruction counter function which will be planted by the clean
 * call.
 */
static void inscount(uint64 native_instrs, uint64 emulated_instrs)
{
    if(enable_inscount){
        global_counts.native_instrs = global_counts.native_instrs + native_instrs;
        global_counts.emulated_instrs = global_counts.emulated_instrs + emulated_instrs;
    }
}
static void event_exit(void);
static dr_emit_flags_t event_bb_analysis(void *drcontext, void *tag,
                                         instrlist_t *bb,
                                         bool for_trace, bool translating);

DR_EXPORT void
dr_client_main(client_id_t id, int argc, const char *argv[])
{
    dr_set_client_name("DynamoRIO Sample Client 'inscount'",
                       "http://dynamorio.org/issues");

    /* Options */
    if (!droption_parser_t::parse_argv(DROPTION_SCOPE_CLIENT, argc, argv, NULL, NULL))
        DR_ASSERT(false);
    drmgr_init();

    /* Get main module address */
    if (!shared_libs.get_value()) {
        module_data_t *exe = dr_get_main_module();
        if (exe != NULL)
            exe_start = exe->start;
        dr_free_module_data(exe);
    }

    dr_register_exit_event(event_exit);
    if (!drmgr_register_bb_app2app_event(event_bb_analysis, NULL))
        DR_ASSERT(false);

    /* make it easy to tell, by looking at log file, which client executed */
    dr_log(NULL, DR_LOG_ALL, 1, "Client 'inscount' initializing\n");
#ifdef SHOW_RESULTS
    /* also give notification to stderr */
    if (dr_is_notify_on()) {
# ifdef WINDOWS
        /* ask for best-effort printing to cmd window.  must be called at init. */
        dr_enable_console_printing();
# endif
        dr_fprintf(STDERR, "Client inscount is running\n");
    }
#endif
}

static void
event_exit(void)
{
#ifdef SHOW_RESULTS
    char msg[512];
    int len;
    len = dr_snprintf(msg, sizeof(msg)/sizeof(msg[0]),
          "%llu instructions executed of which %llu were emulated instructions\n",
           uint64(global_counts.native_instrs) + uint64(global_counts.emulated_instrs),
           uint64(global_counts.emulated_instrs));
    DR_ASSERT(len > 0);
    NULL_TERMINATE(msg);
    DISPLAY_STRING(msg);
#endif /* SHOW_RESULTS */
    if (!drmgr_unregister_bb_app2app_event(event_bb_analysis))
      DR_ASSERT(false);
    drmgr_exit();
}

static dr_emit_flags_t
event_bb_analysis(void *drcontext, void *tag, instrlist_t *bb,
                  bool for_trace, bool translating)
{
    instr_t *instr, *next_instr;
    instr_counts bb_counts;

#ifdef VERBOSE
    dr_printf("in dynamorio_basic_block(tag=" PFX")\n", tag);
# ifdef VERBOSE_VERBOSE
    instrlist_disassemble(drcontext, tag, bb, STDOUT);
# endif
#endif

    /* By default drmgr enables auto-predication, which predicates all instructions with
     * the predicate of the current instruction on ARM.
     * We disable it here because we want to unconditionally execute the following
     * instrumentation.
     */
    drmgr_disable_auto_predication(drcontext, bb);

    /* Only count in app BBs */
    if (!shared_libs.get_value()) {
        module_data_t *mod = dr_lookup_module(dr_fragment_app_pc(tag));
        if (mod != NULL) {
            bool from_exe = (mod->start == exe_start);
            dr_free_module_data(mod);
            if (!from_exe)
                return DR_EMIT_DEFAULT;
        }
    }

    /* Count instructions */
    bb_counts.native_instrs = bb_counts.emulated_instrs = 0;
    bool is_emulation = false;

    /* Count all instructions if no region-of-interest flag is set */
    if (noROI.get_value())
        enable_inscount = true;

    for (instr = instrlist_first(bb); instr != NULL; instr = next_instr) {
        next_instr = instr_get_next(instr);

        if (drmgr_is_emulation_start(instr)) {
            is_emulation = true;
            /* Data about the emulated instruction can be extracted from the
             * start label using drmgr_get_emulated_instr_data().
             */
            emulated_instr_t emulated;
            drmgr_get_emulated_instr_data(instr, &emulated);

            /* When instrumenting a region-of-interest, enable the counting
             * at the markers in the code, through a clean call.
             */
            if (!noROI.get_value()){
                if (instr_get_raw_word(emulated.instr, 0) == START_TRACE_INSTR){
                    dr_insert_clean_call(drcontext, bb, instr,
                                        (void *)enableROI, false /* save fpstate */, 3,
                                        OPND_CREATE_INT8(true),
                                        OPND_CREATE_INT64(bb_counts.native_instrs),
                                        OPND_CREATE_INT64(bb_counts.emulated_instrs));
                    continue;
                }
                if (instr_get_raw_word(emulated.instr, 0) == STOP_TRACE_INSTR){
                    dr_insert_clean_call(drcontext, bb, instr,
                                        (void *)enableROI, false /* save fpstate */, 3,
                                        OPND_CREATE_INT8(false),
                                        OPND_CREATE_INT64(bb_counts.native_instrs),
                                        OPND_CREATE_INT64(bb_counts.emulated_instrs));
                    continue;
                }
            }
            bb_counts.emulated_instrs++;
            continue;
        }
        if (drmgr_is_emulation_end(instr)) {
            is_emulation = false;
            continue;
        }
        if (is_emulation)
            continue;
        if (!instr_is_app(instr))
            continue;

        bb_counts.native_instrs++;
    }

     /* Insert clean call */
     dr_insert_clean_call(drcontext, bb, instrlist_last_app(bb),
                          (void *)inscount, false /* save fpstate */, 2,
                          OPND_CREATE_INT64(bb_counts.native_instrs),
                          OPND_CREATE_INT64(bb_counts.emulated_instrs));

#if defined(VERBOSE) && defined(VERBOSE_VERBOSE)
    dr_printf("Finished counting for dynamorio_basic_block(tag=" PFX")\n", tag);
    instrlist_disassemble(drcontext, tag, bb, STDOUT);
#endif
    return DR_EMIT_DEFAULT;
}
