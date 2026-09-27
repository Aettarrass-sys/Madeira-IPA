/* The Apple Metal Shader Converter headers are a separately supplied build
 * input. Keep the D3D12 unix-call ABI present when that package is absent so
 * the D3D11/DXMT path can still link and report D3D12 unavailability cleanly. */
#include "../../research/madeira-d3d12/src/madeira_ir_abi.h"
#include <stdio.h>

int madeira_ir_convert(void *raw) {
    struct madeira_ir_convert_args *args = raw;
    if (args) {
        args->ret_status = MADEIRA_IR_NO_DYLIB;
        snprintf(args->ret_note, sizeof args->ret_note,
                 "Metal Shader Converter package was unavailable at build time");
    }
    return 0; /* The unix call completed; ret_status carries the failure. */
}

int madeira_d3d12_canary_run_log(const char *fixture_dir, const char *dylib_path,
                                  void (*sink)(const char *), const char *log_path,
                                  const char *build_id) {
    const char *message = "D3D12 canary unavailable: Metal Shader Converter headers were absent at build time\n";
    (void)fixture_dir;
    (void)dylib_path;
    (void)build_id;
    if (sink) sink(message);
    if (log_path && *log_path) {
        FILE *log = fopen(log_path, "w");
        if (log) { fputs(message, log); fclose(log); }
    }
    return 1;
}
