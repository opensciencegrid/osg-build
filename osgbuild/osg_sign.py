"""Sign packages in Koji.  Download the RPMs, add the requested signatures,
and import them back.  Requires access to the signing key and the "admin"
Koji permission.
"""
from argparse import ArgumentParser
import glob
import logging
import re
import os
import shutil
import subprocess
from tempfile import TemporaryDirectory
from typing import List, Optional, Dict

from . import constants
from .error import Error, ProgramNotFoundError, KojiError, ConfigErrors
from . import utils
from .kojiinter import KojiHelper
from .utils import IniConfiguration

log = logging.getLogger(__name__)


class SigningError(Error):
    """Base class for errors in the signing module"""


class SigningKey(object):
    """Information about a signing key"""

    def __init__(self, name: str, keyid: str, dvers: List[str], digest_algo: Optional[str]):
        self.name = name
        self.keyid = keyid
        self.dvers = dvers
        self.digest_algo = digest_algo or None
        self.all_signing_keyids = []

    def query_all_signing_keyids(self):
        """Asks GPG for the keyids of the primary and all subkeys that can be
        used to sign packages (i.e. have 's' or 'S' in the 'capabilities' field.

        Saves the results.
        """
        if not self.all_signing_keyids:
            ret = subprocess.run(["gpg", "--list-keys", "--with-colons", self.keyid],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 encoding="latin-1")
            if ret.returncode != 0:
                log.warning("Could not get information about subkeys for %s", self.keyid)
                log.warning("gpg exited with return code %d", ret.returncode)
                log.warning("Output:\n%s", ret.stdout)
                log.warning("Error:\n%s", ret.stderr)
                return []

            signing_keyids = []
            for line in ret.stdout.splitlines():
                try:
                    if ":" not in line:
                        continue
                    fields = line.split(":")
                    type_of_record = fields[0]
                    if type_of_record not in ["pub", "sub"]:  # primary or subkey
                        continue
                    key_id = fields[4].lower()[-8:]
                    capabilities = fields[11]
                    if 's' in capabilities.lower():  # this key can sign
                        signing_keyids.append(key_id)
                except IndexError as err:
                    log.warning("Unexpected output from gpg: IndexError %s for line\n%s", err, line)
                    return []

            self.all_signing_keyids = signing_keyids
        return self.all_signing_keyids

    def have_public_key(self) -> bool:
        """Return True if we have the public key for this SigningKey.

        """
        with open(os.devnull, "w") as devnull:
            err = subprocess.call(["gpg", "--list-keys", self.keyid],
                                  stdout=devnull,
                                  stderr=devnull)
            return err == 0

    def have_secret_key(self) -> bool:
        """Return True if we have the public key for this SigningKey.

        """
        with open(os.devnull, "w") as devnull:
            err = subprocess.call(["gpg", "--list-secret-keys", self.keyid],
                                  stdout=devnull,
                                  stderr=devnull)
            return err == 0

    def __str__(self):
        return "%s (%s)" % (self.name, self.keyid)

    def __repr__(self):
        return "SigningKey(%r, %r, %r, %r)" % (self.name, self.keyid, self.dvers, self.digest_algo)

    def __lt__(self, other):
        return (self.name, self.keyid) < (other.name, other.keyid)


class SigningKeysConfig(IniConfiguration):
    """Configuration for the available signing keys"""

    def __init__(self, inifiles):
        super().__init__(inifiles)

        signing_key_sections = [sec for sec in self.cp.sections() if sec.startswith('key ')]

        self.signing_keys_by_name = self.parse_signing_keys(signing_key_sections)
        self.signing_keys_by_keyid = {sk.keyid: sk for sk in self.signing_keys_by_name.values()}

    def parse_signing_keys(self, signing_key_sections: List[str]) -> Dict[str, SigningKey]:
        """Parse the 'key X' sections of the config file

        A section called "key X" creates a signing key named "X"
        Required attributes in a key section are:
        - keyid: the short hex ID of the key
        - dvers: a comma or space separated list of dvers this key is used for

        Optional attributes:
        - digest_algo: the digest algorithm, sha256 or sha1
        """
        signing_keys = {}
        for sec in signing_key_sections:
            keyname = sec.split(None, 1)[1]
            keyid = self.config_safe_get(sec, 'keyid')
            dvers = self.config_safe_get_list(sec, 'dvers')
            digest_algo = self.config_safe_get(sec, 'digest_algo')
            errors = []
            if not keyid:
                errors.append("keyid not provided")
            elif not re.match(r'[0-9a-zA-Z]{8}', keyid):
                errors.append("keyid %r is not an 8-char hex string" % keyid)
            if not dvers:
                errors.append("dvers not provided or empty")
            if errors:
                raise ConfigErrors("Section %r" % sec, errors)
            signing_keys[keyname] = SigningKey(keyname, keyid.lower(), dvers, digest_algo=digest_algo)
        return signing_keys


