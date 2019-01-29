"""Fetch sources from upstream locations and combine them with sources from
the osg/ dir in the package.


Lines from upstream/*.source files have syntax like a python function call:

    [args...] [field=value...]


Possible fields names:

    type:     {git|github|cached|uri}
    url:      git clone url (type=git)
    name:     repo name if different from url basename (type=git, optional)
    tag:      git tag or ref to archive (type=git/github)
    hash:     git commit hash (type=git/github, optional if nocheck=True)
    repo:     owner/repo (type=github)
    prefix:   archive prefix dir if not name-tag (type=git/github, optional)
    tarball:  archive name if not prefix.tar.gz (type=git/github, optional)
              (setting tarball will also set a default prefix accordingly)
    spec:     path rpm spec, if not rpm/name.spec (type=git/github, optional)
    relpath:  upstream cache relative path (type=cached)
    uri:      uri for file to download (type=uri)
    filename: outfile if different than uri basename (type=uri, optional)
    sha1sum:  chksum of downloaded file (type=uri/cached, optional)


Each line is associated with a source 'type':

    git:      a git repo url to fetch and produce a git archive
    github:   same as git, but repo=owner/project is shorthand for the url

    cached:   a file to be retrieved from the vdt upstream cache
    uri:      a generic proto://... uri for a file to download


Some initial unnamed args are allowed for the pre-git types:

    cached:   relpath [sha1sum]
    uri:      uri     [sha1sum]

All other options must be specified as name=value keyword args.


If type is unspecified, it will be inferred by the form of the first argument:

    unnamed-arg1         -> inferred-type
    --------------------    -------------
    pkg/version/file.ext -> cached
    proto://...          -> uri
    /abs/path/to/file    -> uri (file://)
"""

# pylint: disable=W0614
from __future__ import absolute_import
from __future__ import print_function
import collections
import fnmatch
import hashlib
import logging
import glob
import re
import os
import tempfile
import shutil
import sys
try:
    from six.moves import urllib
except ImportError:
    from .six.moves import urllib


from . import constants as C
from .error import Error, GlobNotFoundError
from . import utils


if __name__ != "__main__":
    log = logging.getLogger(__name__)
else:
    log = logging.getLogger()
    logging.basicConfig(format="%(message)s", level=logging.INFO)


# common fetch options not found in .source line
FetchOptions = collections.namedtuple('FetchOptions',
    ['destdir', 'cache_prefix', 'nocheck', 'want_spec']
)

# fetch handlers are defined like:
#
#   fetch_xyz_source(
#       required_named_or_positional_arg, ...,
#       optional_named_or_positional_arg=None, ...,
#       ops=None,  # no positional args allowed after 'ops'; only named fields
#       named_arg=None, ...,
#       **kw  # only list if extra args are intended (to pass to another fn)
#   )

def fetch_cached_source(relpath, sha1sum=None, ops=None):
    uri = os.path.join(ops.cache_prefix, relpath)
    return fetch_uri_source(uri, sha1sum, ops=ops)

def fetch_uri_source(uri, sha1sum=None, ops=None, filename=None):
    if uri.startswith('/'):
        uri = "file://" + uri
        log.warning("Absolute path names in .source files break the 4th wall")

    outfile = os.path.join(ops.destdir, os.path.basename(filename or uri))
    got_sha1sum = download_uri(uri, outfile)
    log.debug("got sha1sum=%s for uri=%s" % (got_sha1sum, uri))

    if sha1sum: # or not ops.nocheck:
        check_file_checksum(outfile, sha1sum, got_sha1sum, ops.nocheck)

    return [outfile]

def download_uri(uri, outfile):
    log.info('Retrieving ' + uri)
    try:
        handle = urllib.request.urlopen(uri)
    except urllib.error.URLError as err:
        raise Error("Unable to download %s\n%s" % (uri, err))

    sha = hashlib.sha1()
    try:
        with open(outfile, 'wb') as desthandle:
            for chunk in chunked_read(handle):
                desthandle.write(chunk)
                sha.update(chunk)
    except EnvironmentError as e:
        raise Error("Unable to save downloaded file to %s\n%s" % (outfile, e))
    return sha.hexdigest()

def chunked_read(handle, size=64*1024):
    chunk = handle.read(size)
    while chunk:
        yield chunk
        chunk = handle.read(size)

def check_file_checksum(path, sha1sum, got_sha1sum, nocheck):
    efmt = "sha1 mismatch for '%s':\n    expected: %s\n         got: %s"
    if sha1sum != got_sha1sum:
        msg = efmt % (path, sha1sum, got_sha1sum)
        if nocheck:
            log.warning(msg + "\n    (ignored)")
        else:
            raise Error(msg)

def _required(item, key):
    if item is None:
        raise Error("No '%s' specified" % key)

def _nvl(arg, default):
    return default if arg is None else arg

