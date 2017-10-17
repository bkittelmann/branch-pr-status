#!/usr/bin/env python

import argparse
import re
from subprocess import check_output
import sys

from github import Github
from termcolor import colored


description = "Check the status of pull requests originating from local branches"


def get_repo_name(args):
    repo_name_command = "cd %s && git config --get remote.origin.url" % args.repository
    out = check_output([repo_name_command], shell=True).strip()
    matches = re.match(r"git@github\.com:(.+?)\.git", out)
    return matches.group(1)


def format_status(pull_request):
    status = ""
    if pull_request.merged:
        status = colored("merged", "green")
    elif pull_request.state == "closed":
        status =colored("closed", "yellow")
    elif pull_request.state == "open":
        status =colored("open", "red")
    return status


def validate_args(args):
    if args.user == None or args.token == None:
        print "No --user and --token arguments set"
        return False
    return True


def print_pr_found(commit_id, last_ref_name, pull_request):
    status = format_status(pull_request)
    print "%s %s '%s', %s, %s" % (commit_id, last_ref_name, pull_request.title, status, pull_request.html_url)


def print_no_pr_found(commit_id, last_ref_name):
    print "%s %s" % (commit_id, last_ref_name)


def inspect_branches(args):
    repo_name = get_repo_name(args)

    branch_list_command = "cd %s && git branch -l | grep -v '* ' | grep -v 'master'| xargs -n 1 -I{} git log {} -n1 --oneline --pretty=format:'%%h*%%D\n'" % args.repository
    out = check_output([branch_list_command], shell=True)

    github = Github(args.user, args.token)

    for line in out.splitlines():
        commit_id, ref_names = line.split("*")
        ref_name_list = ref_names.split(", ")

        results = github.search_issues("repo:%s %s" % (repo_name, commit_id))
        if results.totalCount > 0:
            issue = results[0]

            # see https://github.com/PyGithub/PyGithub/issues/572
            pull_request = issue.repository.get_pull(issue.number)
            print_pr_found(commit_id, ref_name_list[-1], pull_request)
        else:
            print_no_pr_found(commit_id, ref_name_list[-1])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=description, formatter_class=argparse.RawTextHelpFormatter)

    # TODO: prompt user for credentials if not given as arguments
    parser.add_argument("-u", "--user")
    parser.add_argument("-t", "--token")

    parser.add_argument("repository")

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    else:
        args = parser.parse_args()
        if validate_args(args):
            inspect_branches(args)