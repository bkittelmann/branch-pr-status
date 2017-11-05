#!/usr/bin/env python

from __future__ import print_function
from __future__ import unicode_literals
import argparse
from builtins import input
from builtins import str as text
import getpass
import re
import sys

from dulwich import porcelain
from dulwich.repo import Repo
from github import Github, GithubException, BadCredentialsException
import keyring
from termcolor import colored


description = "Check the status of pull requests corresponding to local branches"


def prompt(text):
    sys.stderr.write(str(text))
    return input()


def get_repo_name(repo):
    config = repo.get_config()
    remote_origin = config.get(("remote", "origin"), "url")
    matches = re.match(r".*?github\.com[:/](.+?)\.git", remote_origin)
    return matches.group(1)


def get_branch_commits(repo, ignored_branches):
    branches = filter(lambda b: b not in ignored_branches, porcelain.branch_list(repo))
    branches_with_commits = {}
    for branch_name in branches:
        branch_ref = bytes("refs/heads/%s" % branch_name)
        commits = [entry.commit for entry in repo.get_walker(include=[repo[branch_ref].id], max_entries=1)]
        branches_with_commits[branch_name] = commits[0].id
    return branches_with_commits


def format_status(pull_request):
    status = ""
    if pull_request.merged:
        status = colored("merged", "green")
    elif pull_request.state == "closed":
        status =colored("closed", "yellow")
    elif pull_request.state == "open":
        status =colored("open", "red")
    return status


def print_pr_found(commit_id, last_ref_name, pull_request):
    status = format_status(pull_request)
    print("%s %s '%s', %s, %s" % (commit_id, last_ref_name, pull_request.title, status, pull_request.html_url))


def print_pr_found_minimal(commit_id, last_ref_name, pull_request, align_to = None):
    status = "merged" if pull_request.merged else pull_request.state
    output_format = "%%-%ss %%s" % align_to if align_to is not None else "%s %s"
    print(output_format % (last_ref_name, status))


def print_no_pr_found(commit_id, last_ref_name, align_to = None):
    output_format = "%%-%ss -" % align_to if align_to is not None else "%s -"
    print(output_format % last_ref_name)


def inspect_branches(github, args):
    repo = Repo(args.repository)

    repo_name = get_repo_name(repo)
    branches_with_latest_commits = get_branch_commits(repo, args.ignored_branches)

    align_to = None
    if args.align:
        longest_branch_name = sorted(branches_with_latest_commits.keys(), cmp = lambda a,b: len(b) - len(a))[0]
        align_to = len(longest_branch_name) + 1

    for branch, commit_id in sorted(branches_with_latest_commits.items()):
        query = "repo:%s %s" % (repo_name, commit_id)
        results = github.search_issues(query)
        if len(list(results)) > 0:
            issue = results[0]

            # see https://github.com/PyGithub/PyGithub/issues/572
            pull_request = issue.repository.get_pull(issue.number)
            print_pr_found_minimal(commit_id, branch, pull_request, align_to)
        else:
            print_no_pr_found(commit_id, branch)


def get_credentials():
    credentials = keyring.get_password("branch-pr-status", "github-api-credentials")
    if credentials:
        user_name, token = credentials.split(":")
        return user_name, token
    else:
        return None


def store_credentials(user_name, token):
    do_store = prompt("Login ok. Store credentials in keyring? [y/n]\n")
    if do_store.strip().lower() == "y":
        credentials = "%s:%s" % (user_name, token)
        keyring.set_password("branch-pr-status", "github-api-credentials", credentials)


def remove_credentials():
    do_remove = prompt("Login failed. Remove credentials from keyring? [y/n]\n")
    if do_remove.strip().lower() == "y":
        keyring.delete_password("branch-pr-status", "github-api-credentials")


def no_operation(*args):
    "Does nothing"


def login_failed():
    sys.stderr.write("Login to GitHub API failed\n")


def authenticate(user_name, token):
    "Throws exception when login fails"
    github = Github(user_name, token)
    user = github.get_user()
    user.login
    return github


def query_github(user_name, token, args, on_login_success=no_operation, on_login_failure=no_operation):
    try:
        github = authenticate(user_name, token)
        on_login_success(user_name, token)
        inspect_branches(github, args)
    except BadCredentialsException as ex:
        on_login_failure()
        sys.exit(1)


def run(args):
    if args.user and args.token:
            query_github(args.user, args.token, args, on_login_failure=login_failed)
    else:
        credentials = get_credentials()
        if credentials:
            user_name, token = credentials
            query_github(user_name, token, args, on_login_failure=remove_credentials)
        else:
            user_name = prompt("Enter GitHub user name: ")
            token = getpass.getpass(prompt="Enter personal access token: ")
            query_github(
                user_name,
                token,
                args,
                on_login_success=store_credentials,
                on_login_failure=login_failed
            )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=description, formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument("-u", "--user")
    parser.add_argument("-t", "--token")

    parser.add_argument("--align", action="store_true", default=False)
    parser.add_argument("--ignored-branches", nargs="*", default=["master", "develop"])
    parser.add_argument("repository")

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    else:
        try:
            run(parser.parse_args())
        except KeyboardInterrupt:
            pass
