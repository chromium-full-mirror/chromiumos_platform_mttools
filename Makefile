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
	OUT=. $(MAKE) -C mtreplay all

clean:
	OUT=. $(MAKE) -C mtreplay clean

install: replay
	mkdir -p $(DESTDIR)/mtedit
	install -m 644 mtedit/*.py $(DESTDIR)/mtedit

	mkdir -p $(DESTDIR)/mtlib
	install -m 644 mtlib/*.py $(DESTDIR)/mtlib

	mkdir -p $(DESTDIR)/mtreplay
	install -m 644 mtreplay/*.py $(DESTDIR)/mtreplay
	install mtreplay/replay $(DESTDIR)/mtreplay/replay

IN_PLACE_DEPS=../libevdev ../gestures mtreplay

setup-in-place:
	# utouch-evemu is currently required, but will be removed soon.
	emerge utouch-evemu

	$(foreach dep, $(IN_PLACE_DEPS), OUT=. make -C $(dep) setup-in-place;)

	# add project folder to python path
	echo "$(SRC)" > $(PYTHON_SITE)/mttools.pth

	# install symlinks to command line tools
	ln -sf $(SRC)/mtedit/main.py /usr/bin/mtedit
	ln -sf $(SRC)/mtreplay/main.py /usr/bin/mtreplay

clean-in-place:
	$(foreach dep, $(IN_PLACE_DEPS), OUT=. make -C $(dep) clean-in-place;)

in-place:
	# can't use foreach loop here, otherwise make errors will be ignored.
	OUT=. make -C ../libevdev in-place
	OUT=. make -C ../gestures in-place
	OUT=. make -C mtreplay in-place
