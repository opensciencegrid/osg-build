VERSION = 1.8.90
NAME = osg-build
NAME_VERSION = $(NAME)-$(VERSION)
PYDIR = osgbuild
TESTDIR = $(PYDIR)/test
SVNDATADIR = data
SVNDOCDIR = doc
MAIN_SCRIPT = $(NAME)
MAIN_SCRIPT_SYMLINK = vdt-build
EXTRA_SCRIPTS = koji-tag-diff osg-import-srpm osg-koji osg-promote koji-blame
MAIN_TEST_SYMLINK = osg-build-test
MAIN_TEST = $(TESTDIR)/test_osgbuild.py
PYTHON_SITELIB = $(shell python -c "from distutils.sysconfig import get_python_lib; import sys; sys.stdout.write(get_python_lib())")
PYTHON26_SITELIB = $(shell python26 -c "from distutils.sysconfig import get_python_lib; import sys; sys.stdout.write(get_python_lib())")
BINDIR = /usr/bin
DOCDIR = /usr/share/doc/$(NAME)
DATADIR = /usr/share/$(NAME)
AFS_SOFTWARE_DIR = /p/vdt/public/html/upstream/$(NAME)

_default:
	@echo "Nothing to make. Try make install"

clean:
	rm -f *.py[co] *~ $(PYDIR)/*.py[co] $(PYDIR)/*~ $(TESTDIR)/*.py[co] $(TESTDIR)/*~ tags

install-common:
	mkdir -p $(DESTDIR)/$(DOCDIR)
	install -p -m 644 $(SVNDOCDIR)/* $(DESTDIR)/$(DOCDIR)

	mkdir -p $(DESTDIR)/$(BINDIR)
	install -p -m 755 $(MAIN_SCRIPT) $(DESTDIR)/$(BINDIR)
	install -p -m 755 $(EXTRA_SCRIPTS) $(DESTDIR)/$(BINDIR)
	ln -snf $(MAIN_SCRIPT) $(DESTDIR)/$(BINDIR)/$(MAIN_SCRIPT_SYMLINK)

	mkdir -p $(DESTDIR)/$(DATADIR)
	install -p -m 644 $(SVNDATADIR)/* $(DESTDIR)/$(DATADIR)


install: install-common
	mkdir -p $(DESTDIR)/$(PYTHON_SITELIB)/$(PYDIR)
	install -p -m 644 $(PYDIR)/*.py $(DESTDIR)/$(PYTHON_SITELIB)/$(PYDIR)

	mkdir -p $(DESTDIR)/$(PYTHON_SITELIB)/$(TESTDIR)
	install -p -m 755 $(TESTDIR)/*.py $(DESTDIR)/$(PYTHON_SITELIB)/$(TESTDIR)

	ln -snf $(PYTHON_SITELIB)/$(MAIN_TEST) $(DESTDIR)/$(BINDIR)/$(MAIN_TEST_SYMLINK)

install-python26: install-common
	mkdir -p $(DESTDIR)/$(PYTHON26_SITELIB)/$(PYDIR)
	install -p -m 644 $(PYDIR)/*.py $(DESTDIR)/$(PYTHON26_SITELIB)/$(PYDIR)

	mkdir -p $(DESTDIR)/$(PYTHON26_SITELIB)/$(TESTDIR)
	install -p -m 755 $(TESTDIR)/*.py $(DESTDIR)/$(PYTHON26_SITELIB)/$(TESTDIR)

	ln -snf $(PYTHON26_SITELIB)/$(MAIN_TEST) $(DESTDIR)/$(BINDIR)/$(MAIN_TEST_SYMLINK)

	for script in $(MAIN_SCRIPT) $(EXTRA_SCRIPTS); do \
		sed -i -e '1s#/usr/bin/python#/usr/bin/python26#' $(DESTDIR)/$(BINDIR)/$$script; \
		sed -i -e '1s#/usr/bin/env python$$#/usr/bin/python26#' $(DESTDIR)/$(BINDIR)/$$script; \
	done


dist:
	mkdir -p $(NAME_VERSION)
	cp -rp $(MAIN_SCRIPT) $(EXTRA_SCRIPTS) $(PYDIR) $(SVNDATADIR) $(SVNDOCDIR) Makefile pylintrc $(NAME_VERSION)/
	sed -i -e '/__version__/s/@VERSION@/$(VERSION)/' $(NAME_VERSION)/$(PYDIR)/main.py
	tar czf $(NAME_VERSION).tar.gz $(NAME_VERSION)/ --exclude='*/.svn*' --exclude='*/*.py[co]' --exclude='*/*~'

afsdist: dist
	mkdir -p $(AFS_SOFTWARE_DIR)/$(VERSION)
	mv -i $(NAME_VERSION).tar.gz $(AFS_SOFTWARE_DIR)/$(VERSION)/
	rm -rf $(NAME_VERSION)

release: dist
	@if [ "$(DESTDIR)" = "" ]; then                                        \
		echo " ";                                                      \
		echo "ERROR: DESTDIR is required";                             \
		exit 1;                                                        \
	fi
	mkdir -p $(DESTDIR)/$(NAME)/$(VERSION)
	mv -i $(NAME_VERSION).tar.gz $(DESTDIR)/$(NAME)/$(VERSION)/
	rm -rf $(NAME_VERSION)

check:
	pylint -E osg-build osg-promote osg-koji $(PYDIR)/*.py $(TESTDIR)/*.py
test:
	pylint -E osg-build osg-promote osg-koji $(PYDIR)/*.py $(TESTDIR)/*.py
	python $(MAIN_TEST) -v TestSuiteAll
	python $(TESTDIR)/test_osgpromote.py

shorttest:
	pylint -E osg-build osg-promote osg-koji $(PYDIR)/*.py $(TESTDIR)/*.py
	python $(MAIN_TEST) -v TestSuiteShort
	python $(TESTDIR)/test_osgpromote.py

lint:
	-pylint --rcfile=pylintrc osg-build osg-promote osg-koji $(PYDIR)/*.py $(TESTDIR)/*.py
# ignore return code in above

tags:
	-ctags -R --exclude='.backup' --exclude='.bak' --exclude='*~' --exclude='.svn' --exclude='_darcs' --exclude='.git' --exclude='CVS' --exclude='.pyc' --exclude='Attic/*' --exclude='data/*' --exclude='doc/*' .

.PHONY: _default clean install-common install install-python26 dist afsdist release check test shorttest lint tags
