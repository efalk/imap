#!/usr/bin/python
# -*- coding: utf8 -*-

usage = """Command-line imap access

Usage:  imap [options] command [arguments]

    options:

	-v		verbose
	-q		quiet
	-l		long form
	-n		show what would be done without actually doing it
	-u username	user[@host[:port]]
	-h hostname
	-p port		(default is 143 or 993)
	-s		ssl/tls
	-a authtype	'plain' or 'md5'
	-d dir		local mail directory; fetch and put commands
	-D		delete remote mailboxes before writing
	-f		force; upload mail to non-empty mailboxes
	-P pfx		mailbox prefix; used with upload command
	-t timeout	set timeout value in seconds
	-w seconds	set time interval between queries
	-x pat		exclude mailboxes matching pattern
	-I file		file contains a list of mailbox patterns, 1 per line
	-X file		file contains a list of patterns to exclude
	--pw paswd	password on command line (not recommended)

	--help		this list

	username may be expressed as name[@host[:port]]. The -h and -p
	options override host and port. If the username has an '@' in it, you
	could use e.g. "-u user@example.com@mail.example.com" or
	"-u user@example.com -h mail.example.com"

	patterns are shell-style glob patterns

    commands:

	probe <user@host>	Guess imap server
	listboxes		List user mailboxes
	list [mailboxes]	List messages in given mailbox(es); default is INBOX
	download [mailboxes]	Download emails; -d option required; default is all mailboxes
	upload mailboxes	Upload emails; -d option required

    examples:
      Figure out where your imap server is:
	imap.py -v probe user@example.com

      See what mailboxes are on your account:
	imap.py -u user@mail.example.com:993 listboxes

      List messages in a mailbox:
	imap.py -u user@mail.example.com:993 list vacation

      Download messages from a mailbox:
	imap.py -u user@mail.example.com:993 -d ./LocalMail download vacation

      Download messages from all mailboxes:
	imap.py -u user@mail.example.com:993 -d ./LocalMail download

      Upload mailbox
	imap.py -u user@mail.example.com:993 -d ./LocalMail upload vacation

Exit codes:

	0 - successful return
	0 - search failed
	2 - user error
	3 - unable to connect to host
	4 - unable to log in
	5 - internal error

"""

import sys
import os
import getopt
import string
import signal
import socket
import time
import imaplib
import email.parser
import getpass
import re
import types
import fnmatch
import ast

# Numeric flag values. Most important flags have higher values
MBOX_MARKED = 0x1
MBOX_UNMARKED = 0x2
MBOX_NO_INFERIORS = 0x4
MBOX_CHILDREN = 0x8
MBOX_NO_CHILDREN = 0x10
MBOX_NO_SELECT = 0x20
MBOX_FLAGGED = 0x100
MBOX_TRASH = 0x200
MBOX_SENT = 0x400
MBOX_JUNK = 0x1000
MBOX_DRAFTS = 0x2000
MBOX_ARCHIVE = 0x4000
MBOX_ALL = 0x8000

verbose = 0
quiet = False
host = None
port = None
ssltls = None
authtype = None
user = None
passwd = None
timeout = None
longform = False
waitTime = 0.0
mailDir = None
notreally = False
prefix = ''
deleteFirst = False
force = False
includes = []
excludes = []

