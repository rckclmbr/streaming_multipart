#!/usr/bin/python

"""
A streaming multipart content reader.  Unlike every other multipart streaming library,
contents aren't cached to a file, or stored in memory.

https://github.com/rckclmbr/streaming_multipart
"""

from io import BufferedReader
from cgi import parse_header
from mimetypes import MimeTypes
from mimetools  import Message
from cStringIO import StringIO
import hashlib

__version__ = "1.0"

BLOCK_SIZE = 4096

def _new_part(mr):
    bp = Part(mr)
    bp.populate_headers()
    return bp

def skipLWSPChar(b):
    while len(b) > 0 and b[0] in [" ", "\t"]:
        b = b[1:]
    return b


class _Buff(object):
    # A simple read buffer

    def __init__(self, st=""):
        self.st = st
        self.buf = st

    def read(self, n=None):
        if n is None:
            ret = self.buf
            self.buf = ""
            return ret
        ret = buffer(self.buf, 0, n)
        self.buf = buffer(self.buf, n)
        return ret

    def __len__(self):
        return len(self.buf)


class _StreamWrapper(object):
    # So that file objects can use the BufferedReader

    def readable(self):
        return True

    @property
    def closed(self):
        return False

    def readinto(self, b):
        if hasattr(self._wrapped, "readinto"):
            return self._wrapped.readinto(b)

        size = len(b)
        # print "readinto", size
        buf = self._wrapped.read(size)
        if not buf:
            return
        if len(buf) == 0:
            return None
        for i, c in enumerate(buf):
            b[i] = c
        # print len(b.tobytes())
        return len(buf)

    def __init__(self, wrapped):
        self._wrapped = wrapped

    def __getattr__(self, n):
        # print n
        return getattr(self._wrapped, n)


class _PartReader(object):

    def __init__(self, p):
        self.p = p

    def read(self, d):
        """
        Reads the body of the part, up to and including length "d".
        """
        n = ""
        p = self.p
        try:
            # If the buffer contains the length of data we need, just return it
            if len(p.buf) >= d:
                #print "Buffer has size %d, just reading %d bytes" % (len(p.buf), d)
                return p.buf.read(d)
            #print "Peeking %s from BufferedReader" % BLOCK_SIZE
            peek = p.mr.buf_reader.peek(BLOCK_SIZE)
            #print "length of peek:", len(peek), hashlib.md5(peek).hexdigest()

            if p.bytes_read == 0 and p.mr.peek_buffer_is_empty_part(peek):
                return "" # EOF

            # * Search for the boundary.  If it exists, return all bytes up to
            #   the boundary.
            # * Only actually read up to bytes_in_buffer - sizeof(boundary),
            #   leaving a tail for the boundary check
            n_copy = 0
            found_boundary = False
            idx = peek.find(p.mr.nl_dash_boundary)
            safe_count = len(peek) - len(p.mr.nl_dash_boundary)

            if idx != -1:
                n_copy = idx
                found_boundary = True
            elif safe_count > 0:
                n_copy = safe_count
            elif idx == -1 and safe_count == 0:
                # When the data isn't a boundary, but has the same length as the
                # boundary, read more off the BufferedReader
                #print "Reading %d bytes from BufferedReader into buffer" % n_copy
                data = p.mr.buf_reader.read(len(peek))
                p.buf = _Buff(p.buf.read() + data)

            if n_copy > 0:
                #print "Reading %d bytes from BufferedReader into buffer" % n_copy
                data = p.mr.buf_reader.read(n_copy)
                p.buf = _Buff(p.buf.read() + data)

            #print "Reading %s bytes from buffer of size %s" % (d, len(p.buf))
            n = p.buf.read(d)
            return n
        finally:
            if n is not None:
                p.bytes_read += len(n)


