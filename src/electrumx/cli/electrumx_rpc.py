#!/usr/bin/env python3
#
# Copyright (c) 2016-2018, Neil Booth
#
# All rights reserved.
#
# See the file "LICENCE" for information about the copyright
# and warranty status of this software.

'''Script to send RPC commands to a running ElectrumX server.'''


import argparse
import asyncio
import json
import sys
from os import environ

from aiorpcx import timeout_after, connect_rs
import electrumx.lib.text as text


simple_commands = {
    'getinfo': 'Print a summary of server state',
    'groups': 'Print current session groups',
    'peers': 'Print information about peer servers for the same coin',
    'sessions': 'Print information about client sessions',
    'stop': 'Shut down the server cleanly',
}

session_commands = {
    'disconnect': 'Disconnect sessions',
    'log': 'Control logging of sessions',
}

other_commands = {
    'add_peer': (
        'add a peer to the peers list',
        [], {
            'type': str,
            'dest': 'real_name',
            'help': 'e.g. "a.domain.name s995 t"',
        },
    ),
    'daemon_url': (
        "replace the daemon's URL at run-time, and forecefully rotate "
        " to the first URL in the list",
        [], {
            'type': str,
            'nargs': '?',
            'default': '',
            'dest': 'daemon_url',
            'help': 'see documentation of DAEMON_URL envvar',
        },
    ),
    'query': (
        'query the UTXO and history databases',
        ['-l', '--limit'], {
            'type': int,
            'default': 1000,
            'help': 'UTXO and history output limit',
        }, ['items'], {
            'nargs': '+',
            'type': str,
            'help': 'hex scripts, or addresses, to query',
        },
    ),
    'reorg': (
        'simulate a chain reorganization',
        [], {
            'type': int,
            'dest': 'count',
            'default': 3,
            'help': 'number of blocks to back up'
        },
    ),
    'debug_memusage_list_all_objects': (
        'Print a table of types of most common types in memory',
        ['--limit'], {
            'type': int,
            'default': 50,
            'help': 'max number of types to return',
        },
    ),
    'debug_memusage_get_random_backref_chain': (
        "Return a dotfile as text containing the backref chain "
        "for a randomly selected object of type objtype",
        [], {
            'type': str,
            'dest': 'objtype',
            'help': 'e.g. "_asyncio.Task"',
        },
    ),
}


def main():
    '''Send the RPC command to the server and print the result.'''
    main_parser = argparse.ArgumentParser(
        'electrumx_rpc',
        description='Send electrumx an RPC command'
    )
    main_parser.add_argument('-p', '--port', metavar='port_num', type=int,
                             help='RPC port number')
    main_parser.add_argument('--timeout', type=int, default=30,
                             help='timeout for command in seconds')

    subparsers = main_parser.add_subparsers(help='sub-command help',
                                            dest='command')

    for command, help in simple_commands.items():
        parser = subparsers.add_parser(command, help=help)

    for command, help in session_commands.items():
        parser = subparsers.add_parser(command, help=help)
        parser.add_argument('session_ids', nargs='+', type=str,
                            help='list of session ids')

    for command, data in other_commands.items():
        parser_help, *arguments = data
        parser = subparsers.add_parser(command, help=parser_help)
        for n in range(0, len(arguments), 2):
            args, kwargs = arguments[n: n+2]
            parser.add_argument(*args, **kwargs)

    args = main_parser.parse_args()
    args = vars(args)
    port = args.pop('port')
    if port is None:
        port = int(environ.get('RPC_PORT', 8000))
    method = args.pop('command')
    timeout = args.pop('timeout')

    # aiorpcX makes this so easy...
    async def send_request():
        try:
            async with timeout_after(timeout):
                async with connect_rs('localhost', port) as session:
                    session.transport._framer.max_size = 0
                    session.sent_request_timeout = timeout
                    result = await session.send_request(method, args)
                    if method in ('query', ):
                        for line in result:
                            print(line)
                    elif method in (
                            'debug_memusage_list_all_objects',
                            'debug_memusage_get_random_backref_chain',
                    ):
                        for line in result.split('\n'):
                            print(line)
                    elif method in ('groups', 'peers', 'sessions'):
                        lines_func = getattr(text, f'{method}_lines')
                        for line in lines_func(result):
                            print(line)
                    else:
                        print(json.dumps(result, indent=4, sort_keys=True))
            return 0
        except OSError:
            print('cannot connect - is ElectrumX catching up, not running, or '
                  f'is {port} the wrong RPC port?')
            return 1
        except Exception as e:
            print(f'error making request: {e}')
            return 1

    code = asyncio.run(send_request())
    sys.exit(code)


if __name__ == '__main__':
    main()
