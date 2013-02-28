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
	OUT=. $(MAKE) -C mtlib/replay all

clean:
	OUT=. $(MAKE) -C mtlib/replay clean

install: replay
	mkdir -p $(DESTDIR)/mtedit
	install -m 644 mtedit/*.py $(DESTDIR)/mtedit
	mkdir -p $(DESTDIR)/mtlib/replay
	install -m 644 mtlib/*.py $(DESTDIR)/mtlib
	install mtlib/replay/replay $(DESTDIR)/mtlib/replay

IN_PLACE_DEPS=../libevdev ../gestures mtlib/replay

setup-in-place:
	# utouch-evemu is currently required, but will be removed soon.
	emerge utouch-evemu

	$(foreach dep, $(IN_PLACE_DEPS), OUT=. make -C $(dep) setup-in-place;)

	# add project folder to python path
	echo "$(SRC)" > $(PYTHON_SITE)/mttools.pth

	# install symlinks to command line tools
	ln -sf $(SRC)/mtedit/main.py /usr/bin/mtedit

clean-in-place:
	$(foreach dep, $(IN_PLACE_DEPS), OUT=. make -C $(dep) clean-in-place;)

in-place:
	# can't use foreach loop here, otherwise make errors will be ignored.
	make -C ../libevdev in-place
	make -C ../gestures in-place
	make -C mtlib/replay in-place
