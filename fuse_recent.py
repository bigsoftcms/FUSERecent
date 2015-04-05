#!/usr/bin/env python

from __future__ import with_statement

import os
import sys
import errno
import time

from fuse import FUSE, FuseOSError, Operations


class PassthroughFiltered(Operations):
    """
    Make a read-only alias of another directory, filtering entities by
    some criterion. Entities that are filtered out won't show up in the
    alias' listing, and will not be readable. You can, however, run `ls`
    on an unlisted filtered out entity itself, within the alias. I
    haven't figured out how to fix that, but it shouldn't be an issue
    for most things.

    The default case doesn't filter out anything. This should be
    subclassed, redefining `is_visible`.
    """

    def __init__(self, root):
        self.root = root

    def is_visible(self, path):
        """Should the file from the first directory show up in the second one?"""
        return True

    # Helpers
    # =======

    def _full_path(self, partial):
        if partial.startswith("/"):
            partial = partial[1:]
        path = os.path.join(self.root, partial)
        return path

    # Filesystem methods
    # ==================


    def getattr(self, path, fh=None):
        full_path = self._full_path(path)
        st = os.lstat(full_path)
        return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
                     'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))

    def readdir(self, path, fh):
        full_path = self._full_path(path)

        yield '.'
        yield '..'
        if os.path.isdir(full_path):
            for child in os.listdir(full_path):
                if self.is_visible(os.path.join(full_path, child)):
                    yield child

    def readlink(self, path):
        pathname = os.readlink(self._full_path(path))
        if pathname.startswith("/"):
            # Path name is absolute, sanitize it.
            return os.path.relpath(pathname, self.root)
        else:
            return pathname

    def statfs(self, path):
        full_path = self._full_path(path)
        stv = os.statvfs(full_path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))

    def utimens(self, path, times=None):
        return os.utime(self._full_path(path), times)

    # File methods
    # ============

    def open(self, path, flags):
        full_path = self._full_path(path)
        if not self.is_visible(full_path):
            raise FuseOSError(errno.ENOENT)
        return os.open(full_path, flags)

    def read(self, path, length, offset, fh):
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, length)

    def flush(self, path, fh):
        return os.fsync(fh)

    def release(self, path, fh):
        return os.close(fh)

class OnlyNew(PassthroughFiltered):
    """
    Only show items that are 2 weeks old or newer.
    """
    def is_visible(self, path):
        """Should the file from the first directory show up in the second one?"""
        st = os.lstat(path)
        minute = 60
        hour = minute * 60
        day = hour * 24
        week = day * 7
        return time.time() - st.st_ctime < week * 2

def main(mountpoint, root):
    FUSE(OnlyNew(root), mountpoint, foreground=True)

if __name__ == '__main__':
    main(sys.argv[2], sys.argv[1])