class Mbox(object):
  """This object represents one mailbox. Its constructor accepts
  one server response line from the 'list' command."""
  def __init__(self):
    self.flags = 0
    self.flaglist = []
    self.separator = ''
    self.name = ''

  def __init__(self, srvResp):
    '''Initialize an mbox object from a LIST server response.'''
    resp = parseList(srvResp)
    self.flaglist = resp[0]
    self.separator = resp[1]
    self.name = resp[2]
    self.flags = self.mboxFlags()

  def mboxFlags(self):
    flaglist = self.flaglist
    oflags = 0
    for flag in flaglist:
      flag = flag.lower()
      if flag in flagMap:
	oflags |= flagMap[flag]
    return oflags

  def FlagLetters(self):
    # Flags:
    #  d children
    #  C no children
    #   * Marked
    #    u unmarked
    #     - No inferiors
    #     A All
    #     a archive
    #     d drafts
    #     j junk
    #     s sent
    #     t trash
    #      f flagged
    #       n no select
    flags = self.flags
    oflags = list('------')
    for m in letterMap:
      if flags & m[0]:
	oflags[m[1]] = m[2]
    return ''.join(oflags)

  def __str__(self):
    return self.name

  def __repr__(self):
    return '<Mbox %s>' % self.name

  MBOX_MASK = MBOX_FLAGGED | MBOX_TRASH | MBOX_SENT | MBOX_JUNK | \
    MBOX_DRAFTS | MBOX_ARCHIVE | MBOX_ALL

  def __lt__(self, other):
    sf = self.flags & Mbox.MBOX_MASK
    of = other.flags & Mbox.MBOX_MASK
    if sf != of: return sf > of
    ss = specialName(self.name)
    os = specialName(other.name)
    if ss != os: return ss > os
    return self.name < other.name
  def __gt__(self, other):
    return other<self
  def __ge__(self, other):
    return not self<other
  def __le__(self, other):
    return not other<self
  def __eq__(self, other):
    sf = self.flags & Mbox.MBOX_MASK
    of = other.flags & Mbox.MBOX_MASK
    if sf != of: False
    ss = self._specialName()
    os = other._specialName()
    if ss != os: False
    return self.name != other.name
  def __ne__(self, other):
    return not self == other




def main():
  global host, port, ssltls, authtype, user, passwd, timeout, notreally
  global quiet, verbose, longform, waitTime, mailDir, prefix, deleteFirst
  global force
  global includes, excludes

  try:
    (optlist, args) = getopt.gnu_getopt(sys.argv[1:],
	'vqlnfh:p:sa:u:t:w:d:DP:x:I:X:', ['help','pw='])
    for flag, value in optlist:
      if flag == '-v': verbose += 1
      elif flag == '-q': quiet = True
      elif flag == '-l': longform = True
      elif flag == '-n': notreally = True
      elif flag == '-h': host = value
      elif flag == '-p': port = int(value)
      elif flag == '-s': ssltls = True
      elif flag == '-a': authtype = value
      elif flag == '-u': user = value
      elif flag == '-t': timeout = float(value)
      elif flag == '-w': waitTime = float(value)
      elif flag == '-d': mailDir = value
      elif flag == '-D': deleteFirst = True
      elif flag == '-f': force = True
      elif flag == '-P': prefix = value
      elif flag == '-x': excludes.append(value)
      elif flag == '-I': includes.extend(readpats(value))
      elif flag == '-X': excludes.extend(readpats(value))
      elif flag == '--help':
	print usage
	return 0
      elif flag == '--pw': passwd = value
    if not args:
      print >>sys.stderr, 'Missing command'
      print >>sys.stderr, usage
      return 2
  except getopt.GetoptError as e:
    print >>sys.stderr, e
    print >>sys.stderr, "--help for more info"
    return 2
  except ValueError as e:
    print >>sys.stderr, e
    print >>sys.stderr, "--help for more info"
    return 2

  # If host was not specified, try to parse it from user
  if user and not host:
    user,host,port = parseEmail(user, user,host,port)

  if args[0] == 'probe':
    return doProbe(args)
  elif args[0] == 'listboxes':
    return doListBoxes(args)
  elif args[0] == 'list':
    return doList(args)
  elif args[0] == 'download':
    return doDownload(args)
  elif args[0] == 'upload':
    return doUpload(args)
  else:
    print >>sys.stderr, "Command '%s' not recognized" % args[0]
    print >>sys.stderr, usage
    return 2


