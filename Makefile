# version now specified in osgbuild/version.py
PYTHON = python
VERSION := $(shell $(PYTHON) -c "import sys; sys.path.insert(0, '.'); from osgbuild import version; sys.stdout.write(version.__version__ + '\n')")
HASH := $(shell git rev-parse HEAD)
NAME = osg-build
NAME_VERSION = $(NAME)-$(VERSION)
PYDIR = osgbuild
TESTDIR = $(PYDIR)/test
SVNDATADIR = data
MAIN_SCRIPT = $(NAME)
EXTRA_SCRIPTS = koji-tag-diff osg-import-srpm osg-koji osg-promote koji-blame
MAIN_TEST_SYMLINK = osg-build-test
MAIN_TEST = $(TESTDIR)/test_osgbuild.py
PYTHON_SITELIB := $(shell $(PYTHON) -c "import sysconfig; print(sysconfig.get_paths()['platlib'])")
BINDIR = /usr/bin
DATADIR = /usr/share/$(NAME)
AFS_SOFTWARE_DIR = /p/vdt/public/html/upstream/$(NAME)

_default:
	@echo "Nothing to make. Try make install"

clean:
	rm -f *.py[co] *~ $(PYDIR)/*.py[co] $(PYDIR)/*~ $(TESTDIR)/*.py[co] $(TESTDIR)/*~ tags

install-common:
	mkdir -p $(DESTDIR)/$(BINDIR)
	install -p -m 755 $(MAIN_SCRIPT) $(DESTDIR)/$(BINDIR)
	install -p -m 755 $(EXTRA_SCRIPTS) $(DESTDIR)/$(BINDIR)

	mkdir -p $(DESTDIR)/$(DATADIR)
	install -p -m 644 $(SVNDATADIR)/* $(DESTDIR)/$(DATADIR)


install: install-common
	mkdir -p $(DESTDIR)/$(PYTHON_SITELIB)/$(PYDIR)
	install -p -m 644 $(PYDIR)/*.py $(DESTDIR)/$(PYTHON_SITELIB)/$(PYDIR)

	mkdir -p $(DESTDIR)/$(PYTHON_SITELIB)/$(TESTDIR)
	install -p -m 755 $(TESTDIR)/*.py $(DESTDIR)/$(PYTHON_SITELIB)/$(TESTDIR)

	ln -snf $(PYTHON_SITELIB)/$(MAIN_TEST) $(DESTDIR)/$(BINDIR)/$(MAIN_TEST_SYMLINK)

dist:
	mkdir -p $(NAME_VERSION)
	cp -rp $(MAIN_SCRIPT) $(EXTRA_SCRIPTS) $(PYDIR) $(SVNDATADIR) Makefile pylintrc $(NAME_VERSION)/
	tar czf $(NAME_VERSION).tar.gz $(NAME_VERSION)/ --exclude='*/.svn*' --exclude='*/*.py[co]' --exclude='*/*~'

check:
	pylint -E osg-build osg-promote osg-koji $(PYDIR)/*.py $(TESTDIR)/*.py
test:
	pylint -E osg-build osg-promote osg-koji $(PYDIR)/*.py $(TESTDIR)/*.py
	$(PYTHON) $(MAIN_TEST) -v TestSuiteAll
	$(PYTHON) $(TESTDIR)/test_osgpromote.py

shorttest:
	pylint -E osg-build osg-promote osg-koji $(PYDIR)/*.py $(TESTDIR)/*.py
	$(PYTHON) $(MAIN_TEST) -v TestSuiteShort
	$(PYTHON) $(TESTDIR)/test_osgpromote.py

lint:
	-pylint --rcfile=pylintrc osg-build osg-promote osg-koji $(PYDIR)/*.py $(TESTDIR)/*.py
# ignore return code in above

tags:
	-ctags -R --exclude='.backup' --exclude='.bak' --exclude='*~' --exclude='.svn' --exclude='_darcs' --exclude='.git' --exclude='CVS' --exclude='.pyc' --exclude='Attic/*' --exclude='data/*' --exclude='doc/*' .

testsource:
	mkdir -p upstream
	echo "type=git url=. name=osg-build tag=HEAD tarball=$(NAME_VERSION).tar.gz hash=$(HASH)" > upstream/test.source

rpmbuild: testsource
	osg-build rpmbuild

kojiscratch: testsource
	osg-build koji --scratch --getfiles

.PHONY: _default clean install-common install dist check test shorttest lint tags testsource rpmbuild kojiscratch
