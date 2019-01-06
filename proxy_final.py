#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    proxy.py
    ~~~~~~~~

    HTTP Proxy Server in Python.

    :copyright: (c) 2013 by Abhinav Singh.
    :license: BSD, see LICENSE for more details.
"""
import sys
import datetime
import argparse
import logging
import socket
import select
import threading
import errno
import urlparse
logger = logging.getLogger(__name__)
buffer = dict()
f = open("cache.txt",'w')

CRLF, COLON, SPACE = b'\r\n', b':', b' '

HTTP_REQUEST_PARSER = 1
HTTP_RESPONSE_PARSER = 2

HTTP_PARSER_STATE_INITIALIZED = 1
HTTP_PARSER_STATE_HEADERS_COMPLETE = 2
HTTP_PARSER_STATE_RCVING_BODY = 3
HTTP_PARSER_STATE_COMPLETE = 4

CHUNK_PARSER_STATE_WAITING_FOR_SIZE = 1
CHUNK_PARSER_STATE_WAITING_FOR_DATA = 2
CHUNK_PARSER_STATE_COMPLETE = 3

class HttpParser(object):
    """HTTP request/response parser."""

    def __init__(self, typ=None):
        self.state = HTTP_PARSER_STATE_INITIALIZED
        self.type = typ if typ else HTTP_REQUEST_PARSER
        self.chunk_state = CHUNK_PARSER_STATE_WAITING_FOR_SIZE
        self.raw = b''
        self.buffer = b''
        self.chunk = b''
        self.size = None
        self.headers = dict()
        self.body = None
        self.flag = False
        self.method = None
        self.url = None
        self.code = None
        self.reason = None
        self.version = None

        self.chunk_parser = False

    def chunk_parse(self, data):
        more = True if len(data) > 0 else False
        while more: more, data = self.chunk_process(data)

    def chunk_process(self, data):
        if self.chunk_state == CHUNK_PARSER_STATE_WAITING_FOR_SIZE:
            line, data = HttpParser.split(data)
            self.size = int(line, 16)
            self.chunk_state = CHUNK_PARSER_STATE_WAITING_FOR_DATA
        elif self.chunk_state == CHUNK_PARSER_STATE_WAITING_FOR_DATA:
            remaining = self.size - len(self.chunk)
            self.chunk += data[:remaining]
            data = data[remaining:]
            if len(self.chunk) == self.size:
                data = data[len(CRLF):]
                self.body += self.chunk
                if self.size == 0:
                    self.chunk_state = CHUNK_PARSER_STATE_COMPLETE
                else:
                    self.chunk_state = CHUNK_PARSER_STATE_WAITING_FOR_SIZE
                self.chunk = b''
                self.size = None
        return len(data) > 0, data

    def parse(self, data):
        self.raw += data
        data = self.buffer + data
        self.buffer = b''

        more = True if len(data) > 0 else False
        while more:
            more, data = self.process(data)
        self.buffer = data

    def process(self, data):
        if self.state >= HTTP_PARSER_STATE_HEADERS_COMPLETE and \
                (self.method == b'POST' or self.type == HTTP_RESPONSE_PARSER):
            if not self.body:
                self.body = b''

            if b'content-length' in self.headers:
                self.state = HTTP_PARSER_STATE_RCVING_BODY
                self.body += data
                if len(self.body) >= int(self.headers[b'content-length'][1]):
                    self.state = HTTP_PARSER_STATE_COMPLETE
            elif b'transfer-encoding' in self.headers and self.headers[b'transfer-encoding'][1].lower() == b'chunked':
                if not self.chunk_parser:
                    self.chunk_parser = True
                self.chunk_parse(data)
                if self.chunk_state == CHUNK_PARSER_STATE_COMPLETE:
                    self.state = HTTP_PARSER_STATE_COMPLETE

            return False, b''

        line, data = HttpParser.split(data)
        if line is False:
            return line, data

        if self.state < HTTP_PARSER_STATE_HEADERS_COMPLETE:
            self.process_line_and_header(line)
        if self.state == HTTP_PARSER_STATE_HEADERS_COMPLETE and \
                self.type == HTTP_REQUEST_PARSER and \
                not self.method == b'POST' and \
                self.raw.endswith(CRLF * 2):
            self.state = HTTP_PARSER_STATE_COMPLETE

        return len(data) > 0, data
    def process_line_and_header(self,data):
        if self.flag == False:
            line = data.split(SPACE)
            if self.type == HTTP_REQUEST_PARSER:
                self.method = line[0].upper()
                self.url = urlparse.urlsplit(line[1])
                self.version = line[2]
            else:
                self.version = line[0]
                self.code = line[1]
                self.reason = b' '.join(line[2:])
            self.flag = True
        elif self.flag:
            if len(data) == 0:
                self.state = HTTP_PARSER_STATE_HEADERS_COMPLETE
            else:
                parts = data.split(COLON)
                key = parts[0].strip()
                value = COLON.join(parts[1:]).strip()
                self.headers[key.lower()] = (key, value)
    def build_url(self):
        if not self.url:
            return b'/None'

        url = self.url.path
        if url == b'':
            url = b'/'
        if not self.url.query == b'':
            url += b'?' + self.url.query
        if not self.url.fragment == b'':
            url += b'#' + self.url.fragment
        return url

    def build(self, del_headers=None, add_headers=None):
        req = b' '.join([self.method, self.build_url(), self.version])
        req += CRLF

        if not del_headers:
            del_headers = []
        for k in self.headers:
            if k not in del_headers:
                req += self.build_header(self.headers[k][0], self.headers[k][1])

        if not add_headers:
            add_headers = []
        for k in add_headers:
            req += self.build_header(k[0], k[1])

        req += CRLF
        if self.body:
            req += self.body

        return req

    @staticmethod
    def build_header(k, v):
        return k + b': ' + v + CRLF

    @staticmethod
    def split(data):
        pos = data.find(CRLF)
        if pos == -1:
            return False, data
        line = data[:pos]
        data = data[pos + len(CRLF):]
        return line, data


class Connection(object):
    """TCP server/client connection abstraction."""

    def __init__(self,  host, port, what):
        self.what = what  # server or client
        self.conn = None
        self.buffer = b''
        self.closed = False
        self.addr=b''
        if self.what == b'server':
            self.addr = (host, int(port))
        else:
            self.conn = host
            self.addr = port


    def send(self, data):
        return self.conn.send(data)

    def recv(self, b=8192):
        data = self.conn.recv(b)
        if len(data) == 0:
            return None
        return data


    def close(self):
        self.conn.close()
        self.closed = True

    def buffer_size(self):
        return len(self.buffer)

    def has_buffer(self):
        return self.buffer_size() > 0

    def queue(self, data):
        self.buffer += data

    def flush(self):
        sent = self.send(self.buffer)
        self.buffer = self.buffer[sent:]

    def connect(self):
        self.conn = socket.create_connection((self.addr[0], self.addr[1]))

class ProxyError(Exception):
    pass


class ProxyConnectionFailed(ProxyError):

    def __init__(self, host, port, reason):
        self.host = host
        self.port = port
        self.reason = reason

    def __str__(self):
        return '<ProxyConnectionFailed - %s:%s - %s>' % (self.host, self.port, self.reason)


class Proxy(threading.Thread):
    """HTTP proxy implementation.
    
    Accepts connection object and act as a proxy between client and server.
    """

    def __init__(self, client):
        super(Proxy, self).__init__()
        self.first_time=True
        self.Read=False
        self.start_time = self._now()
        self.last_activity = self.start_time

        self.client = client
        self.server = None

        self.request = HttpParser()
        self.response = HttpParser(HTTP_RESPONSE_PARSER)

        self.connection_established_pkt = CRLF.join([
            b'HTTP/1.1 200 Connection established',
            b'Proxy-agent: proxy.py',
            CRLF
        ])

    @staticmethod
    def _now():
        return datetime.datetime.utcnow()

    def _process_request(self, data):
        # once we have connection to the server
        # we don't parse the http request packets
        # any further, instead just pipe incoming
        # data from client to server

        if self.server and not self.server.closed:
            self.server.queue(data)
            return
        # parse http request
        self.request.parse(data)
        # once http request parser has reached the state complete
        # we attempt to establish connection to destination server
        if self.request.state == HTTP_PARSER_STATE_COMPLETE:
            if self.request.method == b'CONNECT':
                host, port = self.request.url.path.split(COLON)
                #self.server = Server(host, port)
                self.server = Connection(host,port,b'server')
                try:
                    self.server.connect()
                except Exception as e:
                    self.server.closed = True
                self.client.queue(self.connection_established_pkt)
            else:
                host, port = self.request.url.hostname, self.request.url.port if self.request.url.port else 80
                #self.server = Server(host, port)
                self.server = Connection(host,port,b'server')
                try:
                    self.server.connect()
                except Exception as e:
                    self.server.closed = True
                self.server.queue(self.request.build(
                    del_headers=[b'proxy-connection', b'connection', b'keep-alive'],
                    add_headers=[(b'Connection', b'Close')]
                ))
        return


    def _process_response(self, data,flag):
        # parse incoming response packet
        # only for non-https requests
        if not self.request.method == b'CONNECT':
            self.response.parse(data)
        # queue data for client
        self.client.queue(data)

        if not flag:
            if self.request.build_url()+str(self.server.addr) not in buffer and self.request.method != b'CONNECT':
                print("creating buffer")
                print("a:", self.request.build_url()+str(self.server.addr))
                buffer[self.request.build_url()+str(self.server.addr)] = data
            elif self.request.build_url()+str(self.server.addr) in buffer and self.request.method != b'CONNECT':
                print("adding buffer")
                print("a:", self.request.build_url()+str(self.server.addr))
                buffer[self.request.build_url()+str(self.server.addr)] += data

    def _get_waitable_lists(self):
        rlist, wlist, xlist = [self.client.conn], [], []

        if self.client.has_buffer():
            wlist.append(self.client.conn)

        if self.server and not self.server.closed:
            rlist.append(self.server.conn)

        if self.server and not self.server.closed and self.server.has_buffer():
            wlist.append(self.server.conn)

        return rlist, wlist, xlist

    def _process_wlist(self, w):
        if self.client.conn in w:
            self.client.flush()

        if self.server and not self.server.closed and self.server.conn in w:
            self.server.flush()

    def _process_rlist(self, r):
        if self.client.conn in r:
            data = self.client.recv()
            self.last_activity = self._now()

            if not data:
                return True

            try:
                self._process_request(data)
            except ProxyConnectionFailed as e:
                logger.exception(e)
                self.client.queue(CRLF.join([
                    b'HTTP/1.1 502 Bad Gateway',
                    b'Proxy-agent: proxy.py',
                    b'Content-Length: 11',
                    b'Connection: close',
                    CRLF
                ]) + b'Bad Gateway')
                self.client.flush()
                return True
        if self.first_time:
            self.first_time = False
            if self.request.build_url() + str(self.server.addr) in buffer and self.request.method != b'CONNECT':
                print("using buffer:", self.request.build_url() + str(self.server.addr))
                self.Read = True
                data = buffer[self.request.build_url() + str(self.server.addr)]
                flag = True
                self._process_response(data, flag)
                self.server.close()
                return False
        else:
            if self.Read:
                if self.request.build_url() + str(self.server.addr) in buffer and self.request.method != b'CONNECT':
                    print("using buffer:", self.request.build_url() + str(self.server.addr))
                    data = buffer[self.request.build_url() + str(self.server.addr)]
                    flag = True
                    self._process_response(data, flag)
                    self.server.close()
                    return False
            else:
                print('not read at first time so don''t use buffer')
                '''if self.request.build_url() + str(self.server.addr) in buffer:
                    print('but ', self.request.build_url() + str(self.server.addr), ' in buffer')
                else:
                    print('and ', self.request.build_url() + str(self.server.addr), ' not in buffer')'''
        if self.server and not self.server.closed and self.server.conn in r:
            data = self.server.recv()
            self.last_activity = self._now()
            flag = False
            if not data:
                self.server.close()
            else:
                self._process_response(data,flag)

        return False

    def _process(self):
        while True:
            rlist, wlist, xlist = self._get_waitable_lists()
            r, w, x = select.select(rlist, wlist, xlist, 1)

            self._process_wlist(w)
            if self._process_rlist(r):
                break

            if self.client.buffer_size() == 0:
                if self.response.state == HTTP_PARSER_STATE_COMPLETE:
                    break

                if (self._now() - self.last_activity).seconds > 35:
                    break

    def run(self):
        self._process()
        self.client.close()


class Handshake(object):
    """TCP server implementation."""

    def __init__(self, hostname='127.0.0.1', port=8899, backlog=100):
        self.hostname = hostname
        self.port = port
        self.backlog = backlog
        self.socket = None

    def handle(self, client):
        proc = Proxy(client)
        proc.daemon = True
        proc.start()

    def run(self):
        logger.info('Starting server on port %d' % self.port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.hostname, self.port))
        self.socket.listen(self.backlog)
        while True:
            conn, addr = self.socket.accept()
            # client = Client(conn, addr)
            client = Connection(conn, addr, b'client')
            self.handle(client)
        logger.info('Closing server socket')
        self.socket.close()


def main():
    parser = argparse.ArgumentParser(
        description='proxy.py'
    )

    parser.add_argument('--hostname', default='127.0.0.1', help='Default: 127.0.0.1')
    parser.add_argument('--port', default='8899', help='Default: 8899')
    parser.add_argument('--log-level', default='INFO', help='DEBUG, INFO, WARNING, ERROR, CRITICAL')
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level),
                        format='%(asctime)s - %(levelname)s - pid:%(process)d - %(message)s')

    hostname = args.hostname
    port = int(args.port)
    proxy = Handshake(hostname, port)
    proxy.run()


if __name__ == '__main__':
    main()