def doProbe(args):
  global verbose, host, port, ssltls, authtype, user, passwd, timeout

  foundHost = None
  foundPort = None
  foundSsl = None
  foundSrvr = None

  if len(args) < 2:
    print >>sys.stderr, "Email address required"
    print >>sys.stderr, "--help for more info"
    return 2

  emailAddr = args[1]
  hhost = host
  user,h,p = parseEmail(emailAddr, user,host,port)
  if not host: host = h
  if not port: port = p

  if not timeout: timeout = 10
  socket.setdefaulttimeout(timeout)

  if hhost:
    h = hhost
    pfxs = ('',)
  else:
    h = host
    pfxs = ('mail.', 'imap.', 'imap4.', '', 'pop.')

  ss = (True,) if ssltls else (True, False)

  print 'Probing %d host/security connections, this can take up to %.0f seconds' \
    % (len(pfxs)*len(ss), len(pfxs)*len(ss)*timeout)

  for pfx in pfxs:
    for s in ss:
      testhost = pfx + h
      p = port
      if not p:
	p = 993 if s else 143
      if verbose:
	print 'Trying %s:%d, %sssl ...' % (testhost, p, '' if s else 'no '),
	sys.stdout.flush()
      try:
	if s:
	  srvr = imaplib.IMAP4_SSL(testhost, p)
	else:
	  srvr = imaplib.IMAP4(testhost, p)
      except socket.error:
	if verbose: print 'failed to connect'
	srvr = None
      if srvr:
	if verbose: print 'success'
	if not foundHost:
	  foundHost = testhost
	  foundPort = p
	  foundSsl = s
	  foundSrvr = srvr
	  if not verbose:
	    break

  if not foundHost:
    print 'Unable to find a connection for', emailAddr
    return 1

  print 'Success: host = %s, port = %d, ssl/tls = %s' % (foundHost, foundPort, foundSsl)

  if verbose:
    print 'Server capabilities:'
    for cap in foundSrvr.capabilities:
      print ' ', cap

  return 0


def doListBoxes(args):
  global host, port, ssltls, authtype, user, passwd, timeout, waitTime
  global verbose, longform

  if len(args) > 1:
    parseEmailAndDefaults(args[1])

  if not user:
    print >>sys.stderr, 'User (-u) required'
    print >>sys.stderr, usage
    return 2
  if not passwd:
    passwd = getpass.getpass()

  srvr = srvConnect(host, port, ssltls)
  if not srvr: return 3

  if not srvLogin(srvr, user, passwd):
    return 4

  if verbose:
    print 'Fetch mailbox list, this may take a while ...'
  mailboxes = getMailboxes(srvr)
  if mailboxes:
    if longform:
      print 'd - has children, C=no children'
      print ' * - Marked'
      print '  u - Unmarked'
      print '   A - A=All, a=archive, d=drafts, j=junk, s=sent, t=trash'
      print '    f - flagged'
      print '     n - not selectable'
    for mbox in mailboxes:
      if longform:
	print mbox.FlagLetters(), mbox.name
      else:
	print mbox.name
  else:
    print >>sys.stderr, "Mailbox LIST request fails"

  return 0


def doList(args):
  r'''The "list" command.'''
  global host, port, ssltls, authtype, user, passwd, timeout
  global verbose, longform, waitTime
  global includes, excludes

  args.pop(0)
  if len(args) > 0 and '@' in args[0]:
    parseEmailAndDefaults(args[0])
    args.pop(0)

  if not user:
    print >>sys.stderr, 'User (-u) required'
    print >>sys.stderr, usage
    return 2
  if not passwd:
    passwd = getpass.getpass()

  srvr = srvConnect(host, port, ssltls)
  if not srvr: return 3

  if not srvLogin(srvr, user, passwd):
    return 4

  mailboxes = getMailboxes(srvr)
  if not mailboxes:
    print >>sys.stderr, "Unable to read mailbox list from server"
    return 5

  if not args: args = ['INBOX']
  for name in includes + args:
    for mbox in matchBoxes(name, mailboxes, excludes):
      messages = getMailboxHeaders(srvr, mbox, True)
      if messages:
	for msg in messages:
	  headers = email.message_from_string(msg['RFC822.HEADER'])
	  if longform:
	    print '\nMessage %s:' % msg['UID']
	    print headers
	  else:
	    print '%8s  %-40.40s  %-40.40s  %-40.40s' % \
	      (msg['UID'], headers['subject'],
	       headers['from'], headers['date'])

  return 0

