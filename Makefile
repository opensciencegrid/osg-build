VERSION = 0.0.17
PYFILES = $(wildcard *.py) vdtkoji.conf
# TODO: Move vdtkoji.conf
MAIN_SCRIPT = vdt-build
PYTHON_SITELIB = $(shell python -c "from distutils.sysconfig import get_python_lib; import sys; sys.stdout.write(get_python_lib())")
BINDIR = /usr/bin
DOCDIR = /usr/share/doc/vdt-build
AFS_SOFTWARE_DIR = /p/vdt/public/html/upstream/vdt-build

_default:
	@echo "Nothing to make. Try make install"

clean:
	rm -f *.py[co] *~

install:
	@if [ "$(DESTDIR)" = "" ]; then                                        \
		echo " ";                                                      \
		echo "ERROR: DESTDIR is required";                             \
		exit 1;                                                        \
	fi

	mkdir -p $(DESTDIR)/$(PYTHON_SITELIB)
	for p in $(PYFILES); do                                                \
		install -p -m 644 $$p $(DESTDIR)/$(PYTHON_SITELIB)/$$p;        \
	done
	mkdir -p $(DESTDIR)/$(DOCDIR)
	install -p -m 644 sample-vdt-build.ini $(DESTDIR)/$(DOCDIR)/sample-vdt-build.ini
	    
	mkdir -p $(DESTDIR)/$(BINDIR)
	install -p -m 755 $(MAIN_SCRIPT) $(DESTDIR)/$(BINDIR)

	sed -i -e '/__version__/s/@VERSION@/$(VERSION)/' $(DESTDIR)/$(BINDIR)/$(MAIN_SCRIPT)

dist:
	mkdir -p vdt-build-$(VERSION)
	cp -p $(PYFILES) $(MAIN_SCRIPT) Makefile sample-vdt-build.ini vdt-build-$(VERSION)/
	tar czf vdt-build-$(VERSION).tar.gz vdt-build-$(VERSION)/

afsdist: dist
	mkdir -p $(AFS_SOFTWARE_DIR)/$(VERSION)
	mv -f vdt-build-$(VERSION).tar.gz $(AFS_SOFTWARE_DIR)/$(VERSION)/
	rm -rf vdt-build-$(VERSION)

release: dist
	@if [ "$(DESTDIR)" = "" ]; then                                        \
		echo " ";                                                      \
		echo "ERROR: DESTDIR is required";                             \
		exit 1;                                                        \
	fi
	mkdir -p $(DESTDIR)/vdt-build/$(VERSION)
	mv -f vdt-build-$(VERSION).tar.gz $(DESTDIR)/vdt-build/$(VERSION)/
	rm -rf vdt-build-$(VERSION)

	
