import json
from pprint import pprint
from bisect import bisect

import requests

from django.conf import settings
from django import http
# from django.core.cache import cache # XXX redis!
from django.core.cache import caches


redis = caches['redis']


class SymbolDownloadError(Exception):
    def __init__(self, status_code, url):
        self.status_code = status_code
        self.url = url


def symbolicate_json(request):
    json_body = json.loads(request.body.decode('utf-8'))
    stacks = json_body['stacks']
    memory_map = json_body['memoryMap']
    assert json_body['version'] == 4, json_body['version']

    response = {
        'symbolicatedStacks': [],
        'knownModules': [False] * len(memory_map),
    }

    for stack in stacks:
        response_stack = []
        for module_index, module_offset in stack:
            if module_index < 0:
                response_stack.append(hex(module_offset))
            else:
                symbol_filename = memory_map[module_index][0]
                response_stack.append(
                    "{} (in {})".format(hex(module_offset), symbol_filename)
                )
        response['symbolicatedStacks'].append(response_stack)

    # per request global map of all symbol maps
    all_symbol_maps = {}

    unresolved_frames = []
    for i, stack in enumerate(stacks):
        for j, (module_index, module_offset) in enumerate(stack):
            if module_index < 0:
                continue

            symbol_filename, symbold_debug_id = memory_map[module_index]
            symbol_key = (symbol_filename, symbold_debug_id)
            if symbol_key not in all_symbol_maps:
                # We have apparently NOT looked up this symbol file + ID before
                symbol_map, found = get_symbol_map(*symbol_key)
                # When inserting to the function global all_symbol_maps
                # store it as a tuple with an additional value (for
                # the sake of optimization) of the sorted list of ALL
                # offsets as int16s ascending order.
                all_symbol_maps[symbol_key] = (
                    symbol_map,
                    found,
                    sorted(symbol_map)
                )
            symbol_map, found, symbol_offset_list = all_symbol_maps.get(
                symbol_key,
                ({}, False, [])
            )
            signature = symbol_map.get(module_offset)
            if signature is None and symbol_map:
                try:
                    signature = symbol_map[
                        symbol_offset_list[
                            bisect(symbol_offset_list, module_offset) - 1
                        ]
                    ]
                except IndexError:
                    # XXX How can this happen?!
                    print("INDEXERROR:", module_offset, bisect(symbol_offset_list, module_offset) - 1)
                    signature = None

            response['symbolicatedStacks'][i][j] = (
                '{} (in {})'.format(
                    signature or hex(module_offset),
                    symbol_filename,
                )
            )
            response['knownModules'][module_index] = found

    return http.JsonResponse(response)


def get_symbol_map(filename, debug_id):
    cache_key = '{}/{}'.format(filename, debug_id)
    symbol_map = redis.get(cache_key)
    if symbol_map is None: # XXX _marker()?
        # need to download this from the internet
        symbol_map = load_symbol(filename, debug_id)
        if symbol_map is None:
            # print("SYMBOL_MAP WAS NONE!")
            return {}, False
        else:
            # print("Storing a {} bytes symbol_map".format(len(str(symbol_map))))
            redis.set(cache_key, symbol_map, 60*100)  # XXX Consider using timeout=None to store it indefinitely
            return symbol_map, True
    else:
        # print('CACHE HIT', cache_key)
        # If it was in cache, that means it was originally found.
        return symbol_map, True


def load_symbol(filename, debug_id):
    downloaded = download_symbol(filename, debug_id)
    if not downloaded:
        # XXX perhaps this should be logged in memcache so that
        # we don't try to download it again for the next request.
        print("COULD NOT BE DOWNLOADED")
        return
    content, url = downloaded
    if not content:
        print("EMPTY CONTENT")
        return

    # Need to parse it by line and make a dict of of offset->signature
    public_symbols = {}
    func_symbols = {}
    line_number = 0
    for line in content.splitlines():
        # if 'KiUserCallbackDispatcher' in line:
        #     print(repr(line))
            # raise Exception("LINE")
        line_number += 1
        if line.startswith('PUBLIC '):
            fields = line.strip().split(None, 3)
            if len(fields) < 4:
                logger.warn(
                    'PUBLIC line {} in {} has too few fields'.format(
                        line_number,
                        url,
                    )
                )
                continue
            address = int(fields[1], 16)
            symbol = fields[3]
            # public_symbols[hex(address)] = symbol
            public_symbols[address] = symbol
        elif line.startswith('FUNC '):
            fields = line.strip().split(None, 4)
            if len(fields) < 4:
                logger.warn(
                    'FUNC line {} in {} has too few fields'.format(
                        line_number,
                        url,
                    )
                )
                continue
            address = int(fields[1], 16)
            symbol = fields[4]
            # func_symbols[hex(address)] = symbol
            func_symbols[address] = symbol

    # Prioritize PUBLIC symbols over FUNC symbols # XXX why?
    func_symbols.update(public_symbols)
    with open('/tmp/symbols/{}.json'.format(filename), 'w') as f:
        print('WROTE', '/tmp/symbols/{}.json'.format(filename))
        json.dump(func_symbols, f, indent=4, sort_keys=True)
    return func_symbols


def download_symbol(lib_filename, debug_id):
    if lib_filename.endswith('.pdb'):
        symbol_filename = lib_filename[:-4] + '.sym'
    else:
        symbol_filename = lib_filename + '.sym'

    for base_url in settings.SYMBOL_URLS:
        assert base_url.endswith('/')
        url = '{}{}/{}/{}'.format(
            base_url,
            lib_filename,
            debug_id,
            symbol_filename
        )
        print("Requesting {}".format(url))
        response = requests.get(url)
        if response.status_code == 200:  # Note! This includes redirects
            # print(repr(response.text[:100]))
            return response.text, url
        elif response.status_code == 404:
            print("Tried {} but 404".format(url))
        else:
            # XXX Need more grace. A download that isn't 200 or 404 means
            # either a *temporary* network operational error or something
            # horribly wrong with the URL.
            raise SymbolDownloadError(response.status_code, url)

    # None of the URLs worked
