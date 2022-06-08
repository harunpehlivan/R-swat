#!/usr/bin/env python

'''
Utitily for moving a release candidate to a full release

When a Github release is first created, it is done as a draft release.
This is done so that the release can be tested and verified before going
public as an official release. This utility is used to promote a
draft release to a public release.

'''

import argparse
import datetime
import glob
import io
import os
import re
import requests
import shutil
import sys
import subprocess
import tarfile
import tempfile
from urllib.parse import quote
from urllib.request import urlopen, urlretrieve


GITHUB_TOKEN = os.environ['GITHUB_TOKEN']


def get_repo():
    ''' Retrieve the repo part of the git URL '''
    cmd = ['git', 'remote', 'get-url', 'origin']
    repo = subprocess.check_output(cmd).decode('utf-8').strip()
    repo = re.search(r'github.com[/:](.+?)\.git$', repo)[1]
    return repo


def create_release(tag_name, target_commitish, rc_release):
    '''
    Create new release on Github

    POST /repos/:owner/:repo/releases

    '''
    res = requests.post(
        f'https://api.github.com/repos/{get_repo()}/releases',
        headers=dict(
            Authorization=f'token {GITHUB_TOKEN}',
            Accept='application/vnd.github.v3+json',
        ),
        json=dict(
            tag_name=tag_name,
            target_commitish=target_commitish,
            name=re.sub(r'(v\d+\.\d+\.\d+)-rc', r'\1', rc_release['name']),
            body=re.sub(r'(v\d+\.\d+\.\d+)-rc', r'\1', rc_release['body']),
            draft=False,
            prerelease=False,
        ),
    )


    if res.status_code >= 400:
        raise RuntimeError(res.json())

    res = res.json()

    copy_assets(res['upload_url'].split('{')[0], rc_release['assets'])


def copy_assets(url, assets):
    ''' Copy assets from other release to the upload url '''
    for asset in assets:
        asset_url = asset['browser_download_url']
        print(f" > {asset['name']}")
        with urlopen(asset_url) as asset_file:
            requests.post(
                f"{url}?name={quote(asset['name'])}",
                headers={
                    'Authorization': f'token {GITHUB_TOKEN}',
                    'Accept': 'application/vnd.github.v3+json',
                    'Content-Type': 'application/octet-stream',
                },
                data=asset_file.read(),
            )


def git_tag(tag, sha=None):
    ''' Add a tag '''
    cmd = ['git', 'tag', tag]
    if sha:
        cmd.append(sha)
    subprocess.check_call(cmd)


def git_push(tag=None):
    ''' Push updates '''
    cmd = ['git', 'push']
    subprocess.check_call(cmd)
    if tag:
        cmd = ['git', 'push', 'origin', tag]
        subprocess.check_call(cmd)


def git_fetch():
    ''' Make sure we have all commits and tags '''
    cmd = ['git', 'fetch', '--tags']
    subprocess.check_call(cmd)


def delete_release(tag_name):
    ''' Remove local and remote tags for the given release '''
    # Delete release
    res = requests.get(
        f'https://api.github.com/repos/{get_repo()}/releases/tags/{tag_name}',
        headers=dict(
            Authorization=f'token {GITHUB_TOKEN}',
            Accept='application/vnd.github.v3+json',
        ),
    )


    if res.status_code < 400:
        release_url = res.json()['url']
        res = requests.delete(
            release_url,
            headers=dict(
                Authorization=f'token {GITHUB_TOKEN}',
                Accept='application/vnd.github.v3+json',
            ),
        )


    # Delete tags
    del_tags = [tag_name, tag_name.replace('-rc', '-snapshot')]
    cmd = ['git', 'show-ref', '--tags']
    for line in subprocess.check_output(cmd).decode('utf-8').strip().split('\n'):
        sha, tag = re.split(r'\s+', line.strip())
        tag = tag.split('/')[-1]
        if tag in del_tags:
            cmd = ['git', 'tag', '-d', tag]
            subprocess.check_call(cmd)
            cmd = ['git', 'push', 'origin', f':refs/tags/{tag}']
            subprocess.check_call(cmd)
            break


def checkout_main(tag=None):
    ''' Make sure we're on the main branch '''
    cmd = ['git', 'checkout', 'main']
    subprocess.check_call(cmd)


def get_release(tag_name):
    ''' Retrieve the upload URL for the given tag '''
    res = requests.get(
        f'https://api.github.com/repos/{get_repo()}/releases/tags/{tag_name}',
        headers=dict(
            Authorization=f'token {GITHUB_TOKEN}',
            Accept='application/vnd.github.v3+json',
        ),
    )


    if res.status_code < 400:
        return res.json()

    raise RuntimeError(f'Could not locate tag name: {tag_name}')


def get_release_sha(tag_name):
    ''' Get the sha of the tag '''
    cmd = ['git', 'rev-list', '-n', '1', tag_name]
    return subprocess.check_output(cmd).decode('utf-8').strip()


def tag_type(value):
    ''' Check version syntax '''
    if re.match(r'^v\d+\.\d+\.\d+-rc$', value):
        return value
    raise argparse.ArgumentTypeError(value)


def main(args):
    ''' Main routine '''
    # Make sure local repo is up-to-date
    git_fetch()
    checkout_main()

    release_tag = args.tag.replace('-rc', '')
    release_sha = get_release_sha(args.tag)

    # Retrieve rc release info
    rc_release = get_release(args.tag)

    # Push release
    git_tag(release_tag, sha=release_sha)
    git_push(tag=release_tag)
    create_release(release_tag, release_sha, rc_release)

    # Delete rc release and snapshots
    delete_release(args.tag)
    delete_release(args.tag.replace('-rc', '-snapshot'))

    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.strip(),
                                     formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('tag', type=tag_type, metavar='tag',
                        help='tag of the release to promote')

    args = parser.parse_args()

    try:
        sys.exit(main(args))
    except KeyboardInterrupt:
        sys.exit(1)
