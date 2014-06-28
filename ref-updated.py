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
    p.add_argument('--submitter')
    p.add_argument('--oldrev')
    p.add_argument('--newrev')
    return p

def repodir():
    return os.environ['GIT_DIR']

def reflogfile(ref):
    if not ref.startswith('refs/heads'): ref='refs/heads/' + ref
    return join(repodir(),'logs', ref)

def reflogref(ref):
    #cut off 'refs/heads'
    return '/'.join([REFS_REFLOGS,branch(ref)])

def branch(ref):
    #cut off 'refs/heads'
    return ref[10:] if ref.startswith('refs/heads') else ref

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

def init_or_update_log(repo, ref, reflog_file):
    reflog_ref = reflogref(ref)
    refpath=realpath(join(repodir(), reflog_ref, '..'))
    initial=False
    if not exists(refpath):
      os.makedirs(refpath)
    if not exists(join(repodir(), reflog_ref)): initial=True
    file_name = REFLOG
    if not initial: insane=checkinsanity(repo, ref, reflog_file)
    else: insane=False
    if insane: p_rev=repo.git.rev_parse(reflog_ref)
    hash = repo.git.hash_object('-w', reflog_file)
    repo.git.update_index('--add', '--cacheinfo', '10644', hash, file_name)
    hash = repo.git.write_tree()
    arglist = [hash, '-m', 'persist reflog']
    if not initial and not insane:
        #determine parent commit (if any)
        parent=repo.git.rev_list('--parents','-n1',reflog_ref).strip().split(' ')
        if len(parent)>1: arglist.extend(['-p', parent[1]])
    if insane: arglist.extend(['-p',p_rev])
    hash = repo.git.commit_tree(arglist)
    #update head
    with open(join(repodir(),reflog_ref),'w') as f:
        f.write(hash)
    #todo: log a warning somewhere?
    print 'log was ' + ('insane' if insane else 'sane')

def main(argv=sys.argv[1:]):
    p = cliparser()
    parsed_args,_ = p.parse_known_args(argv)
    refname = parsed_args.refname
    #if not refname.startswith('refs/heads/'): exit(0) #only process refs/heads
    repo = Repo(repodir())
    reflog_file=reflogfile(refname)
    init_or_update_log(repo, refname, reflog_file)


if __name__ == "__main__":
    main(sys.argv[1:])
