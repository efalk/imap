# imap
Imap utilities

## imap.py

Simple command-line tool to download mailboxes from an imap server, or to upload
them. Created with the intent of migrating mailboxes from a local system
up to an imap server, or to migrate email from one imap server to another. Or
to backup your email into local folders. The possibilities are endless! (Actually,
I think I've already listed all the possibilities.)

Typical usage:

### Figure out where your imap server is

    $ ./imap.py -v probe user@example.com
    Probing 10 host/security connections, this can take up to 100 seconds
    Trying mail.example.com:993, ssl ... success
    Trying mail.example.com:143, no ssl ... success
    Trying imap.example.com:993, ssl ... failed to connect
    Trying imap.example.com:143, no ssl ... failed to connect
    Trying imap4.example.com:993, ssl ... failed to connect
    Trying imap4.example.com:143, no ssl ... failed to connect
    Trying example.com:993, ssl ... failed to connect
    Trying example.com:143, no ssl ... failed to connect
    Trying pop.example.com:993, ssl ... failed to connect
    Trying pop.example.com:143, no ssl ... failed to connect
    Success: host = mail.example.com, port = 993, ssl/tls = True
    Server capabilities:
      IMAP4REV1
      LITERAL+
      SASL-IR
      LOGIN-REFERRALS
      ID
      ENABLE
      IDLE
      AUTH=PLAIN
      AUTH=LOGIN


### See what mailboxes are on your account

(Note that the user's login in this example is `user@example.com` and the host is
`mail.example.com`, so the `-u` argument is `user@example.com@mail.example.com`.)

    $ ./imap.py -s -u user@example.com@mail.example.com listboxes
    Password:
    Deleted Messages
    Drafts
    INBOX
    Junk
    Sent
    Sent Messages
    Trash
    Jokes
    House
    House.Plumbing
    House.Electrical
    Vacation
    Vacation.Schedules
    games

### List the contents of a mailbox

    $ ./imap.py -u user@mail.example.com:993 list games
    Password:

    games: 3 messages
	   1  Re: whither Quake?        Joe Cool <joe@cool>      Thu, 1 Jan 1998 11:35:43 -0800 (PST)
	   2  Re: whither Quake?        Joe Cool <joe@cool>      Thu, 1 Jan 1998 11:44:52 -0800 (PST)
	   3  Re: whither Quake?        Alan Parson <Alan@Ebay>  Thu, 1 Jan 1998 15:36:36 -0800 (PST)

### Download specific mailboxes

    $ mkdir LocalMail
    $ ./imap.py -d ./LocalMail -u user@mail.example.com:993 download games Jokes House House.Plumbing
    Password: 
    games: 3 messages
    Jokes: 6 messages
    House: 25 messages
    House.Plumbing: 2 messages

### Download all mailboxes

    $ mkdir LocalMail
    $ ./imap.py -d ./LocalMail -u user@mail.example.com:993 download
    Password: 
    ...

### Upload mailboxes

    $ ./imap.py -d ./LocalMail -u user@mail.newhost.com:993 upload games jokes
    Password: 
    ...

### A note of caution where mailbox names are concerned

IMAP doesn't really have a concept of directory structure (although some servers may
include this as an extension). It's very common to use '.' as a seperator, e.g. "House" and
"House.Plumbing" as mailbox names. Many email clients recognize this convention and
convert to e.g. "House" and "House/Plumbing" on the local system.

This tool does not do this conversion, but you should be aware that some email clients, such
as Thunderbird, do.

For this reason, it's probably best to avoid mailbox names such as "Dr.Who" or "sci/fi" as
these can cause issues when moving email between remote IMAP servers and your local system.
For example, on Unix systems, it's impossible for the files "House" and "House/Plumbing" to
both exist.
