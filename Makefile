VERSION = 0.0.23
NAME = osg-build
NAME_VERSION = $(NAME)-$(VERSION)
PYDIR = osg_build_lib
DATAFILES = osg-koji-site.conf osg-koji-home.conf
INIFILE = sample-osg-build.ini
MAIN_SCRIPT = $(NAME)
MAIN_SCRIPT_SYMLINK = vdt-build
EXTRA_SCRIPTS = osg-import-srpm rpm-ripper osg-koji
PYTHON_SITELIB = $(shell python -c "from distutils.sysconfig import get_python_lib; import sys; sys.stdout.write(get_python_lib())")
BINDIR = /usr/bin
DOCDIR = /usr/share/doc/$(NAME)
DATADIR = /usr/share/$(NAME)
AFS_SOFTWARE_DIR = /p/vdt/public/html/upstream/$(NAME)

_default:
	@echo "Nothing to make. Try make install"

clean:
	rm -f *.py[co] *~ $(PYDIR)/*.py[co] $(PYDIR)/*~

install:
	@if [ "$(DESTDIR)" = "" ]; then                                        \
		echo " ";                                                      \
		echo "ERROR: DESTDIR is required";                             \
		exit 1;                                                        \
	fi

	mkdir -p $(DESTDIR)/$(PYTHON_SITELIB)
	cp -rp $(PYDIR) $(DESTDIR)/$(PYTHON_SITELIB)/
	chmod 0755 $(DESTDIR)/$(PYTHON_SITELIB)/$(PYDIR)/*

	mkdir -p $(DESTDIR)/$(DOCDIR)
	install -p -m 644 $(INIFILE) $(DESTDIR)/$(DOCDIR)/$(INIFILE)

	mkdir -p $(DESTDIR)/$(BINDIR)
	install -p -m 755 $(MAIN_SCRIPT) $(DESTDIR)/$(BINDIR)
	ln -s $(MAIN_SCRIPT) $(DESTDIR)/$(BINDIR)/$(MAIN_SCRIPT_SYMLINK)
	install -p -m 755 $(EXTRA_SCRIPTS) $(DESTDIR)/$(BINDIR)

	mkdir -p $(DESTDIR)/$(DATADIR)
	install -p -m 644 $(DATAFILES) $(DESTDIR)/$(DATADIR)

	sed -i -e '/__version__/s/@VERSION@/$(VERSION)/' $(DESTDIR)/$(BINDIR)/$(MAIN_SCRIPT)

dist:
	mkdir -p $(NAME_VERSION)
	cp -rp $(PYDIR) $(MAIN_SCRIPT) $(EXTRA_SCRIPTS) $(DATAFILES) Makefile $(INIFILE) $(NAME_VERSION)/
	tar czf $(NAME_VERSION).tar.gz $(NAME_VERSION)/ --exclude='*/.svn*' --exclude='*/*.py[co]' --exclude='*/*~'

afsdist: dist
	mkdir -p $(AFS_SOFTWARE_DIR)/$(VERSION)
	mv -f $(NAME_VERSION).tar.gz $(AFS_SOFTWARE_DIR)/$(VERSION)/
	rm -rf $(NAME_VERSION)

release: dist
	@if [ "$(DESTDIR)" = "" ]; then                                        \
		echo " ";                                                      \
		echo "ERROR: DESTDIR is required";                             \
		exit 1;                                                        \
	fi
	mkdir -p $(DESTDIR)/$(NAME)/$(VERSION)
	mv -f $(NAME_VERSION).tar.gz $(DESTDIR)/$(NAME)/$(VERSION)/
	rm -rf $(NAME_VERSION)


