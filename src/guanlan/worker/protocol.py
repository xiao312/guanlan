"""JSON transport must bypass pvpython's replaced sys.stdout/sys.stderr."""
import json
import os
import traceback


def emit(value):
    # VTK error capture redirects ParaView's Python console object as well.
    # Duplicating the descriptor preserves the actual SSH pipe and handles partial
    # writes through TextIOWrapper without closing the process's original stdout.
    with os.fdopen(os.dup(1), 'w', encoding='utf-8') as output:
        output.write('GUANLAN ' + json.dumps(value, allow_nan=False) + '\n')


def report_exception():
    with os.fdopen(os.dup(2), 'w', encoding='utf-8') as errors:
        traceback.print_exc(file=errors)