def getMailboxHeaders(srvr, mbox, listInfo):
  '''Fetch all the RFC822 headers from the named mailbox.'''
  global verbose, longform, waitTime
  if verbose:
    print 'Fetch message list from %s, this may take a while ...' % mbox
  resp = srvr.select(mbox, True)
  if resp[0] == 'OK':
    nmesg = int(resp[1][0])
    if listInfo:
      print
      print '%s: %s messages' % (mbox, nmesg)
    if nmesg == 0:
      return None
    else:
      try:
	resp = srvr.fetch('1:*', "(UID RFC822.HEADER)")
	return parseFetch(resp)
      except imaplib.IMAP4.error as e:
	print >>sys.stderr, 'Failed to fetch messages from %s: %s' % \
	  (mbox, e)
	return None


def doDownload(args):
  r'''The "download" command.'''
  global host, port, ssltls, authtype, user, passwd, timeout
  global verbose, longform, waitTime, mailDir, notreally
  global includes, excludes

  if not mailDir:
    print >>sys.stderr, 'The "download" command requires the -d option'
    print >>sys.stderr, 'Use --help for more information.'
    return 2
  if not os.path.isdir(mailDir):
    print >>sys.stderr, '%s is not a directory' % mailDir
    print >>sys.stderr, 'Use --help for more information.'
    return 2

  args.pop(0)
  if len(args) > 0 and '@' in args[0]:
    parseEmailAndDefaults(args[0])
    args.pop(0)

  if not user:
    print >>sys.stderr, 'User (-u) required'
    print >>sys.stderr, 'Use --help for more information.'
    return 2
  if not passwd:
    passwd = getpass.getpass()

  srvr = srvConnect(host, port, ssltls)
  if not srvr: return 3

  if not srvLogin(srvr, user, passwd):
    return 4

  mailboxes = getMailboxes(srvr)
  if not mailboxes:
    print >>sys.stderr, "Unable to read mailbox list from server"
    return 5

  if not args: args = map(lambda m: m.name, mailboxes)
  # For all names on command line:
  for name in includes + args:
    # For all matching mboxes:
    for mbox in matchBoxes(name, mailboxes, excludes):
      mboxDir = os.path.join(mailDir, mbox.name)
      if not os.path.isdir(mboxDir):
	os.makedirs(mboxDir)
      resp = srvr.select(str(mbox), True)
      if resp[0] == 'OK':
	nmesg = int(resp[1][0])
	print '%s: %s messages' % (mbox, nmesg)
	if nmesg > 0:
	  try:
	    metadataName = os.path.join(mboxDir, 'metadata')
	    needHeader = not os.path.exists(metadataName)
	    if not notreally:
	      with open(metadataName, "a") as metadata:
		if needHeader:
		  print >>metadata, '# msgno  UID  msgid  FLAGS'
		pct0 = 0
		t0 = time.time()
		for idx in xrange(1,nmesg+1):
		  downloadOne(srvr, mbox, idx, mboxDir, metadata)
		  if verbose == 1:
		    pct = idx * 100 // nmesg
		    t = time.time()
		    if pct != pct0 or t > t0+1:
		      sys.stdout.write('\r%d/%d %d%% ' % (idx, nmesg, pct))
		      sys.stdout.flush()
		      pct0 = pct
		      t0 = t
		print
	  except imaplib.IMAP4.error as e:
	    print >>sys.stderr, 'Failed to fetch messages from %s: %s' % \
	      (mbox, e)

  return 0


