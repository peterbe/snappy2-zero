from __future__ import print_function

import sys
import time
import json
from pprint import pprint

import requests


def run(fp, url):
    body = json.load(open(fp))
    body['debug'] = True
    t0 = time.time()
    r = requests.post(url, json=body)
    t1 = time.time()
    if r.status_code == 200:
        rj = r.json()
        debug = rj.pop('debug')
        print(json.dumps(rj, indent=4))
        print(
            json.dumps(debug, indent=4),
            file=sys.stderr,
        )
        print(
            'TOOK {:.4f} seconds'.format(t1 - t0),
            file=sys.stderr
        )
    else:
        print(r)
        print(r.text)


if __name__ == '__main__':
    import sys
    run(*sys.argv[1:])
