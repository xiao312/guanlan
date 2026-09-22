"""JSON-line worker; all expensive operations occur inside the Slurm allocation."""
import argparse
import json
import os
import select
import sys
import traceback

from guanlan.casepage import validate_document
from guanlan.worker.pipeline import Pipeline
from guanlan.worker.protocol import emit, report_exception


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--idle', type=int, default=300)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('worker requires a Slurm allocation; do not run on a login node')
    emit({'event': 'loading', 'message': 'Opening decomposed OpenFOAM reader'})
    pipeline = Pipeline(args.case, args.workspace)
    emit({'event': 'ready', 'fields': pipeline.catalog(), 'job_id': os.environ['SLURM_JOB_ID']})
    # pvpython replaces sys.stdin with a console wrapper without fileno().
    # Read the actual SSH/srun pipe, not ParaView's interactive console object.
    input_pipe = os.fdopen(os.dup(0), 'r')
    last_revision = None
    while select.select([input_pipe], [], [], args.idle)[0]:
        line = input_pipe.readline(65537)
        if not line:
            return
        try:
            if len(line) > 65536:
                raise ValueError('request too large')
            request = json.loads(line)
            document = validate_document(request['document'], pipeline.catalog())
            result = pipeline.render(document)
            if result.get('cache_hit') and request['revision'] == last_revision:
                emit({'event': 'unchanged', 'revision': request['revision']})
            else:
                emit({'event': 'preview', 'revision': request['revision'], 'result': result})
            last_revision = request['revision']
        except Exception as error:
            report_exception()
            emit({'event': 'error', 'message': str(error)})
    emit({'event': 'idle', 'message': 'worker idle timeout; allocation released'})


if __name__ == '__main__':
    main()