def downloadOne(srvr, mbox, msgno, mboxDir, metadata):
  '''Download one message to this location.'''
  global host, port, ssltls, authtype, user, passwd, timeout
  global verbose, longform, waitTime
  resp = srvr.fetch(msgno, "(UID RFC822.SIZE)")
  messages = parseFetch(resp)
  if messages:
    msg = messages[0]
    msgFilename = os.path.join(mboxDir, 'u%d' % msg['UID'])
    if quickCheck(msgFilename, msg):
      if waitTime > 0.0:
	time.sleep(waitTime)
      if verbose >= 2:
	print 'Download message %d, %d bytes' % (msg['UID'], msg['RFC822.SIZE'])
      resp = srvr.fetch(msgno, "(FLAGS RFC822)")
      messages = parseFetch(resp)
      msg2 = messages[0]
      parser = email.parser.Parser()
      headers = parser.parsestr(msg2['RFC822'], True)
      print >>metadata, '%d	%d	%s	%s' % \
	(msgno, msg['UID'], headers['Message-Id'], msg2['FLAGS'])
      with open(msgFilename, "w") as ofile:
	ofile.write(msg2['RFC822'])


def quickCheck(msgFilename, msg):
  '''Return True if we need to download this message.'''
  return not os.path.exists(msgFilename) or \
       os.path.getsize(msgFilename) != msg['RFC822.SIZE']


def doUpload(args):
  r'''The "download" command.'''
  global host, port, ssltls, authtype, user, passwd, timeout
  global verbose, longform, waitTime, mailDir, prefix, notreally
  global deleteFirst, force
  global includes, excludes

  if not mailDir:
    print >>sys.stderr, 'The "download" command requires the -d option'
    print >>sys.stderr, 'Use --help for more information.'
    return 2
  if not os.path.isdir(mailDir):
    print >>sys.stderr, '%s is not a directory' % mailDir
    print >>sys.stderr, 'Use --help for more information.'
    return 2

  args.pop(0)
  if len(args) > 0 and '@' in args[0]:
    parseEmailAndDefaults(args[0])
    args.pop(0)

  if not user:
    print >>sys.stderr, 'User (-u) required'
    print >>sys.stderr, 'Use --help for more information.'
    return 2
  if not passwd:
    passwd = getpass.getpass()

  srvr = srvConnect(host, port, ssltls)
  if not srvr: return 3

  if not srvLogin(srvr, user, passwd):
    return 4

  # List all the directories under mailDir that contain the
  # file "metadata". These are mailboxes. Then strip the leading
  # "maildir" part from the names. Remove any that are in the
  # exclude list, and then limit to those listed on the command
  # line.
  dirList = []
  mdlen = len(mailDir)
  if not mailDir.endswith(os.sep): mdlen += 1
  for dirInfo in os.walk(mailDir):
    if 'metadata' in dirInfo[2]:
      dirList.append(dirInfo[0][mdlen:])
  if excludes:
    dirList = filter(lambda x: not included(x, excludes), dirList)
  l = includes + args
  if l:
    dirList = filter(lambda x: included(os.path.basename(x), l), dirList)
  dirList.sort(mboxNameCompare)

  mailboxes = getMailboxes(srvr)
  if not mailboxes:
    print >>sys.stderr, "Unable to read mailbox list from server"
    return 5

  for name in dirList:
    uploadMbox(srvr, name)

  return 0

