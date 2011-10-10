PROG=scj
DESTDIR=/usr
VERSION=0.1

qtsox:
	echo "#!/bin/sh\ncd $(DESTDIR)/share/$(PROG) ; PYTHONIOENCODING='utf_8' python $(PROG).py; cd -\n" >$(PROG)
	chmod +x $(PROG)

all: qtsox

install: qtsox
	mkdir -p $(DESTDIR)/share/$(PROG)
	cp -a * $(DESTDIR)/share/$(PROG)
	ln -fs $(DESTDIR)/share/$(PROG)/$(PROG) $(DESTDIR)/bin

src:
	cp -r ../$(PROG) ../$(PROG)-$(VERSION)
	tar cvfz ../$(PROG)-$(VERSION).tar.gz -C .. $(PROG)-$(VERSION)
	rm -rf ../$(PROG)-$(VERSION)
