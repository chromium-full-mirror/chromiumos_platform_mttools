# Copyright 2014 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
""" This module provides various tools for writing cros developer tools.

This includes tools for regular expressions, path processing, chromium os git
repositories, shell commands, and user interaction via command line.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import re
import shlex
import shutil
from six import string_types
import subprocess
import sys
import time

class Emerge(object):
  """Provides tools for emerging and deploying packages to chromebooks."""

  def __init__(self, board_variant):
    self.cmd = "emerge-{}".format(board_variant)

  def Emerge(self, package_name):
    SafeExecute([self.cmd, package_name], verbose=True)

  def Deploy(self, package_name, remote, emerge=True):
    if emerge:
      self.Emerge(package_name)
    SafeExecute(["cros", "deploy", remote.ip, package_name], verbose=True)


class RegexException(Exception):
  """Describes a regular expression failure."""
  def __init__(self, regex, string, match_type):
    Exception.__init__(self)
    self.regex = regex
    self.string = string
    self.match_type = match_type

  def __str__(self):
    capped = self.string
    if len(capped) > 256:
      capped = capped[1:251] + "[...]"
    msg = "RequiredRegex \"{}\" failed to {} on:\n{}\n"
    return msg.format(self.regex, self.match_type, capped)


class RequiredRegex(object):
  """Wrapper for regular expressions using exceptions.

  Most regular expression calls in mttools are used for parsing and any
  mismatches result in a program failure.
  To reduce the amount of error checking done in place this wrapper throws
  meaningful exceptions in case of mismatches.
  """
  cap_length = 30

  def __init__(self, pattern):
    self.pattern = pattern

  def Search(self, string, must_succeed=True):
    match = re.search(self.pattern, string)
    return self.__Check(match, string, must_succeed, "search")

  def Match(self, string, must_succeed=True):
    match = re.match(self.pattern, string)
    return self.__Check(match, string, must_succeed, "match")

  def __Check(self, match, string, must_succeed, match_type):
    if not match and must_succeed:
      raise RegexException(self.pattern, string, match_type)
    return match


class Path(object):
  """Wrapper for os.path functions enforcing absolute/real paths.

  This wrapper helps processing file paths by enforcing paths to be
  always absolute and with symlinks resolved. Being a class it also
  allows a more compact syntax for common operations.
  """
  def __init__(self, path, *args):
    if isinstance(path, Path):
      self.path = path.path
    else:
      self.path = os.path.abspath(path)

    for arg in args:
      self.path = os.path.join(self.path, str(arg))

  def ListDir(self):
    for entry in os.listdir(self.path):
      yield Path(self, entry)

  def Read(self):
    return open(self.path, "r").read()

  def Open(self, props):
    return open(self.path, props)

  def Write(self, value):
    self.Open("w").write(value)

  def Join(self, other):
    return Path(os.path.join(self.path, other))

  def CopyTo(self, target):
    shutil.copy(self.path, str(target))

  def MoveTo(self, target):
    target = Path(target)
    shutil.move(self.path, str(target))

  def RelPath(self, rel=os.curdir):
    return os.path.relpath(self.path, str(rel))

  def RmTree(self):
    return shutil.rmtree(self.path)

  def MakeDirs(self):
    if not self.exists:
      os.makedirs(self.path)

  @property
  def parent(self):
    return Path(os.path.dirname(self.path))

  @property
  def exists(self):
    return os.path.exists(self.path)

  @property
  def is_file(self):
    return os.path.isfile(self.path)

  @property
  def is_link(self):
    return os.path.islink(self.path)

  @property
  def is_dir(self):
    return os.path.isdir(self.path)

  @property
  def basename(self):
    return os.path.basename(self.path)

  def __eq__(self, other):
    return self.path == other.path

  def __ne__(self, other):
    return self.path != other.path

  def __div__(self, other):
    return self.Join(other)

  def __truediv__(self, other):
    return self.Join(other)

  def __bool__(self):
    return self.exists

  def __str__(self):
    return self.path


class ExecuteException(Exception):
  """Describes a failure to run a shell command."""
  def __init__(self, command, code, out, verbose=False):
    Exception.__init__(self)
    self.command = command
    self.code = code
    self.out = out
    self.verbose = verbose

  def __str__(self):
    string = "$ %s\n" % " ".join(self.command)
    if self.out:
      string = string + str(self.out) + "\n"
    string = string + "Command returned " + str(self.code)
    return string


def Execute(command, cwd=None, verbose=False, interactive=False,
            must_succeed=False):
  """Execute shell command.

  Returns false if the command failed (i.e. return code != 0), otherwise
  this command returns the stdout/stderr output of the command.
  The verbose flag will print the executed command.
  The interactive flag will not capture stdout/stderr, but allow direct
  interaction with the command.
  """
  if must_succeed:
    return SafeExecute(command, cwd, verbose, interactive)
  (code, out) = __Execute(command, cwd, verbose, interactive)
  if code != 0:
    return False
  return out


def SafeExecute(command, cwd=None, verbose=False, interactive=False):
  """Execute shell command and throw exception upon failure.

  This method behaves the same as Execute, but throws an ExecuteException
  if the command fails.
  """
  if isinstance(command, string_types):
    command = shlex.split(command)
  (code, out) = __Execute(command, cwd, verbose, interactive)
  if code != 0:
    raise ExecuteException(command, code, out, verbose)
  return out

def __Execute(command, cwd=None, verbose=False, interactive=False):
  if isinstance(command, string_types):
    command = shlex.split(command)

  if cwd:
    cwd = str(cwd)

  if verbose:
    print("$", " ".join(command))

  if interactive:
    process = subprocess.Popen(command, cwd=cwd)
  else:
    process = subprocess.Popen(command,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT,
                               cwd=cwd)
  if verbose and not interactive:
    # print a . approximately every second to show progress
    seconds = 0
    while process.poll() is None:
      seconds += 0.01
      time.sleep(0.01)
      if seconds > 1:
        seconds = seconds - 1
        sys.stdout.write(".")
        sys.stdout.flush()
    print("")
  else:
    process.wait()

  out = None
  if not interactive:
    out = process.stdout.read().decode('utf-8', 'strict')
    out = out.replace("\r", "").strip()

  return (process.returncode, out)

class GitRepo(object):
  """A helper class to work with Git repositories.

  This class is specialized to deal with chromium specific git workflows
  and uses the git command line program to interface with the repository.
  """
  def __init__(self, repo_path, verbose=False):
    self.path = Path(repo_path)
    self.verbose = verbose
    rel_path = self.path.RelPath("/mnt/host/source/src/")
    self.review_url = ("https://chrome-internal.googlesource.com/chromeos/" +
                       rel_path)

  def SafeExecute(self, command):
    if isinstance(command, str):
      command = "git " + command
    else:
      command = ["git"] + command
    return SafeExecute(command, cwd=self.path, verbose=self.verbose)

  def Execute(self, command):
    if isinstance(command, str):
      command = "git " + command
    else:
      command = ["git"] + command
    return Execute("git " + command, cwd=self.path, verbose=self.verbose)

  @property
  def active_branch(self):
    result = self.SafeExecute("branch")

    regex = "\\* (\\S+)"
    match = re.search(regex, result)
    if match:
      return match.group(1)
    return None

  @property
  def branches(self):
    branches = []
    result = self.SafeExecute("branch")
    regex = "(\\S+)$"
    for match in re.finditer(regex, result):
      branches.append(match.group(1))
    print("Branches:", branches)
    return branches

  @property
  def working_directory_dirty(self):
    result = self.SafeExecute("status")
    return "Changes not staged for commit" in result

  @property
  def index_dirty(self):
    result = self.SafeExecute("status")
    return "Changes to be committed" in result

  @property
  def diverged(self):
    result = self.SafeExecute("status")
    return "Your branch is ahead of" in result

  @property
  def remote(self):
    return self.SafeExecute("remote").strip()

  @property
  def status(self):
    status = []
    if self.index_dirty:
      status.append("changes in index")
    if self.diverged:
      status.append("diverged from main")
    if self.working_directory_dirty:
      status.append("local changes")
    if not status:
      status.append("clean")
    return ", ".join(status)

  def Move(self, source, destination):
    source = Path(source).RelPath(self.path)
    destination = Path(destination).RelPath(self.path)
    self.SafeExecute(["mv", source, destination])

  def DeleteBranch(self, branch_name):
    if branch_name not in self.branches:
      return
    self.SafeExecute("checkout -f m/main")
    self.SafeExecute("branch -D " + branch_name)

  def CreateBranch(self, branch_name, tracking=None):
    if tracking:
      self.SafeExecute("checkout -b " + branch_name + " " + tracking)
    else:
      self.SafeExecute("checkout -b " + branch_name)

  def Checkout(self, name, force=False):
    cmd = "checkout " + name
    if force:
      cmd = cmd + " -f"
    self.SafeExecute(cmd)

  def Stash(self):
    self.SafeExecute("stash")

  def Add(self, filepath):
    self.SafeExecute(["add", Path(filepath).RelPath(self.path)])

  def Commit(self, message, ammend=False, all_changes=False,
             ammend_if_diverged=False):
    cmd = "commit"
    if ammend or (ammend_if_diverged and self.diverged):
      existing = self.SafeExecute("log --format=%B -n 1")
      regex = "Change-Id: I[a-f0-9]+"
      match = re.search(regex, existing)
      if match:
        message = message + "\n" + match.group(0)
      cmd = cmd + " --amend"
    if all_changes:
      cmd = cmd + " -a"
    cmd = cmd + " -m \"" + message + "\""
    self.SafeExecute(cmd)

  def Upload(self):
    result = self.SafeExecute("push %s HEAD:refs/for/main" % self.remote)
    if "error" in result or "Error" in result:
      raise Exception("Failed to upload:\n{}".format(result))
    regex = "https://[a-zA-Z0-9\\-\\./]+"
    match = re.search(regex, result)
    if match:
      return match.group(0)
    return None

class AskUser(object):
  """Various static methods to ask for user input."""

  @staticmethod
  def Text(message=None, validate=None, default=None):
    """Ask user to input a text."""
    while True:
      if message:
        print(message)
      reply = sys.stdin.readline().strip()
      if len(reply) == 0:
        return default
      if validate:
        try:
          reply = validate(reply)
        except Exception as e:
          print(e)
          continue
      return reply

  @staticmethod
  def Continue():
    """Ask user to press enter to continue."""
    AskUser.Text("Press enter to continue.")

  @staticmethod
  def YesNo(message, default=False):
    """Ask user to reply with yes or no."""
    if default is True:
      print(message, "[Y/n]")
    else:
      print(message, "[y/N]")
    choice = sys.stdin.readline().strip()
    if choice in ("y", "Y", "Yes", "yes"):
      return True
    elif choice in ("n", "N", "No", "no"):
      return False
    return default

  @staticmethod
  def Select(choices, msg, allow_none=False):
    """Ask user to make a single choice from a list.

    Returns the index of the item selected by the user.

    allow_none allows the user to make an empty selection, which
    will return None.

    Note: Both None and the index 0 will evaluate to boolean False,
          check the value explicitly with "if selection is None".
    """
    selection = AskUser.__Select(choices, msg, False, allow_none)
    if len(selection) == 0:
      return None
    return selection[0]

  @staticmethod
  def SelectMulti(choices, msg, allow_none=False):
    """Ask user to make a multiple choice from a list.

    Returns the list of indices selected by the user.

    allow_none allows the user to make an empty selection, which
    will return an empty list.
    """
    return AskUser.__Select(choices, msg, True, allow_none)

  @staticmethod
  def __Select(choices, msg, allow_multi=False, allow_none=False):
    # skip selection if there is only one option
    if len(choices) == 1 and not allow_none:
      return [0]

    # repeat until user made a valid selection
    while True:
      # get user input (displays index + 1).
      print(msg)
      for i, item in enumerate(choices):
        print(" ", str(i + 1) + ":", item)
      if allow_multi:
        print("(Separate multiple selections with spaces)")
      if allow_none:
        print("(Press enter to select none)")

      sys.stdout.write('> ')
      sys.stdout.flush()
      selection = sys.stdin.readline()

      if len(selection.strip()) == 0 and allow_none:
        return []

      if allow_multi:
        selections = selection.split(" ")
      else:
        selections = [selection]

      # validates single input value
      def ProcessSelection(selection):
        try:
          idx = int(selection) - 1
          if idx < 0 or idx >= len(choices):
            print("Number out of range")
            return None
        except ValueError:
          print("Not a number")
          return None
        return idx

      # validate list of values
      selections = [ProcessSelection(s) for s in selections]
      if None not in selections:
        return selections
