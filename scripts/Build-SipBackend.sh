#!/bin/sh
set -eu
archive=${1:?Pass the reviewed, scanned Asterisk 22.12.0 source archive path}
expected=f8b2ba98aac6c4ff3376bc0a2868bea6ed577ca684efb7ec739ae6e8ce6e35e2
build=/tmp/pat-asterisk-22.12.0-build
prefix=/opt/pat-codex-sip/asterisk-22.12.0
printf '%s  %s\n' "$expected" "$archive" | sha256sum -c -
mkdir -p "$build"
if [ ! -f "$build/asterisk-22.12.0/configure" ]; then
    tar -xzf "$archive" -C "$build"
fi
cd "$build/asterisk-22.12.0"
./configure --prefix="$prefix" --sysconfdir=/var/lib/pat-codex-sip/etc --localstatedir=/var/lib/pat-codex-sip/state --with-pjproject-bundled --without-dahdi --without-pri
make menuselect.makeopts
menuselect/menuselect --disable BUILD_NATIVE --disable-category MENUSELECT_ADDONS --disable-category MENUSELECT_CORE_SOUNDS --disable-category MENUSELECT_MOH --disable-category MENUSELECT_EXTRA_SOUNDS menuselect.makeopts
make -j4
make install
"$prefix/sbin/asterisk" -V
