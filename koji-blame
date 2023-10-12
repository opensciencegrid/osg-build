#!/usr/bin/env python3
import re
import sys
import datetime
import time
import argparse

from osgbuild import utils

try:
    strptime = datetime.datetime.strptime
except AttributeError:
    def strptime(date_string, format):
        return datetime.datetime(*(time.strptime(date_string, format)[0:6]))

class Error(Exception):
    pass

_all_tags = []
def get_all_tags():
    global _all_tags
    if not _all_tags:
        # TODO EC
        _all_tags = utils.sbacktick(["osg-koji", "list-tags"])[0].split("\n")
    return _all_tags

def is_tag(maybe_tag):
    return maybe_tag in get_all_tags()

def is_build(maybe_build):
    out, ret = utils.sbacktick(["osg-koji", "buildinfo", maybe_build], err2out=True)
    if maybe_build not in out:
        raise Error("koji buildinfo returned unexpected result. Return: %d Output: %s" % (ret, out))
    return "No such build" not in out

def is_package(maybe_package):
    # Returns 1 if package not found
    out, ret = utils.sbacktick(["osg-koji", "list-pkgs", "--package", maybe_package], err2out=True)
    if maybe_package not in out or (not 0 <= ret <= 1):
        raise Error("koji list-pkgs returned unexpected result. Return: %d Output: %s" % (ret, out))
    return "No such entry" not in out

# TODO: koji list-history can take --before and --after arguments... try using those instead of re-implementing them
def run_list_history(item):
    cmd = ["osg-koji", "list-history"]
    if is_package(item):
        cmd += ["--package", item]
    elif is_build(item):
        cmd += ["--build",   item]
    elif is_tag(item):
        cmd += ["--tag",     item]
    else:
        raise Error("%s is not a package, build or tag" % item)
    return utils.sbacktick(cmd)[0]

def parse_history(lh_output, since=None, until=None):
    # This is what a line of output from koji list-history looks like:
    # Fri May 30 11:45:59 2014 osg-configure-1.0.55-2.osg31.el6 tagged into osg-3.1-el6-development by Matyas Selmeci [still active]
    pattern = re.compile(r"(?P<date>.+?20\d\d) (?P<build>\S+) (?P<action>tagged into|untagged from) (?P<tag>\S+) by (?P<user>[^\[]+) \[still active\]")
    parsed = []
    for line in lh_output.split("\n"):
        m = pattern.match(line)
        if m:
            user = m.group('user').rstrip()
            user = re.sub(r" A?\d+$", "", user)
            date = strptime(m.group('date'), "%a %b %d %H:%M:%S %Y")
            if (since is None or since < date) and (until is None or date < until):
                parsed.append({'date' : date.strftime("%Y-%m-%d"),
                               'user' : user,
                               'tag'  : m.group('tag'),
                               'build': m.group('build')})
    return parsed

def detect_mode(item):
    if is_package(item):
        return 'package'
    if is_build(item):
        return 'build'
    if is_tag(item):
        return 'tag'

def format_history_item(history_item, mode):
    line = "%s  %-18s  " % (history_item['date'], history_item['user'])
    if mode == 'package':
        line += "%-30s  %s" % (history_item['tag'], history_item['build'])
    if mode == 'build':
        line += "%s" % (history_item['tag'])
    if mode == 'tag':
        line += "%s" % (history_item['build'])
    return line


def parse_cli(args):
    """This function parses all the arguments, options, and validates them.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--since', action=DateAction, dest='since',
                        help="List packages since YYYY-MM-DD")
    parser.add_argument('-u', '--until', action=DateAction, dest='until',
                        help="List packages until YYYY-MM-DD")
    parser.add_argument('koji_object', help='Koji package, tag, or build')

    return parser.parse_args(args)


class DateAction(argparse.Action):
    """Action for validating date options
    """
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError("Date options only accept a single argument (format: YYYY-MM-DD)")
        super(DateAction, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        try:
            setattr(namespace, self.dest, strptime(values, "%Y-%m-%d"))
        except ValueError as e:
            parser.error(str(e))


def main(argv):
    args = parse_cli(argv[1:])

    if not utils.which('osg-koji'):
        raise Error("osg-koji not found in $PATH")
    mode = detect_mode(args.koji_object)
    lh_output = run_list_history(args.koji_object)
    print("\n".join(format_history_item(item, mode) for item in parse_history(lh_output,
                                                                              since=args.since,
                                                                              until=args.until)))


def entrypoint():
    """CLI entrypoint for koji-blame"""
    try:
        main(sys.argv)
    except Error as err:
        sys.stderr.write(str(err))
        return 1


if __name__ == "__main__":
    sys.exit(entrypoint())