def check_program_requirements():
    """Checks if we have the necessary programs to do everything.
    Raises ProgramNotFoundError if we're missing something.

    """
    for program in "rpm", "osg-koji", "rpmsign", "gpg":
        if not utils.which(program):
            raise ProgramNotFoundError(program)


def check_permissions_requirements():
    """Checks if we have the permissions necessary to do everything.
    This means Koji 'sign'.  'admin' will also do.

    """
    perms, status = utils.sbacktick(["osg-koji", "-q", "list-permissions", "--mine"])
    if status != 0:
        raise KojiError("Error getting Koji permissions")
    if "admin" not in perms and "sign" not in perms:
        raise Error("Koji 'sign' or 'admin' permission required")


def do_list_keys(config: SigningKeysConfig):
    """Handle the --list-keys command: print a table of signing keys,
    their names, IDs, what distro versions they can be used for and whether we
    can use them to sign, i.e., have the secret keys for them.

    """
    print("Signing keys:")
    utils.print_line()
    fmt = "%-7s %-31s %-11s %-17s %-7s"
    gpg_bin = utils.which("gpg")
    if not gpg_bin:
        log.warning("gpg not found; unable to check which keys are available")
    print(fmt % (" Sign ", " Name ", " Key ID ", " Supported dvers ", " Digest algo "))
    print(fmt % ("------", "------", "--------", "-----------------", "-------------"))
    for sk in sorted(config.signing_keys_by_name.values()):
        can_sign = "  ?"
        if gpg_bin:
            can_sign = "  Y" if sk.have_secret_key() else "  N"
        print(fmt % (can_sign, sk.name, sk.keyid, ", ".join(sk.dvers), sk.digest_algo or "DEFAULT"))


def sign_rpms(signing_key, rpms):
    rpm_cmd = ["rpm", "--resign"]
    rpm_cmd += ["--define", f"_signature gpg",
                "--define", f"_gpg_name {signing_key.keyid}",
                "--define", f"_gpgbin {utils.which('gpg')}",
                "--define", f"__gpg {utils.which('gpg')}",
                ]
    if signing_key.digest_algo:
        rpm_cmd += ["--define", f"_gpg_digest_algo {signing_key.digest_algo}"]
    rpm_cmd += rpms

    try:
        log.debug("Signing rpm with command %r", rpm_cmd)
        subprocess.run(rpm_cmd, timeout=300, check=True)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as err:
        raise SigningError("Signing failed: %s" % err) from err

    log.info("Signing complete.")


def import_signatures(rpms: List[str]):
    """Import the signatures from the given RPM files into Koji."""
    try:
        subprocess.run(["osg-koji", "import-sig"] + rpms, timeout=900, check=True)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as err:
        raise SigningError("Import of signatures failed (%s)" % err) from err


