#!/usr/bin/python

'''

@author: Christian Cwienk
'''


import sys
import os
from os.path import dirname, realpath, join,abspath, exists
from argparse import ArgumentParser

from git import Repo

def cliparser():
    p = ArgumentParser()
    p.add_argument('--project')
    p.add_argument('--refname')
    p.add_argument('--uploader')
    p.add_argument('--oldrev')
    p.add_argument('--newrev')
    return p

def repodir(project):
    #todo: use explicit configuration instead of relying on relative path
    owndir = dirname(abspath(__file__))
    return join(owndir, '..', 'git', project+'.git')

def reflogfile(repodir,ref):
    return join(repodir,'logs', ref)

def reflogref(ref):
    #cut off 'refs/heads'
    return 'refs/reflogs'+ref[10:]

def init_or_update_log(repo, repo_dir, ref, reflog_file):
    refpath=realpath(join(repo_dir, reflogref(ref), '..'))
    if not exists(refpath):
      os.makedirs(refpath)
    file_name = 'reflog'
    hash = repo.git.hash_object('-w', reflog_file)
    repo.git.update_index('--add', '--cacheinfo', '10644', hash, file_name)
    hash = repo.git.write_tree()
    hash = repo.git.commit_tree(hash)
    #replace old commit for now
    #todo: check for consistency against previous content
    #      and do a successor commit in this case
    with open(join(repo_dir,reflogref(ref)),'w') as f:
        f.write(hash)

def main(argv=sys.argv[1:]):
    p = cliparser()
    parsed_args = p.parse_args(argv)
    refname = parsed_args.refname
    if not refname.startswith('refs/heads/'): exit(0) #only process refs/heads
    repo_dir=repodir(parsed_args.project)
    repo = Repo(repo_dir)
    reflog_file=reflogfile(repo_dir,refname)
    init_or_update_log(repo, repo_dir, refname, reflog_file)


if __name__ == "__main__":
    main(sys.argv[1:])