class MultipartReader(object):
    """
    Reads a stream formatted as multipart/form-data.  Provides each part as a
    readable interface, avoiding loading the entire body into memory or
    caching to a file.

    Usage:

    reader = MultipartReader(f, boundary)
    part1 = reader.next_part()
    print part1.form_name()
    data = part1.read(1024)
    """

    def __init__(self, stream, boundary=None):
        b = "\r\n--" + boundary + "--"
        stream = _StreamWrapper(stream)

        self.buf_reader = BufferedReader(stream)
        self.nl = b[:2]
        self.nl_dash_boundary = b[:len(b)-2]
        self.dash_boundary_dash = b[2:]
        self.dash_boundary = b[2:len(b)-2]
        self.headers = {}
        self.parts_read = 0

        self.current_part = None

    def iter_parts(self):
        """
        Returns an iterator over the Parts in multipart/form-data.

        Do not use if you're skipping the end of the data, as the last
        iteration will seek to the end of the stream.
        """
        part = self.next_part()
        while part != None:
            yield part
            part = self.next_part()

    def next_part(self):
        """
        Returns the next Part in the stream.  If a previous part was not read
        completely, it will seek to the beginning of the next part, closing the
        previous one.
        """

        if self.current_part != None:
            self.current_part.close()

        expect_new_part = False
        while True:
            line = self.buf_reader.readline()
            is_EOF = self.buf_reader.peek(1)
            if len(is_EOF) == 0 and self.is_final_boundary(line):
                return None

            if self.is_boundary_delimeter_line(line):
                #print "Creating new part"
                self.parts_read += 1
                bp = _new_part(self)
                self.current_part = bp
                return bp

            if self.is_final_boundary(line):
                return None

            if expect_new_part:
                raise Exception("expecting a new Part, got line %s" % line)

            if self.parts_read == 0:
                continue

            if line == self.nl:
                expect_new_part = True
                continue

            raise Exception("Unexpected line in next_part(): %s" % line)

    def is_final_boundary(self, line):
        if not line.startswith(self.dash_boundary_dash):
            return False
        rest = line[len(self.dash_boundary_dash):]
        rest = skipLWSPChar(rest)
        return len(rest) == 0 or rest == self.nl

    def is_boundary_delimeter_line(self, line):
        if not line.startswith(self.dash_boundary):
            return False

        rest = line[len(self.dash_boundary):]
        rest = skipLWSPChar(rest)
        if self.parts_read == 0 and len(rest) == 1 and rest[0] == "\n":
            self.nl = self.nl[1:]
            self.nl_dash_boundary = self.nl_dash_boundary[1:]
        return rest == self.nl

    def peek_buffer_is_empty_part(self, peek):
        if peek.startswith(self.dash_boundary_dash):
            rest = peek[len(self.dash_boundary_dash):]
            rest = skipLWSPChar(rest)
            return rest.startswith(self.nl) or len(rest) == 0

        if not peek.startswith(self.dash_boundary):
            return False

        rest = peek[len(self.dash_boundary):]
        rest = skipLWSPChar(rest)
        return rest.startswith(self.nl)


class Part(object):
    """
    Represents a Part of a multipart/form-data.  This is never instantiated
    directly, but returned as part of the MultipartReader.next_part method.
    """

    def __init__(self, mr):
        self.buf = _Buff()          # Buffer
        self.mr = mr               # Reader
        self.r = _PartReader(self) # PartReader
        self.bytes_read = 0
        self.disposition = ""
        self.disposition_params = {}
        self.headers = {}
        self.closed = False

    def close(self):
        """ Flushes the stream to the end of the part, so the next one can be started """
        # Empty the stream, so the next part can be accessed
        while True:
            line = self.read(BLOCK_SIZE)
            if line == "":
                break
        self.closed = True

    def populate_headers(self):
        line = None
        while not line:
            line = self.mr.buf_reader.readline().strip()
        while line != "":
            self.headers.update(Message(StringIO(line)))
            line = self.mr.buf_reader.readline().strip()

    def form_name(self):
        """ Returns the name of the element, as used in a form"""
        if not self.disposition_params:
            self._parse_content_disposition()
        return self.disposition_params["name"]

    def file_name(self):
        """ If a file upload, returns the filename """
        if not self.disposition_params:
            self._parse_content_disposition()
        if "filename" in self.disposition_params:
            return self.disposition_params["filename"]

    def _parse_content_disposition(self):
        if "content-disposition" in self.headers:
            v = self.headers["content-disposition"]
            params = parse_header(v)
            key, values = params
            self.disposition_params.update(values)

    def read(self, d=None):
        """ Reads d bytes from the body of the part.  If the end, and empty string will be returned """
        if self.closed:
            raise IOError("Part already closed")
        if d is None:
            data = ""
            while True:
                d = str(self.r.read(BLOCK_SIZE))
                if len(d) == 0:
                    break
                data += str(d)
            return data
        else:
            return str(self.r.read(d))

    def readline(self):
        raise NotImplementedError()


if __name__ == "__main__":
    boundary = "----------------------------205472a3c0e0"
    f = open("test_post.http", "rb")

    reader = MultipartReader(f, boundary)
    with open("test.out", "wb") as outfile:
        for i in range(2):
            part = reader.next_part()
            print "name: " + part.form_name()
            if part.form_name() == "name":
                print "data: " + part.read(14)
            elif part.form_name() == "file":
                data = part.read(100)
                print data