def sign_and_import_build(build_nvr: str, signing_key: SigningKey, kojihelper: KojiHelper, results_dir=None,
                          dry_run=False):
    """Download RPMs for the given `build_nvr` and sign them with the given
    `signing_key`.  Import back into Koji the ones that Koji doesn't already
    have signatures with this key for.

    Optionally put the downloaded RPMs in `results_dir`.

    Note: rpm may decide to sign using a subkey of the given signing key, not
          the primary key.

    """
    rpms_and_keyids = kojihelper.get_rpms_and_keyids_in_build(build_nvr)
    signing_keyids = signing_key.query_all_signing_keyids()

    rpms_to_import = []
    # ^^ we're actually importing _signatures_, not RPMs, but this is a list
    #    of RPM files to take the signatures from.
    log.debug("signing_keyids: %r", signing_keyids)
    for rk in rpms_and_keyids:
        log.debug("rpm=%r signatures=%r", rk.rpm, rk.keyids)
        if set(signing_keyids).isdisjoint(rk.keyids):
            log.debug("needs signing; adding")
            rpms_to_import.append(rk.rpm)
    log.info("%d out of %d RPMs in %s need signing and importing",
             len(rpms_to_import), len(rpms_and_keyids), build_nvr)

    with TemporaryDirectory(prefix=f"osg-sign-{build_nvr}") as workdir:
        with utils.chdir(workdir):
            utils.checked_call(["osg-koji",
                                "download-build",
                                "--debuginfo",
                                "--noprogress",
                                build_nvr])

        rpms = glob.glob(os.path.join(workdir, "*.rpm"))
        sign_rpms(signing_key, rpms)

        if results_dir is not None:
            results_dir = os.path.abspath(results_dir)
            if not os.path.exists(results_dir):
                os.mkdir(results_dir)
            try:
                for rpm in rpms:
                    dst = os.path.join(results_dir, os.path.basename(rpm))
                    shutil.copy(rpm, dst)
                    log.info("RPM copied to %s", dst)
            except OSError as err:
                log.warning("Error copying RPMs back to %s: %s", results_dir, err)

        if dry_run:
            log.info("Stopping because we're in dry-run mode")
            return

        if rpms_to_import:
            with utils.chdir(workdir):
                import_signatures(rpms_to_import)
        else:
            log.info("No signatures need to be imported")


def main(argv: List[str]):
    """Main function"""
    progdir = os.path.realpath(os.path.dirname(argv[0]))
    os.environ['PATH'] = progdir + ":" + os.environ['PATH']
    check_program_requirements()

    prog = os.path.basename(argv[0])
    config = SigningKeysConfig(utils.find_file(constants.SIGNING_KEYS_INI, strict=True))
    args = parse_commandline_args(argv)

    if prog == "osg-sign":  # HACK. Is there a better way to do this?
        logging.basicConfig(format=f"{prog}: %(message)s", level=args.loglevel)
    log.setLevel(args.loglevel)

    if args.list_keys:
        do_list_keys(config)
        return 0

    if not args.dry_run:
        check_permissions_requirements()

    if args.signing_key in config.signing_keys_by_name:
        signing_key = config.signing_keys_by_name[args.signing_key]
    elif args.signing_key in config.signing_keys_by_keyid:
        signing_key = config.signing_keys_by_keyid[args.signing_key]
    else:
        raise SigningError(
            f"No signing key matching {args.signing_key} was found.\n"
            f"Run `{prog} --list-keys` to see which keys are available.")

    if not signing_key.have_secret_key():
        raise SigningError(f"Secret key for signing key {signing_key} not available.")

    kojihelper = KojiHelper(do_login=not args.dry_run)

    for build in args.build:
        sign_and_import_build(build, signing_key, kojihelper, results_dir=args.results, dry_run=args.dry_run)


# end of main()


def parse_commandline_args(argv: List[str]):
    """Parse command-line args and validate them."""
    prog = os.path.basename(argv[0])
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "signing_key",
        nargs="?",
        default=None,
        help="The signing key to use. "
             "Signing key can be specified by name or ID. "
             "Run `%(prog)s --list-keys` to list available signing keys.",
    )
    parser.add_argument(
        "build",
        nargs="*",
        help="A package build to sign",
    )
    parser.add_argument(
        "--list-keys",
        action="store_true",
        help="List available signing keys",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Sign RPMs only, don't import the results; "
             "does not require Koji admin permission"
    )
    parser.add_argument(
        "--results",
        default=None,
        help="Copy the resulting signed RPMs to this directory; the directory "
             "will be created if it doesn't exist."
    )
    parser.add_argument("--debug",
                        action="store_const",
                        const=logging.DEBUG,
                        dest="loglevel",
                        help="Display debug output")
    parser.add_argument("--quiet",
                        action="store_const",
                        const=logging.WARNING,
                        dest="loglevel",
                        help="Display warnings and errors only")
    parser.set_defaults(loglevel=logging.INFO)

    args = parser.parse_args(argv[1:])

    if args.list_keys:
        # no additional checks needed
        return args

    if not args.signing_key:
        parser.error(
            f"Signing key not specified.\n"
            f"Run `{prog} --list-keys` to see which keys are available.")

    if not args.build:
        parser.error("No builds specified.")

    return args
