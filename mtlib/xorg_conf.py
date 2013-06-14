# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import re

class XorgInputClassParser(object):
  """ Parser for xorg input config files.

  This class is used to parse xorg config files for input class options.
  Only input class sections with a valid Identifier line are parsed.
  """

  def Parse(self, file=None, string=None):
    """ Parse xorg file and return dictionary of input classes.

    Provide either a filename or file-like object to the file parameters
    or a string containing the configuration to the string parameter.
    The return value is a dictionary of all InputClasses, with the
    Identifier as a key. The value is another dictionary containing
    all options set for this input class.
    """
    if file:
      if isinstance(file, basestring):
        return self._ParseString(open(file).read())
      elif hasattr(file, 'read'):
        return self._ParseString(file.read())
      else:
        raise ValueError
    elif string:
      return self._ParseString(string)
    else:
      raise ValueError

  def _ParseString(self, string):
    lines = string.splitlines()
    lines = map(lambda l: l.strip(), lines)

    section_regex = re.compile('Section\\s+\"([^\"]+)\"')
    id_regex = re.compile('Identifier\\s+\"([^\"]+)\"')
    option_regex = re.compile('Option\\s+\"([^\"]+)\"\\s+\"([^\"]+)\"')

    classes = {}
    current_options = None
    current_id = None

    for line in lines:
      if current_options is None:
        # Outside of sections
        section_match = section_regex.match(line)
        if section_match and section_match.group(1) == 'InputClass':
          current_options = {}
          continue
      else:
        # Inside of a section
        if line == 'EndSection':
          if current_id:
            # if class had an id, save in results
            classes[current_id] = current_options
          current_options = None
          continue

        # look for identifier line
        id_match = id_regex.match(line)
        if id_match:
          current_id = id_match.group(1)
          continue

        # store options in current_options
        option_match = option_regex.match(line)
        if option_match:
          key = option_match.group(1)
          value = option_match.group(2)
          current_options[key] = value
    return classes
