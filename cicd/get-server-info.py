#!/usr/bin/env python

'''
Retrieve CAS server information from CAS log

The CAS server command is expected to have a `-display` option with a unique
key for the invoked server.  This is used to retrieve the PID of the server
process.  The basename of the CAS log file must match the value in the
`-display` option.

'''

import argparse
import os
import re
import subprocess
import sys
import time


def print_err(*args, **kwargs):
    ''' Print a message to stderr '''
    sys.stderr.write(*args, **kwargs)
    sys.stderr.write('\n')


def main(args):
    '''
    Main routine

    Parameters
    ----------
    args : argparse arguments
        Arguments to the command-line

    '''
    if not os.path.isfile(args.log_file):
        print_err(f'ERROR: File not found: {args.log_file}')
        sys.exit(1)

    iters = 0
    for _ in range(args.retries):
        iters += 1
        time.sleep(args.interval)
        if iters > args.retries:
            print_err('ERROR: Could not locate CAS log file.')
            sys.exit(1)

        with open(args.log_file, 'r') as logf:
            txt = logf.read()
            if m := re.search(
                r'===\s+.+?(\S+):(\d+)\s+.+?\s+.+?:(\d+)\s+===', txt
            ):
                hostname = m[1]
                binary_port = m[2]
                http_port = m[3]

                sys.stdout.write(f'CASHOST={hostname} ')
                sys.stdout.write(f'CAS_HOST={hostname} ')
                sys.stdout.write(f'CAS_BINARY_PORT={binary_port} ')
                sys.stdout.write(f'CAS_HTTP_PORT={http_port} ')
                sys.stdout.write(f'CAS_BINARY_URL=cas://{hostname}:{binary_port} ')
                sys.stdout.write(f'CAS_HTTP_URL=http://{hostname}:{http_port} ')

                if 'CASPROTOCOL' in os.environ or 'CAS_PROTOCOL' in os.environ:
                    protocol = os.environ.get('CASPROTOCOL',
                                              os.environ.get('CAS_PROTOCOL', 'http'))
                    if protocol == 'cas':
                        sys.stdout.write('CASPROTOCOL=cas ')
                        sys.stdout.write('CAS_PROTOCOL=cas ')
                        sys.stdout.write(f'CASPORT={binary_port} ')
                        sys.stdout.write(f'CAS_PORT={binary_port} ')
                        sys.stdout.write(f'CASURL=cas://{hostname}:{binary_port} ')
                        sys.stdout.write(f'CAS_URL=cas://{hostname}:{binary_port} ')
                    else:
                        sys.stdout.write(f'CASPROTOCOL={protocol} ')
                        sys.stdout.write(f'CAS_PROTOCOL={protocol} ')
                        sys.stdout.write(f'CASPORT={http_port} ')
                        sys.stdout.write(f'CAS_PORT={http_port} ')
                        sys.stdout.write(f'CASURL={protocol}://{hostname}:{http_port} ')
                        sys.stdout.write(f'CAS_URL={protocol}://{hostname}:{http_port} ')

                elif 'REQUIRES_TK' in os.environ:
                    if os.environ.get('REQUIRES_TK', '') == 'true':
                        sys.stdout.write('CASPROTOCOL=cas ')
                        sys.stdout.write('CAS_PROTOCOL=cas ')
                        sys.stdout.write(f'CASPORT={binary_port} ')
                        sys.stdout.write(f'CAS_PORT={binary_port} ')
                        sys.stdout.write(f'CASURL=cas://{hostname}:{binary_port} ')
                        sys.stdout.write(f'CAS_URL=cas://{hostname}:{binary_port} ')
                    else:
                        sys.stdout.write('CASPROTOCOL=http ')
                        sys.stdout.write('CAS_PROTOCOL=http ')
                        sys.stdout.write(f'CASPORT={http_port} ')
                        sys.stdout.write(f'CAS_PORT={http_port} ')
                        sys.stdout.write(f'CASURL=http://{hostname}:{http_port} ')
                        sys.stdout.write(f'CAS_URL=http://{hostname}:{http_port} ')

                # Get CAS server pid
                cmd = f"ssh -x -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {hostname} ps ax | grep {'.'.join(args.log_file.split('.')[:-1])} | grep -v grep | head -1"

                pid = subprocess.check_output(cmd, shell=True) \
                                .decode('utf-8').strip().split(' ', 1)[0]
                sys.stdout.write(f'CAS_PID={pid} ')

                # Write pid file
                if args.pid_file:
                    with open(args.pid_file, 'w') as pid_file_out:
                        pid_file_out.write(pid)

                break


if __name__ == '__main__':

    opts = argparse.ArgumentParser(description=__doc__.strip(),
                                   formatter_class=argparse.RawTextHelpFormatter)

    opts.add_argument('log_file', type=str, metavar='log-file',
                      help='path to CAS server log')

    opts.add_argument('--login-name', '-l', type=str, metavar='name',
                      help='login name for ssh when acquiring CAS pid')
    opts.add_argument('--pid-file', '-p', type=str, metavar='filename',
                      help='file to write CAS pid to')
    opts.add_argument('--retries', '-r', default=5, type=int, metavar='#',
                      help='number of retries in attempting to locate the log file')
    opts.add_argument('--interval', '-i', default=3, type=int, metavar='#',
                      help='number of seconds between each retry')

    args = opts.parse_args()

    main(args)
