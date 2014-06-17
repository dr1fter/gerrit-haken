#!/usr/bin/env python

'''
gerrit 'ref-update' hook that persists the reflogs for any ref located
below 'refs/heads'. Persisted reflogs are stored in a commit which is
referenced by a ref-specific ref: refs/reflogs/<ref> with <ref> being 
the <ref> part of the respective 'refs/heads/<ref>'.

for the event that previous head-updates were lost or the local reflog was
altered, a heuristical sanity check is in place. If inconsistencies are
detected, the last stored state of the reflog is kept and the new local
reflog is stored as a child commit (thus becoming the new head of 
refs/reflogs/<ref>)

@author: Christian Cwienk
'''


import sys
import os
from subprocess import Popen,PIPE
from os.path import dirname, realpath, join,abspath, exists
from argparse import ArgumentParser

from git import Repo

REFLOG='reflog'
REFS_REFLOGS='refs/reflogs'

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
    return REFS_REFLOGS+ref[10:]

def reflogblobsha(repo,ref):
    blobline = filter(lambda l:l.endswith(REFLOG),repo.git.cat_file('-p',reflogref(ref)+'^{tree}').split('\n'))
    assert len(blobline) == 1, 'there must only be one file in ref/reflogs/<ref>/ that ends with "reflog"'
    blobsha = blobline[0].replace('\t',' ').split(' ')[2].strip()
    return blobsha
    
def tail(repo, blobsha,lines_count=2):
    gitp = Popen(['git','cat-file','-p',blobsha],cwd=repo.git_dir,stdout=PIPE)
    tailp= Popen(['tail', '-'+str(lines_count)],stdin=gitp.stdout, stdout=PIPE)
    stdout,_=tailp.communicate()
    return stdout

def checkinsanity(repo, reflog_ref, reflogfile):
    newtail,_= Popen(['tail', '-2', reflogfile],stdout=PIPE).communicate()
    newtail=newtail.split('\n')
    oldtail= tail(repo, reflogblobsha(repo,reflog_ref)).split('\n')
    if len(oldtail) < 1: return False # nothing in the log so far - can't sanity-check
    if len(newtail) < 2: return True# old log had at least one entry - new log must not be shorter
    return oldtail[1]!=newtail[0] 

def init_or_update_log(repo, repo_dir, ref, reflog_file):
    reflog_ref = reflogref(ref)
    refpath=realpath(join(repo_dir, reflog_ref, '..'))
    initial=False
    if not exists(refpath):
      os.makedirs(refpath)
      initial=True
    file_name = REFLOG
    if not initial: insane=checkinsanity(repo, ref, reflog_file)
    if insane: p_rev=repo.git.rev_parse(reflog_ref)
    hash = repo.git.hash_object('-w', reflog_file)
    repo.git.update_index('--add', '--cacheinfo', '10644', hash, file_name)
    hash = repo.git.write_tree()
    arglist = [hash]
    if not initial and not insane:
        #determine parent commit (if any)
        parent=repo.git.rev_list('--parents','-n1',reflog_ref).strip().split(' ')
        if len(parent)>1: arglist.extend(['-p', parent[1]])
    if insane: arglist.extend(['-p',p_rev])
    hash = repo.git.commit_tree(arglist)
    #update head
    with open(join(repo_dir,reflog_ref),'w') as f:
        f.write(hash)
    #todo: log a warning somewhere?
    print 'log was ' + ('insane' if insane else 'sane')

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