def _mk_prefix(name, tag, tarball):
    if tarball:
        if not tarball.endswith('.tar.gz'):
            raise Error("tarball must end with .tar.gz: '%s'" % tarball)
        prefix = tarball[:-len('.tar.gz')]
    else:
        tag = os.path.basename(tag)
        tarball_version = re.match(r'(?:v(?=\d))?([^-]+)', tag).group(1)
        prefix = "%s-%s" % (name, tarball_version)
    return prefix

def fetch_github_source(repo, tag, hash=None, ops=None, **kw):
    m = re.match(r"([^\s/]+)/([^\s/]+?)(?:.git)?$", repo)
    if not m:
        raise Error("'repo' syntax for type=github must be owner/project")
    url = "https://github.com/" + repo
    return fetch_git_source(url, tag, hash, ops=ops, **kw)

def fetch_git_source(url, tag, hash=None, ops=None,
        name=None, spec=None, tarball=None, prefix=None):
    name = name or re.sub(r'\.git$', '', os.path.basename(url))
    ops.nocheck or _required(hash, 'hash')
    spec = ops.want_spec and _nvl(spec, "rpm/%s.spec" % name)
    prefix = prefix and prefix.strip('/')
    prefix = prefix or _mk_prefix(name, tag, tarball)
    tarball = tarball and os.path.basename(tarball)
    tarball = tarball or prefix + ".tar.gz"

    return run_with_tmp_git_dir(ops.destdir, lambda:
        git_archive_remote_ref(url, tag, hash, prefix, tarball, spec, ops))

def run_with_tmp_git_dir(destdir, call):
    git_dir = tempfile.mkdtemp(dir=destdir)
    old_git_dir = update_env('GIT_DIR', git_dir)
    try:
        return call()
    finally:
        shutil.rmtree(git_dir)
        update_env('GIT_DIR', old_git_dir)

def update_env(key, val):
    oldval = os.environ.get(key)
    if val is None:
        del os.environ[key]
    else:
        os.environ[key] = val
    return oldval

def git_archive_remote_ref(url, tag, hash, prefix, tarball, spec, ops):
    log.info('Retrieving %s %s' % (url, tag))
    utils.checked_call(['git', 'init', '-q', '--bare'])
    utils.checked_call(['git', 'remote', 'add', 'origin', url])
    utils.checked_call(['git', 'fetch', '-q', '--depth=1', 'origin', tag])
    got_sha = utils.checked_backtick(['git', 'rev-parse', 'FETCH_HEAD'])
    if hash or not ops.nocheck:
        check_git_hash(url, tag, hash, got_sha, ops.nocheck)

    dest_tar_gz = os.path.join(ops.destdir, tarball)
    git_archive_cmd = ['git', 'archive', '--format=tar',
                                         '--prefix=%s/' % prefix, got_sha]
    gzip_cmd = ['gzip', '-n']

    with open(dest_tar_gz, "w") as destf:
        utils.checked_pipeline([git_archive_cmd, gzip_cmd], stdout=destf)

    if spec:
        spec = try_get_spec(ops.destdir, got_sha, spec)

    return list(filter(None, [dest_tar_gz, spec]))

def try_get_spec(destdir, tree_sha, spec):
    dest_spec = os.path.join(destdir, os.path.basename(spec))
    spec_rev = '%s:%s' % (tree_sha, spec)
    _, rc = utils.sbacktick(['git', 'rev-parse', '-q', '--verify', spec_rev])
    if rc:
        log.debug("No spec file found under %s" % spec_rev)
        return None
    with open(dest_spec, "w") as specf:
        utils.checked_call(['git', 'show', spec_rev], stdout=specf)
    return dest_spec

def check_git_hash(url, tag, sha, got_sha, nocheck):
    efmt = "Hash mismatch for %s tag %s\n    expected: %s\n    actual:   %s"
    if sha != got_sha and deref_git_sha(sha) != deref_git_sha(got_sha):
        msg = efmt % (url, tag, sha, got_sha)
        if nocheck:
            log.warning(msg + "\n    (ignored)")
        else:
            raise Error(msg)

def deref_git_sha(sha):
    cmd = ["git", "rev-parse", "-q", "--verify", sha + "^{}"]
    output, rc = utils.sbacktick(cmd)
    if rc:
        log.error("Git failed to parse rev: '%s'" % sha)
        return sha
    return output

def process_source_line(line, ops):
    args,kv = parse_source_line(line)

    handlers = dict(
        git    = fetch_git_source,
        github = fetch_github_source,
        cached = fetch_cached_source,
        uri    = fetch_uri_source,
    )
    explicit_type = kv.pop('type', None)
    meta_type = explicit_type or get_auto_source_type(*args, **kv)
    if meta_type in handlers:
        handler = handlers[meta_type]
        try:
            return handler(*args, ops=ops, **kv)
        except TypeError as e:
            fancy_source_error(meta_type, explicit_type, handler, args, kv, e)
    else:
        raise Error("Unrecognized type '%s' (valid types are: %s)"
                    % (meta_type, sorted(handlers)))

