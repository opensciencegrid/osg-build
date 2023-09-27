#!/usr/bin/env python3

import glob
import logging
import re
from optparse import OptionParser
import os
import shutil
import sys
import traceback

from osgbuild import fetch_sources
from osgbuild import utils

# Constants:
VDT_WWW = "/p/vdt/public/html"
DEFAULT_UPSTREAM_ROOT = os.path.join(VDT_WWW, "upstream")
DEFAULT_LOG_LEVEL = logging.INFO


EXTRA_ACTION_DIFF_SPEC = 'diff_spec'
EXTRA_ACTION_EXTRACT_SPEC = 'extract_spec'
EXTRA_ACTION_DIFF3_SPEC = 'diff3_spec'
EXTRA_ACTION_UPDATE = 'update'

PROVIDER_PATTERNS = [
    (r'centos\.org'                    , 'centos') ,
    (r'emisoft\.web\.cern\.ch'         , 'emi')    ,
    (r'fedoraproject\.org/pub/epel/'   , 'epel')   ,
    (r'fedoraproject\.org/pub/fedora/' , 'fedora') ,
    (r'globus\.org'                    , 'globus') ,
    (r'koji\.fedoraproject\.org/'      , 'fedora') ,
    (r'kojipkgs\.fedoraproject\.org/'  , 'fedora') ,
    (r'xrootd\.web\.cern\.ch/'         , 'xrootd') ]




class Error(Exception):
    """Base class for expected exceptions. Caught in main(); may include a
    traceback but will only print it if debugging is enabled.

    """
    def __init__(self, msg, tb=None):
        self.msg = msg
        if tb is None:
            self.traceback = traceback.format_exc()

    def __repr__(self):
        return repr((self.msg, self.traceback))

    def __str__(self):
        return str(self.msg)


class UsageError(Error):
    def __init__(self, msg):
        Error.__init__(self, "Usage error: " + msg + "\n")


def verify_rpm(srpm):
    """Verify that srpm is indeed an RPM. Raise Error if not."""
    cmd = ["rpm", "-qp", "--nomanifest", srpm]
    err = utils.unchecked_call(cmd)
    if err:
        raise Error("rpm: %s does not look like an RPM" % srpm)

def srpm_nv(srpm):
    """Return the NV (Name, Version) from an SRPM."""
    output, ret = utils.sbacktick(["rpm", "-qp", "--qf", "%{name} %{version}", srpm])
    if ret == 0:
        try:
            name, version = output.rstrip().split(" ")
            return name, version
        except ValueError:  # not enough/too many items
            pass
    raise Error("Unable to extract name and version from SRPM %s: %s" % (srpm, output))

def make_svn_tree(srpm, url, dirname=None, extra_action=None, provider=None, sha1sum=None):
    """Create an svn tree for the srpm and populate it as follows:
    $name/osg/*.spec        - the spec file as extracted from the srpm
                              (if extract_spec is True)
    $name/upstream/*.source - the location of the srpm under the upstream cache
                              as well as a comment describing where it's from

    """
    name, version = srpm_nv(srpm)
    if not dirname:
        dirname = name
    abs_srpm = os.path.abspath(srpm)

    package_dir = os.path.abspath(os.getcwd())
    if os.path.basename(package_dir) != dirname:
        package_dir = os.path.join(package_dir, dirname)

    if not os.path.exists(package_dir):
        utils.checked_call(["svn", "mkdir", package_dir])

    osg_dir = os.path.join(package_dir, "osg")
    if extra_action == EXTRA_ACTION_DIFF_SPEC:
        diff_spec(abs_srpm, osg_dir, want_diff3=False)
    elif extra_action == EXTRA_ACTION_EXTRACT_SPEC:
        extract_spec(abs_srpm, osg_dir)
    elif extra_action == EXTRA_ACTION_DIFF3_SPEC:
        if os.path.isdir(osg_dir):
            extract_orig_spec(osg_dir)
        diff_spec(abs_srpm, osg_dir, want_diff3=True)
    elif extra_action == EXTRA_ACTION_UPDATE:
        if os.path.isdir(osg_dir):
            logging.info("osg dir found -- doing 3-way diff")
            extract_orig_spec(osg_dir)
            diff_spec(abs_srpm, osg_dir, want_diff3=True)
        else:
            logging.info("osg dir not found -- updating .source file only")

    upstream_dir = os.path.join(package_dir, "upstream")

    if not os.path.exists(upstream_dir):
        utils.checked_call(["svn", "mkdir", upstream_dir])

    cached_filename = os.path.join(name, version, os.path.basename(srpm))

    make_source_file(url, cached_filename, upstream_dir, provider, sha1sum)

    if len(glob.glob(os.path.join(upstream_dir, "*.source"))) > 1:
        logging.info("More than one .source file found in upstream dir.")
        logging.info("Examine them to make sure there aren't duplicates.")