def uploadMbox(srvr, name):
  '''Upload a single mailbox.'''
  global host, port, ssltls, authtype, user, passwd, timeout
  global verbose, longform, waitTime, mailDir, prefix, notreally
  global deleteFirst, force
  global includes, excludes
  mboxname = prefix + name
  if deleteFirst:
    if verbose:
      print 'Delete mailbox', mboxname
    if not notreally:
      srvr.delete(mboxname)
  if verbose:
    print 'Upload mailbox', mboxname
  if not notreally:
    srvr.create(mboxname)
  resp = srvr.select(mboxname, notreally)
  if resp[0] == 'OK':
    nmesg = int(resp[1][0])
    if verbose >= 2:
      print 'Mailbox %s opened, %d messages' % (mboxname, nmesg)
    if nmesg > 0 and not force:
      print >>sys.stderr, \
	"Mailbox %s is not empty, not uploading any messages" % \
	mboxname
    else:
      # Get list of messages in the mail directory from metadata.
      messages = readMetadata(os.path.join(mailDir, name, 'metadata'))
      nmesg = len(messages)
      # Get list of messages already on the server
      srvrMessages = getMailboxHeaders(srvr, mboxname, verbose > 0)
      if srvrMessages:
	headers = email.message_from_string(srvrMessages[0]['RFC822.HEADER'])
	parser = email.parser.Parser()
	msgIds = set(getMessageId(msg, parser) for msg in srvrMessages)
	srvrMessages = None
      else:
	msgIds = set()
      pct0 = 0
      t0 = time.time()
      for idx,msg in enumerate(messages):
	if msg['msgid'] in msgIds:
	  if verbose >= 2:
	    print 'Not uploading message %d, %s, already on server.' % \
	      (msg['UID'], msg['msgid'])
	else:
	  uploadOne(srvr, name, mboxname, msg)
	  if verbose == 1:
	    pct = (idx+1) * 100 // nmesg
	    t = time.time()
	    if pct != pct0 or t > t0+1:
	      sys.stdout.write('\r%d/%d %d%% ' % ((idx+1), nmesg, pct))
	      sys.stdout.flush()
	      pct0 = pct
	      t0 = t
      if verbose == 1:
	print

def getMessageId(msg, parser):
  '''Return message id, or make one up.'''
  headers = parser.parsestr(msg['RFC822.HEADER'])
  if 'Message-Id' in headers: return headers['Message-Id']
  return '<UID-%d>' % msg['UID']

def uploadOne(srvr, name, mboxname, msg):
  '''Upload one message to the server.'''
  global verbose, longform, waitTime, mailDir, prefix, notreally
  global deleteFirst, force
  global includes, excludes
  msgFileName = os.path.join(mailDir, name, 'u%d' % msg['UID'])
  with open(msgFileName, "r") as msgFile:
    msgData = msgFile.read()
  flags = msg["FLAGS"]
  # \Recent is not allowed in flags, apparently.
  flags = filter(lambda x:x != '\\Recent', flags)
  flags = ' '.join(flags)
  if verbose >= 2:
    print 'Uploading message %d, %d bytes to %s' % \
      (msg['UID'], len(msgData), mboxname)
  if not notreally:
    try:
      srvr.append(mboxname, flags, None, msgData)
    except imaplib.IMAP4.error as e:
      print >>sys.stderr, "Failed to write message %d," % msg['UID'], e



def mboxNameCompare(a,b):
  sa = specialName(a)
  sb = specialName(b)
  if sa != sb: return cmp(sb,sa)
  return cmp(a, b)


def readMetadata(filename):
  '''Read a metadata file for message numbers, uids, msgids, and flags. Return
  a list of Mbox objects.'''
  # Return list of messages. Remove dupes.
  with open(filename, "r") as ifile:
    messages = {}
    for line in ifile:
      if line.startswith('#'): continue
      line = line.strip()
      try:
	msgno, uid, msgid, flags = line.split('\t')
	uid = int(uid)
	msg = {}
	msg['msgno'] = int(msgno)
	msg['UID'] = uid
	msg['msgid'] = msgid
	msg['FLAGS'] = ast.literal_eval(flags)
	messages[uid] = msg
      except ValueError as e:
	print >>sys.stderr, 'Failed to unpack %s, line:' % filename, line
  keys = messages.keys()
  keys.sort()
  return [messages[k] for k in keys]




# ---- Server interaction ----

def srvConnect(host, port, ssltls):
  '''Connect to server, return server object or None.'''
  global verbose, timeout
  if timeout:
    socket.setdefaulttimeout(timeout)
  if port == None and ssltls == None:
    port = 143
    ssltls = False
  if port == None:
    port = 993 if ssltls else 143
  if ssltls == None:
    ssltls = port == 993
  if verbose:
    print 'Connect to %s:%d, ssl %s' % (host, port, ssltls)
  try:
    if ssltls:
      srvr = imaplib.IMAP4_SSL(host, port)
    else:
      srvr = imaplib.IMAP4(host, port)
    return srvr
  except socket.error as e:
    print 'failed to connect to', host
    print e
    return None

