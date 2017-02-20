"""Fetch sources from the upstream cache and combine them with sources from
the osg/ dir in the package.

"""

# pylint: disable=W0614
import fnmatch
import logging
import glob
import re
import os
import json
import tempfile
import subprocess
import shutil
import urllib2

from osgbuild.constants import *
from osgbuild.error import Error, GlobNotFoundError
from osgbuild import utils

log = logging.getLogger('osgbuild')
log.propagate = False

def process_json_url(line, destdir):
    """
    Process a JSON-serialized URL spec.  Should be of the format:
     {"type": "git", "url": "https://github.com/opensciencegrid/cvmfs-config-osg.git", "name": "cvmfs-config-osg", "tag": "0.1", "hash": "e2b54cd1b94c9e3eaee079490c9d85f193c52249"}
    'name' can be derived from the URL if the last component in the URL is of the form 'NAME.git'
    """
    json_contents = json.loads(line)
    tag_type = json_contents.get("type", "")
    if tag_type != "git":
        raise Error("Only 'git'-type URLs are understood in JSON: %s" % line)
    git_url = json_contents.get('url')
    if not git_url:
        raise Error("No git URL provided in JSON: %s" % line)
    name = json_contents.get("name")
    if not name:
        basename = os.path.split(git_url)[-1]
        if basename[-4:] == '.git':
            name = basename[:-4]
        else:
            raise Error("No package name specified in JSON: %s" % line)
    print "Checking out git repo for %s." % name
    tag = json_contents.get("tag")
    if not tag:
        raise Error("No package tag specified: %s" % line)
    dest_file = str("%s-%s.tar.gz" % (name, tag))
    full_dest_file = os.path.join(destdir, dest_file)
    prefix = str("%s-%s" % (name, tag))
    git_hash = json_contents.get("hash")
    if not git_hash:
        raise Error("git hash not provided.")
    checkout_dir = tempfile.mkdtemp(prefix=dest_file, dir=destdir)
    rc = subprocess.call(["git", "clone", str(git_url), checkout_dir])
    if rc:
        shutil.rmtree(checkout_dir)
        raise Error("`git clone %s %s` failed with exit code %d" % (git_url, checkout_dir, rc))
    orig_dir = os.getcwd()
    try:
        os.chdir(checkout_dir)
        try:
            output = subprocess.check_output(["git", "show-ref", str(tag)])
        except subprocess.CalledProcessError:
            raise Error("Repository %s does not contain a tag named %s." % (git_url, tag))
        sha1 = output.split()[0]
        if sha1 != git_hash:
            raise Error("Repository hash %s corresponding to tag %s does not match expected hash %s" % (sha1, tag, git_hash))
        rc = subprocess.call(["git", "archive", "--format=tgz", "--prefix=%s/" % prefix, str(git_hash), "--output=%s" % os.path.join(destdir, dest_file)])
        if rc:
            raise Error("Failed to create an archive of hash %s" % git_hash)
    finally:
        os.chdir(orig_dir)
        shutil.rmtree(checkout_dir)

    return full_dest_file

def process_dot_source(cache_prefix, sfilename, destdir):
    """Read a .source file, fetch any files mentioned in it from the
    cache.

    """
    utils.safe_makedirs(destdir)
    downloaded = []
    try:
        sfile = open(sfilename, 'r')
        for lineno, line in enumerate(sfile):
            line = line.strip()
            if line.startswith('#'):
                continue
            if line == '':
                continue
            basename = os.path.basename(line)
            if line.startswith('{'):
                filename = process_json_url(line, destdir)
                downloaded.append(filename)
                continue
            elif line.startswith('/'):
                uri = "file://" + line
                log.warning(
                    "An absolute path has been given in %s line %d. "
                    "It is recommended to use only paths relative to %s"
                    "in your source files.", sfilename, lineno+1,
                    cache_prefix)
            elif not re.match(r'/|\w+://', line): # relative path
                uri = os.path.join(cache_prefix, line)
            else:
                uri = line

            log.info('Retrieving ' + uri)
            try:
                handle = urllib2.urlopen(uri)
            except urllib2.URLError, err:
                raise Error("Unable to download %s\n%s" % (uri, str(err)))
            filename = os.path.join(destdir, basename)
            try:
                desthandle = open(filename, 'w')
                desthandle.write(handle.read())
            except EnvironmentError, err:
                raise Error("Unable to save downloaded file to %s\n%s" % (filename, str(err)))
            downloaded.append(filename)
    finally:
        sfile.close()

    return downloaded