def make_source_file(url, cached_filename, upstream_dir, provider=None, sha1sum=None):
    """Create an upstream/*.source file with the appropriate name based
    on either `provider` or `url` if the former is not given.  Also add
    the new file to SVN.
    """
    if provider is None:
        for provpat, provname in PROVIDER_PATTERNS:
            if re.search(provpat, url):
                provider = provname
                break
        else:
            provider = 'developer'

    source_filename = os.path.join(upstream_dir, provider+".srpm.source")
    if sha1sum:
        srcspec = "{cached_filename} sha1sum={sha1sum}".format(**locals())
    else:
        srcspec = cached_filename
    source_contents = "{srcspec}\n# Downloaded from {url}\n".format(**locals())

    if os.path.exists(source_filename):
        logging.info("%s already exists. Backing it up as %s.old", source_filename, source_filename)
        shutil.move(source_filename, source_filename + ".old")
        utils.unslurp(source_filename, source_contents)
    else:
        utils.unslurp(source_filename, source_contents)
        svn_safe_add(source_filename)


def is_untracked_path(path):
    """Return True if the given path is untracked in SVN.
    Note: ignored files return False.
    """
    output, ret = utils.sbacktick(["svn", "status", path])

    return output.startswith('?')


def svn_safe_add(path):
    """Add path to SVN if it's not already in there. Return True on success."""
    if is_untracked_path(path):
        ret = utils.unchecked_call(["svn", "add", path])
        return ret == 0


def get_spec_name_in_srpm(srpm):
    """Return the name of the spec file present in an SRPM.  Assumes
    there is exactly one spec file in the SRPM -- if there is more than
    one spec file, returns the name of the first one ``cpio'' prints.
    """
    out, ret = utils.sbacktick("rpm2cpio %s | cpio -t '*.spec' 2> /dev/null" % utils.shell_quote(srpm), shell=True)
    if ret != 0:
        raise Error("Unable to get list of spec files from %s" % srpm)
    try:
        spec_name = [_f for _f in [x.strip() for x in out.split("\n")] if _f][0]
    except IndexError:
        spec_name = None

    if not spec_name:
        raise Error("No spec file inside %s" % srpm)

    return spec_name


def extract_from_rpm(rpm, file_or_pattern=None):
    """Extract a specific file or glob from an rpm."""
    command = "rpm2cpio " + utils.shell_quote(rpm) + " | cpio -ivd"
    if file_or_pattern:
        command += " " + utils.shell_quote(file_or_pattern)
    return utils.checked_call(command, shell=True)


def diff2(old_file, new_file, dest_file=None):
    """Do a 2-way diff, between `old_file` and `new_file`, where the
    differences are shown with markers like what SVN makes for a file
    with merge conflicts, e.g.:

    '''
    <<<<<<< old_file
    old stuff
    =======
    new stuff
    >>>>>>> new_file
    '''

    Write the result to `dest_file` if it is specified.
    Return the text of the diff on success, None on failure.
    """

    diff, ret = utils.sbacktick(["diff", """\
--changed-group-format=<<<<<<< %(old_file)s
%%<=======
%%>>>>>>>> %(new_file)s
""" % locals(), old_file, new_file])
    if not (ret == 0 or ret == 1):
        logging.warning("Error diffing %s %s: diff returned %d",
                        old_file, new_file, ret)
        return

    if dest_file:
        utils.unslurp(dest_file, diff)
        logging.info("Difference between %s and %s written to %s",
                     old_file, new_file, dest_file)

    return diff


def diff3(old_file, orig_file, new_file, dest_file=None):
    """Do a 3-way diff between `old_file`, `orig_file`, and `new_file`,
    where the differences are shown with markers like what SVN makes
    for a file with merge conflicts, e.g.:

    '''
    <<<<<<< old_file
    old stuff
    ||||||| orig_file
    orig stuff
    =======
    new stuff
    >>>>>>> new_file
    '''

    Write the result to `dest_file` if it is specified.
    Return the text of the diff on success, None on failure.
    """

    diff, ret = utils.sbacktick(["diff3", "-m", old_file, orig_file, new_file])
    if not (ret == 0 or ret == 1):
        logging.warning("Error diffing %s %s %s: diff3 returned %d",
                        old_file, orig_file, new_file, ret)
        return

    if dest_file:
        utils.unslurp(dest_file, diff)
        logging.info("Difference between %s, %s, and %s written to %s",
                     old_file, orig_file, new_file, dest_file)

    return diff


