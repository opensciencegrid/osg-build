#!/usr/bin/python
"Tests osgbuild/kojiinter.py"

from osgbuild import kojiinter

kwrap = kojiinter.KojiLibInter()
kwrap.read_config_file()
kwrap.init_koji_session()
print kwrap.search('osg-build-1.1.5-1.osg.el5', 'build', 'exact')

for t in kwrap.kojisession.listTags(None, None):
    print t