# end of process_dot_source()


def full_extract(unpacked_dir, archives_downloaded, destdir):
    """Extract downloaded archives plus archives inside downloaded SRPMs"""
    archives_in_srpm = []
    if os.path.isdir(unpacked_dir):
        for fname in glob.glob(os.path.join(unpacked_dir, '*')):
            if os.path.isfile(fname):
                archives_in_srpm.append(os.path.abspath(fname))
    utils.safe_makedirs(destdir)
    old_dir = os.getcwd()
    os.chdir(destdir)
    for fname in archives_downloaded + archives_in_srpm:
        log.info("Extracting " + fname)
        utils.super_unpack(fname)
    os.chdir(old_dir)
    log.info('Extracted files to ' + destdir)


def extract_srpms(srpms_downloaded, destdir):
    """Extract SRPMs to destdir"""
    abs_srpms_downloaded = [os.path.abspath(x) for x in srpms_downloaded]
    utils.safe_makedirs(destdir)
    old_dir = os.getcwd()
    os.chdir(destdir)
    for srpm in abs_srpms_downloaded:
        log.info("Unpacking SRPM " + srpm)
        utils.super_unpack(srpm)
    os.chdir(old_dir)


def copy_with_filter(files_list, destdir):
    """Copy files in files_list to destdir, skipping backup files and
    directories.

    """
    for fname in files_list:
        base = os.path.basename(fname)
        if (base in [WD_RESULTS,
                     WD_PREBUILD,
                     WD_UNPACKED,
                     WD_UNPACKED_TARBALL] or
                base.endswith('~') or
                os.path.isdir(fname)):
            log.debug("Skipping file " + fname)
        else:
            log.debug("Copying file " + fname)
            shutil.copy(fname, destdir)


def fetch(package_dir,
          destdir=None,
          cache_prefix=WEB_CACHE_PREFIX,
          unpacked_dir=None,
          want_full_extract=False,
          unpacked_tarball_dir=None):
    """Process *.source files in upstream/ directory, downloading upstream
    sources mentioned in them from the software cache. Unpack SRPMs if
    there are any. Override upstream files with those in the osg/
    directory. Return the path to the downloaded spec file. 

    """
    if destdir is None:
        destdir = package_dir
    if unpacked_dir is None:
        unpacked_dir = destdir
    if unpacked_tarball_dir is None:
        unpacked_tarball_dir = destdir

    abs_package_dir = os.path.abspath(package_dir)

    upstream_dir = os.path.join(abs_package_dir, 'upstream')
    osg_dir = os.path.join(abs_package_dir, 'osg')

    # Process upstream/*.source files
    dot_sources = glob.glob(os.path.join(upstream_dir, '*.source'))
    downloaded = []
    for src in dot_sources:
        log.debug('Processing .source file %s', src)
        for fname in process_dot_source(cache_prefix, src, destdir):
            downloaded.append(os.path.abspath(fname))

    # Process downloaded SRPMs
    srpms = fnmatch.filter(downloaded, '*.src.rpm')
    if srpms:
        extract_srpms(srpms, unpacked_dir)
    if unpacked_dir != destdir:
        for f in glob.glob(os.path.join(unpacked_dir, '*')):
            log.debug('Copying unpacked file ' + f)
            shutil.copy(f, destdir)

    # Copy non *.source files in upstream
    other_sources = [x for x in glob.glob(os.path.join(upstream_dir, '*'))
                     if (not fnmatch.fnmatch(x, '*.source')
                         and os.path.isfile(x))]
    copy_with_filter(other_sources, destdir)

    # Extract any archives we downloaded plus any archives in the SRPM
    if want_full_extract:
        full_extract(unpacked_dir, downloaded, unpacked_tarball_dir)

    # Override downloaded files with what's in osg/
    copy_with_filter(glob.glob(os.path.join(osg_dir, '*')),
                     destdir)

    # Return list of spec files
    spec_glob = os.path.join(destdir, '*.spec')
    spec_filenames = glob.glob(spec_glob)
    if not spec_filenames:
        raise GlobNotFoundError(spec_glob)
    if len(spec_filenames) > 1:
        log.warning("Multiple spec files found; using %r", spec_filenames[0])

    return spec_filenames[0]
# end of fetch