def srvLogin(srvr, user, passwd):
  '''Execute login. Return True or False.'''
  global host, port, ssltls, authtype, timeout
  global verbose, longform, waitTime, mailDir

  if not authtype:
    for cap in srvr.capabilities:
      if cap.startswith('AUTH='):
	authtype = cap.split('=')[1].lower()
	break
  if verbose:
    print 'Login user', user
  try:
    if not authtype or authtype == 'plain':
      srvr.login(user, passwd)
      return True
    elif authtype == 'md5':
      srvr.login_cram_md5(user, passwd)
      return True
    else:
      print >>sys.stderr, "Authtype %s not known" % authtype
      return False
  except imaplib.IMAP4.error as e:
    print >>sys.stderr, "Login failed:", e
    return False


def getMailboxes(srvr):
  '''Return list of Mbox objects for this server.'''
  mailboxes = srvr.list()
  if mailboxes[0] == 'OK':
    mailboxes = map(Mbox, mailboxes[1])
    mailboxes.sort()
    return mailboxes
  else:
    return None


# ---- UTILITIES ----

def parseEmail(email, u=None, h=None, p=None):
  '''Extract user, host, port from user@host:port. Return
  user,host,port tuple.'''
  if '@' not in email:
    u = email
  else:
    parts = email.split('@')
    u = '@'.join(parts[:-1])
    h = parts[-1]
    if ':' in h:
      h,p = h.split(':')
      p = int(p)
  return (u,h,p)


def parseEmailAndDefaults(emailAddr):
  '''Extract user, host, port from user@host:port. Set remaining
  defaults as appropriate. Command-line options take precedence
  over email address.'''
  global host, port, ssltls, authtype, user, passwd, timeout
  global verbose, longform

  if emailAddr:
    user,h,p = parseEmail(emailAddr, user, host, port)
    if not host: host = h
    if not port: port = p

  if not host: host = 'localhost'

  if port != None: port = int(port)

  if not port and ssltls == None:
    port = 143
    ssltls = False
  elif not port:
    port = 993 if ssltls else 143


def matchBoxes(pat, mailboxes, excludes):
  '''Given a pattern, a list of mailboxes, and a list of "exclude"
  patterns, return a list of mailboxes that match the pattern and
  don't match any of the exclude patterns.'''
  boxes = [x for x in mailboxes if fnmatch.fnmatch(str(x), pat)]
  if excludes:
    boxes = [x for x in boxes if not included(str(x), excludes)]
  return boxes

def included(name, patterns):
  '''Return True if "name" is in any of the patterns'''
  return any(fnmatch.fnmatch(name, pat) for pat in patterns)


def parseList(srvresp):
  '''Scan string s for (lists) and strings. Return list of results'''
  rval = []
  s = srvresp.strip()
  while s:
    if s.startswith('('):
      i = s.find(')')
      if i < 1:
	print >>sys.stderr, "Malformed server response:", srvresp
	return None
      rval.append(s[1:i].split())
      s = s[i+1:].lstrip()
    elif s.startswith('"'):
      i = s.find('"',1)
      if i < 1:
	print >>sys.stderr, "Malformed server response:", srvresp
	return None
      rval.append(s[1:i])
      s = s[i+1:].lstrip()
    else:
      i = s.find(' ')
      if i < 0:
	i = len(s)
      rval.append(s[0:i])
      s = s[i:].lstrip()
  return rval