def get_auto_source_type(*args, **kw):
    if not args:
        raise Error("No type specified and no default arg provided")
    if args[0].endswith('.git'):
        raise Error("No automatic types allowed for git sources")
    if re.search(r'^\w+://', args[0]) or args[0].startswith('/'):
        return 'uri'
    else:
        return 'cached'

def parse_source_line(line):
    kv, args = dual_filter((lambda t: t[0]), map(kvmatch, line.split()))
    return [ a[1] for a in args ], dict(kv)

def dual_filter(cond, seq):
    pos,neg = [],[]
    for x in seq:
        (pos if cond(x) else neg).append(x)
    return pos,neg

def kvmatch(arg):
    # return (key,val) for "key=val", else return (None, arg)
    return re.search(r'^(?:(\w+)=)?(.*)', arg).groups()

def fancy_source_error(meta_type, explicit_type, handler, args, kw, e):
    xtype = "type" if explicit_type else "implicit type"
    log.error("Error processing source line of %s '%s'" % (xtype, meta_type))
    varnames = handler.__code__.co_varnames
    fn_argcount = handler.__code__.co_argcount
    maxargs = varnames.index('ops')
    posargs = varnames[:maxargs]
    posargs_provided = posargs[:len(args)]
    dupe_args = set(posargs_provided) & set(kw)

    pos_usage = ' '.join("[%s=]arg%s" % (a,i+1) for i,a in enumerate(posargs))
    log.error("Up to %s unnamed initial arguments are allowed: %s"
              % (maxargs, pos_usage))

    if dupe_args:
        for arg in dupe_args:
            log.error("No unnamed positional arguments allowed after"
                      " explicit '%s' named field" % arg)
    elif len(args) > maxargs:
        log.error("Provided %s positional arguments: %s"
                  % (len(args), ' '.join(args)))
    else:
        log.error(e)
    raise Error("Invalid parameters for %s=%s source line" % (xtype,meta_type))

def process_dot_source(cache_prefix, sfilename, destdir, nocheck, want_spec):
    """Read a .source file, fetch any sources specified in it."""
    ops = FetchOptions(destdir=destdir, cache_prefix=cache_prefix,
                       nocheck=nocheck, want_spec=want_spec)

    utils.safe_makedirs(destdir)
    filenames = []
    for line in open(sfilename):
        line = re.sub(r'(^|\s)#.*', '', line).strip()
        if line:
            try:
                filenames += process_source_line(line, ops)
            except Error as e:
                log.error("Error processing source line: '%s'" % line)
                raise

    return filenames


def full_extract(unpacked_dir, archives_downloaded, destdir):
    """Extract downloaded archives plus archives inside downloaded SRPMs"""
    archives_in_srpm = []
    if os.path.isdir(unpacked_dir):
        for fname in glob.glob(os.path.join(unpacked_dir, '*')):
            if os.path.isfile(fname):
                archives_in_srpm.append(os.path.abspath(fname))
    utils.safe_makedirs(destdir)
    utils.pushd(destdir)
    for fname in archives_downloaded + archives_in_srpm:
        log.info("Extracting " + fname)
        utils.super_unpack(fname)
    utils.popd()
    log.info('Extracted files to ' + destdir)


def extract_srpms(srpms_downloaded, destdir):
    """Extract SRPMs to destdir"""
    abs_srpms_downloaded = [os.path.abspath(x) for x in srpms_downloaded]
    utils.safe_makedirs(destdir)
    utils.pushd(destdir)
    for srpm in abs_srpms_downloaded:
        log.info("Unpacking SRPM " + srpm)
        utils.super_unpack(srpm)
    utils.popd()


def copy_with_filter(files_list, destdir):
    """Copy files in files_list to destdir, skipping backup files and
    directories.

    """
    for fname in files_list:
        base = os.path.basename(fname)
        if (base in [C.WD_RESULTS,
                     C.WD_PREBUILD,
                     C.WD_UNPACKED,
                     C.WD_UNPACKED_TARBALL] or
                base.endswith('~') or
                os.path.isdir(fname)):
            log.debug("Skipping file " + fname)
        else:
            log.debug("Copying file " + fname)
            shutil.copy(fname, destdir)


def fetch(package_dir,
          destdir=None,
          cache_prefix=C.WEB_CACHE_PREFIX,
          unpacked_dir=None,
          want_full_extract=False,
          unpacked_tarball_dir=None,
          nocheck=False,
          want_spec=True):
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
        for fname in process_dot_source(cache_prefix, src, destdir, nocheck,
                                                                    want_spec):
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
        raise Error("Multiple spec files found: " + ", ".join(spec_filenames))

    return spec_filenames[0]
# end of fetch


if __name__ == '__main__':
    nocheck = False
    package_dirs = []
    if len(sys.argv) < 2:
        package_dirs = ["."]
    else:
        for arg in sys.argv[1:]:
            if arg == "--nocheck":
                nocheck = True
            else:
                package_dirs.append(arg)
    try:
        for package_dir in package_dirs:
            fetch(os.path.abspath(package_dir), nocheck=nocheck)
    except Error as e:
        print("Error: %s" % e, file=sys.stderr)
        sys.exit(1)