def diff_spec(srpm, osg_dir, want_diff3=False):
    """Do a 2- or 3-way diff between spec files found in the osg/
     directory, and the new upstream SRPM. If a 3-way diff is requested,
     also look at the spec file from the previous upstream SRPM. The
     osg/ directory must exist.

    The files that will be created or changed are:
    - $spec.old  : spec file from the osg/ dir before import
    - $spec.new  : spec file from the new upstream SRPM
    - $spec.orig : spec file from the old upstream SRPM (3-way only)
    - $spec      : combined spec file with differences separated by markers

    """
    if not os.path.isdir(osg_dir) or not glob.glob(os.path.join(osg_dir, '*')):
        logging.error("No osg/ dir found or no spec files in osg/ dir -- nothing to diff.")
        logging.error("To extract the spec file, run with -e instead.")
        sys.exit(1)

    utils.pushd(osg_dir)
    try:
        srpm = os.path.abspath(srpm)

        spec_name = get_spec_name_in_srpm(srpm)
        spec_name_old = spec_name + ".old"
        spec_name_new = spec_name + ".new"

        if not os.path.exists(spec_name):
            logging.info("No old spec file matching %s - the spec file might have been renamed.",
                         spec_name)
            logging.info("Extracting new upstream spec file as %s", spec_name)
            extract_from_rpm(srpm, spec_name)
            return

        logging.info("OSG spec file found matching %s, saving to %s",
                     spec_name, spec_name_old)
        shutil.move(spec_name, spec_name_old)

        logging.info("Extracting new upstream spec file as %s", spec_name_new)
        extract_from_rpm(srpm, spec_name)
        shutil.move(spec_name, spec_name_new)

        if want_diff3:
            spec_name_orig = spec_name + ".orig"
            if os.path.exists(spec_name_orig):
                # Use `diff3 -m` to takes the changes that turn spec_name_orig into
                # spec_name_new, and applies these changes to spec_name_new.
                # Put the results into spec_name.

                diff3(spec_name_old, spec_name_orig, spec_name_new, spec_name)
            else:
                # This can happen if the package before import was an upstream
                # tarball with osg-provided spec file, as opposed to an
                # upstream SRPM with an osg-modified spec file.

                logging.info("No original upstream spec file matching %s - doing a two-way diff instead.", spec_name)
                diff2(spec_name_old, spec_name_new, spec_name)
        else:
            diff2(spec_name_old, spec_name_new, spec_name)

    finally:
        utils.popd()


def extract_spec(srpm, osg_dir):
    """Extract the spec file from the SRPM, put it into an osg/ dir,
    and add both the osg/ dir and the spec file to SVN, if necessary.
    An existing spec file will be moved out of the way, with a .old
    extension, if necessary.
    """
    if not os.path.exists(osg_dir):
        os.mkdir(osg_dir)
        svn_safe_add(osg_dir)

    utils.pushd(osg_dir)
    try:
        srpm = os.path.abspath(srpm)

        spec_name = get_spec_name_in_srpm(srpm)

        if os.path.exists(spec_name):
            spec_name_old = spec_name + ".old"
            logging.info("OSG spec file found matching %s, saving to %s",
                         spec_name, spec_name_old)
            shutil.move(spec_name, spec_name_old)

        logging.info("Extracting new upstream spec file as %s", spec_name)
        extract_from_rpm(srpm, spec_name)
        svn_safe_add(spec_name)
    finally:
        utils.popd()


def extract_orig_spec(osg_dir):
    """Save a copy of the original upstream spec file from before the
    import into the osg_dir
    """
    utils.pushd(osg_dir)
    try:
        utils.checked_call(['osg-build', 'prebuild', '..'])
        spec_paths = list(glob.glob("../_upstream_srpm_contents/*.spec"))
        for spec_path in spec_paths:
            spec_name_orig = os.path.basename(spec_path) + '.orig'
            logging.info("Saving original upstream spec file as %s",
                         spec_name_orig)
            shutil.copy(spec_path, spec_name_orig)
    finally:
        utils.popd()


def move_to_cache(srpm, upstream_root):
    """Move the srpm to the upstream cache. Return the path to the file in the cache."""
    name, version = srpm_nv(srpm)
    base_srpm = os.path.basename(srpm)
    upstream_dir = os.path.join(upstream_root, name, version)
    utils.safe_makedirs(upstream_dir)
    dest_file = os.path.join(upstream_dir, base_srpm)
    if os.path.exists(dest_file):
        os.unlink(dest_file)
    shutil.move(srpm, dest_file)

    return dest_file


def get_sha1sum(file_path):
    """Return the SHA1 checksum of the file located at `file_path` as a string."""
    out, ret = utils.sbacktick(["sha1sum", file_path])
    if ret != 0:
        raise Error("Unable to get sha1sum of %s: exit %d when running sha1sum" % (file_path, ret))
    match = re.match(r"[a-f0-9]{40}", out)
    if not match:
        raise Error("Unable to get sha1sum of %s: unexpected output: %s" % (file_path, out))
    return match.group(0)


