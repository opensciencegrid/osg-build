#!/usr/bin/env python
import sys

tasklistfh = open("tasklist.nmi", "w")
print >>tasklistfh, "\n".join(sys.argv[1:])
tasklistfh.close()