def parseFetch(resp):
  '''Parse a fetch() response; return a list of messages. Each
  message is a dict contining 'msgno' plus any other fields
  requested in the fetch() request.'''
  # Each message consists of a sequence of tuples and
  # strings. The message is terminated by a string that
  # ends with ')'
  # resp ::= ['OK', [message…]]
  # message ::= rstring|tuple… rstring')'
  # tuple ::= (rstring, bodyString)
  # rstring ::= rpart…
  # rpart ::= key intvalue | key (listvalue) | key {size}
  if not isinstance(resp, tuple):
    print >>sys.stderr, resp, 'is not a tuple'
    return None
  if len(resp) < 1 or resp[0] != 'OK':
    print >>sys.stderr, resp, 'is not a valid response'
    return None
  resp = resp[1]
  messages = []
  while resp:
    idx = messageEnd(resp)
    msg = parseMessage(resp[:idx+1])
    if msg:
      messages.append(msg)
    resp = resp[idx+1:]
  return messages

def messageEnd(l):
  '''Search list for a string that ends with ')'; return the
  index of that entry.'''
  for i,x in enumerate(l):
    if isinstance(x, (str,unicode)) and x.endswith(')'):
      return i
  return len(l)-1

def parseMessage(resp):
  '''A message is a sequence of 2-tuples and strings. In
  the case of a 2-tuple, the second half is the text content
  of something, such as the message headers or body.'''
  # The first element will start with the message number and '('
  msg = {}
  first = True
  for item in resp:
    if isinstance(item, (str, unicode)):
      parseMessageStr(msg, item, first)
    else:
      key = parseMessageStr(msg, item[0], first)
      msg[key] = item[1]
    first = False
  return msg

def parseMessageStr(msg, item, firstItem):
  if firstItem:
    item = item.split(' ', 1)
    msg['msgno'] = int(item[0])
    item = item[1]
  item = item.strip('()')
  key = None
  while item:
    item = item.lstrip()
    item = item.split(' ',1)
    if len(item) < 2:
      return None
    key,item = item
    if item[0].isdigit():
      item = item.split(' ',1)
      msg[key] = int(item[0])
      if len(item) < 2:
	return None
      item = item[1]
    elif item.startswith('('):
      idx = item.find(')')
      flags = item[1:idx]
      msg[key] = flags.split()
      item = item[idx+1:]
    elif item.startswith('{'):
      return key
  return None


def specialName(name):
  return name in ('Drafts', 'INBOX', 'Junk', 'Sent', 'Trash',
    'Archive', 'Deleted Messages', 'Sent Messages')


flagMap = {'\\marked': MBOX_MARKED,
	'\\unmarked': MBOX_UNMARKED,
	'\\noinferiors': MBOX_NO_INFERIORS,
	'\\haschildren': MBOX_CHILDREN,
	'\\hasnochildren': MBOX_NO_CHILDREN,
	'\\all': MBOX_ALL,
	'\\archive': MBOX_ARCHIVE,
	'\\drafts': MBOX_DRAFTS,
	'\\junk': MBOX_JUNK,
	'\\sent': MBOX_SENT,
	'\\trash': MBOX_TRASH,
	'\\flagged': MBOX_FLAGGED,
	'\\noselect': MBOX_NO_SELECT,
      }

# flag, column, letter
letterMap = ((MBOX_MARKED, 1, '*'),
	(MBOX_UNMARKED, 2, 'u'),
	(MBOX_NO_INFERIORS, 0, '-'),
	(MBOX_CHILDREN, 0, 'd'),
	(MBOX_NO_CHILDREN, 0, 'C'),
	(MBOX_ALL, 3, 'A'),
	(MBOX_ARCHIVE, 3, 'a'),
	(MBOX_DRAFTS, 3, 'd'),
	(MBOX_JUNK, 3, 'j'),
	(MBOX_SENT, 3, 's'),
	(MBOX_TRASH, 3, 't'),
	(MBOX_FLAGGED, 4, 'f'),
	(MBOX_NO_SELECT, 5, 'n'),
      )


def readpats(filename):
  with open(filename, 'r') as ifile:
    return map(string.rstrip, ifile.readlines())


if __name__ == '__main__':
  signal.signal(signal.SIGPIPE, signal.SIG_DFL)
  try:
    sys.exit(main())
  except KeyboardInterrupt as e:
    print
    sys.exit(1)
