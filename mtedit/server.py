# Copyright 2013 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

try:
  from http.server import SimpleHTTPRequestHandler
except ImportError:
  from SimpleHTTPServer import SimpleHTTPRequestHandler
import os
try:
  import socketserver
except ImportError:
  import SocketServer as socketserver

# change into script in order to serve tpview files
script_dir = os.path.dirname(os.path.realpath(__file__))

class ServerData(object):
  def __init__(self, log):
    self.log = log
    self.loaded = False
    self.saved = False
    self.result = None

class MTEditHTTPRequestHandler(SimpleHTTPRequestHandler):
  """ Serves static files and dynamic pages for log file handling.

    /edit serving view.html
    /load/* serving the log file provided when starting the server
    /save/* for POST'ing trimmed log files

    The latter two are only to be used with AJAX commands from
    /edit
  """
  def respond(self, data, type='text/html'):
    # send text response to browser
    self.send_response(200)
    self.send_header('Content-type', type)
    self.end_headers()
    output_data = data.encode('utf-8') if isinstance(data, str) else data
    self.wfile.write(output_data)

  def end_headers(self):
    # Override end_headers for additional header to be sent with every response
    self.send_header('Cache-Control', 'max-age=0, must-revalidate')
    SimpleHTTPRequestHandler.end_headers(self)

  def do_GET(self):
    data = self.server.user_data

    if self.path.startswith('/load/'):
      self.respond(data.log, 'text/plain')
      data.loaded = True
    else:
      if self.path.startswith('/edit'):
        self.path = 'mtedit.html'
      self.path = 'extension/' + self.path
      SimpleHTTPRequestHandler.do_GET(self)

  def do_POST(self):
    data = self.server.user_data

    if self.path.startswith('/save/'):
      name = os.path.basename(self.path)
      # getallmatchingheaders would be great here, if it hadn't been broken for
      # over 10 years (https://bugs.python.org/issue5053).
      try:
          # Python 3 version
          length = int(self.headers.get_all('Content-Length')[0])
      except AttributeError:
          # Python 2.7 version
          length = int(self.headers.getheader('Content-Length'))
      data.result = self.rfile.read(length).decode('utf-8', 'strict')
      data.saved = True
      self.respond('Success')

  def translate_path(self, path):
    """ Translate url path to local path.

      Modified version of translate_path to use script_dir
      for looking up files instead of the local working dir.
    """
    path = SimpleHTTPRequestHandler.translate_path(self, path)
    if path.startswith(os.getcwd()):
      path = path.replace(os.getcwd(), script_dir, 1)
    return path

def View(port, log=None, persistent=False):
  """ Serve MTEdit viewing 'log'.

    The server will exit after serving MTEdit
    unless persistent is set to True.
  """
  data = ServerData(log)
  httpd = socketserver.TCPServer(('', port), MTEditHTTPRequestHandler)
  httpd.user_data = data

  while True:
    httpd.handle_request()
    if not persistent and data.loaded:
      return


def Edit(port, log=None):
  """ Serve MTEdit for editing 'log'.

    Blocks until the file has been trimmed
    and returns the trimmed log.
  """
  data = ServerData(log)
  httpd = socketserver.TCPServer(('', port), MTEditHTTPRequestHandler)
  httpd.user_data = data

  while True:
    httpd.handle_request()
    if data.saved:
      return data.result


def Serve(port):
  """ Serve MTEdit without any log data.

    The server will serve until killed
    externally (e.g. via keyboard interrupt).
  """
  data = ServerData('')
  httpd = socketserver.TCPServer(('', port), MTEditHTTPRequestHandler)
  httpd.user_data = data
  while True:
    httpd.handle_request()
