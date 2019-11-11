#!/usr/bin/env python

import SimpleHTTPServer
import SocketServer


def main(port, directory):
    Handler = SimpleHTTPServer.SimpleHTTPRequestHandler

    httpd = SocketServer.TCPServer(("", port), Handler)

    print "serving at port", PORT
    httpd.serve_forever()


if __name__ == '__main__':
    main(8080, '.')
