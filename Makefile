# Copyright 2014 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# find location of Python site_packages (semicolons required because line breaks
# are ignored)
define PYTHON_GET_SITE
from __future__ import print_function;
from distutils.sysconfig import get_python_lib;
print(get_python_lib());
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

	mkdir -p $(DESTDIR)/mtbringup
	install -m 644 mtbringup/*.py $(DESTDIR)/mtbringup

	mkdir -p $(DESTDIR)/mtreplay
	install -m 644 mtreplay/*.py $(DESTDIR)/mtreplay
	install mtreplay/replay $(DESTDIR)/mtreplay/replay

	# for each filetype in tests folder
	mkdir -p $(DESTDIR)/platforms
	for file in platforms/* ; do \
		install -D $$file $(DESTDIR)/platforms/; \
	done

	# Copy symlinks
	if test -L remote; then cp -d remote $(DESTDIR)/; fi

IN_PLACE_DEPS=../libevdev ../gestures mtreplay

setup-in-place:
	$(foreach dep, $(IN_PLACE_DEPS), OUT=. make -C $(dep) setup-in-place;)

	# add project folder to python path
	echo "$(SRC)" > $(PYTHON_SITE)/mttools.pth

	# install symlinks to command line tools
	ln -sf $(SRC)/mtedit.py /usr/bin/mtedit
	ln -sf $(SRC)/mtreplay.py /usr/bin/mtreplay
	ln -sf $(SRC)/mtstat.py /usr/bin/mtstat
	ln -sf $(SRC)/mtbringup/main.py /usr/bin/mtbringup
	ln -sf $(SRC)/mtbringup/main_firmware.py /usr/bin/mtbringup-firmware
	ln -sf $(SRC)/mtbringup/main_xorg.py /usr/bin/mtbringup-xorg

clean-in-place:
	$(foreach dep, $(IN_PLACE_DEPS), OUT=. make -C $(dep) clean-in-place;)

in-place: export CXX = clang++
in-place:
	# can't use foreach loop here, otherwise make errors will be ignored.
	OUT=. make -C ../libevdev in-place
	OUT=. make -C ../gestures in-place
	OUT=. make -C mtreplay in-place