def main(argv=sys.argv):
    parser = OptionParser("""
    %prog [options] <upstream-url>

%prog should be called from an SVN checkout and given the URL of an upstream SRPM.
will create and populate the appropriate directories in SVN as well as
downloading and putting the SRPM into the upstream cache.
""")
    try:
        parser.set_defaults(extra_action=None)

        parser.add_option(
            "-d", "--diff-spec", "-2", action="store_const", dest='extra_action', const=EXTRA_ACTION_DIFF_SPEC,
            help="Perform a two-way diff between the new upstream spec file and the OSG spec file. "
            "The new upstream spec file will be written to SPEC.new, and the OSG spec file will be "
            "written to SPEC.old; the differences will be written to SPEC. You will have to edit "
            "SPEC to resolve the differences.")
        parser.add_option(
            "--dirname", default=None,
            help="The SVN directory name the imported files will be placed into; "
            "defaults to the name of the package but you might want to change it "
            "to add an '.el9' suffix for example."
        )
        parser.add_option(
            "-e", "--extract-spec", action="store_const", dest='extra_action', const=EXTRA_ACTION_EXTRACT_SPEC,
            help="Extract the spec file from the SRPM and put it into an osg/ subdirectory.")
        parser.add_option(
            "--loglevel",
            help="The level of logging the script should do. "
            "Valid values are DEBUG,INFO,WARNING,ERROR,CRITICAL")
        parser.add_option(
            "-o", "--output",
            help="The filename the upstream-url should be saved as.")
        parser.add_option(
            "-p", "--provider",
            help="Who provided the SRPM being imported. For example, 'epel'. "
            "This is used to name the .source file in the 'upstream' directory. "
            "If unspecified, guess based on the URL, and use 'developer' as the fallback.")
        parser.add_option(
            "-3", "--diff3-spec", action="store_const", dest='extra_action', const=EXTRA_ACTION_DIFF3_SPEC,
            help="Perform a three-way diff between the original upstream spec file, the OSG spec file, "
            "and the new upstream spec file. These spec files will be written to SPEC.orig, "
            "SPEC.old, and SPEC.new, respectively; a merged result will be written to SPEC."
            "You will have to edit SPEC to resolve merge conflicts.")
        parser.add_option(
            "-u", "--upstream", default=DEFAULT_UPSTREAM_ROOT,
            help="The base directory to put the upstream sources under. "
            "Default: %default")
        parser.add_option(
            "-U", "--update", action="store_const", dest='extra_action', const=EXTRA_ACTION_UPDATE,
            help="If there is an osg/ directory, do a 3-way diff like --diff3-spec.  Otherwise just update"
            " the .source file in the 'upstream' directory."
        )
        parser.add_option(
            "--nosha1sum", action="store_false", dest="want_sha1sum", default=True,
            help="Do not add a 'sha1sum' parameter to the .source file. "
                 ".source files with sha1sums need osg-build 1.14+ to use."
        )

        options, pos_args = parser.parse_args(argv[1:])

        if options.loglevel:
            try:
                loglevel = int(getattr(logging, options.loglevel.upper()))
            except (TypeError, AttributeError):
                raise UsageError("Invalid log level")
        else:
            loglevel = DEFAULT_LOG_LEVEL
        logging.basicConfig(format=" >> %(message)s", level=loglevel)

        try:
            upstream_url = pos_args[0]
        except IndexError:
            raise UsageError("Required argument <upstream-url> not provided")

        if utils.unchecked_call("svn info &>/dev/null", shell=True):
            raise Error("Must be called from an svn checkout!")

        if not re.match(r'(http|https|ftp):', upstream_url):
            raise UsageError("upstream-url is not a valid url")

        outfile = options.output or os.path.basename(upstream_url)
        sha1sum = fetch_sources.download_uri(upstream_url, outfile)
        if not options.want_sha1sum:
            sha1sum = None
        verify_rpm(outfile)
        srpm = move_to_cache(outfile, options.upstream)
        make_svn_tree(
            srpm,
            upstream_url,
            options.dirname,
            options.extra_action,
            options.provider,
            sha1sum
        )

    except UsageError as e:
        parser.print_help()
        print(str(e), file=sys.stderr)
        return 2
    except SystemExit as e:
        return e.code
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 3
    except Error as e:
        logging.critical(str(e))
        logging.debug(e.traceback)
    except Exception as e:
        logging.critical("Unhandled exception: %s", e)
        logging.critical(traceback.format_exc())
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))

