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

    $ ./imap.py -u user@mail.example.com:993 describe
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
    $ ./imap.py -d ./LocalMail -u user@mail.example.com:993 download games Jokes House House/Plumbing
    Password: 
    games: 3 messages
    Jokes: 6 messages
    House: 25 messages
    House/Plumbing: 2 messages

### Download all mailboxes

    $ mkdir LocalMail
    $ ./imap.py -d ./LocalMail -u user@mail.example.com:993 download
    Password: 
    ...

### Upload mailboxes

    $ ./imap.py -d ./LocalMail -u user@mail.newhost.com:993 upload games jokes
    Password: 
    ...
