# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# find location of site_packages
define PYTHON_GET_SITE
from distutils.sysconfig import get_python_lib;
print get_python_lib()
endef
PYTHON_SITE=$(shell python -c "$(PYTHON_GET_SITE)")

# absolute path to source folder
SRC=$(shell readlink -f .)

all: replay

replay:
	OUT=. make -C mtlib/replay all

clean:
	OUT=. make -C mtlib/replay clean

install: replay
	# write source folder into pth file, which adds it to the module
	# search path of python
	echo "$(shell readlink -f .)" > $(PYTHON_SITE)/mttools.pth

	# install symlinks to command line tools
	ln -sf $(SRC)/mtedit/main.py /usr/bin/mtedit
