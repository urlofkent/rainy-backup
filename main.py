
from stegano import lsb
import requests
import random, string, os
import zlib
import sys
import base64
import imaplib, email
import time
import re, json
import urllib.parse
import getopt
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

from crypto_routines import encrypt, decrypt

def randomword(length):
   letters = string.ascii_lowercase
   return ''.join(random.choice(letters) for i in range(length))

def generate_tmp_name(ext='.png'):
    return os.path.join('/tmp/', randomword(10)+ext)

class GenerateImage:
    def __init__(self):
        pass
       
    def save_random_photo(self):
        response = requests.head('https://source.unsplash.com/random')
        url = response.url.replace('fm=jpg', 'fm=png')
        response = requests.get(url)
        fn = generate_tmp_name()
        with open(fn, 'wb') as f:
            f.write(response.content)
        return fn

    def create(self, filedata):
        image_filename = self.save_random_photo()
        hidden = lsb.hide(image_filename, filedata.decode())
        fn = generate_tmp_name()
        hidden.save(fn)
        outdata = self.reveal(fn)
        if zlib.crc32(outdata.encode()) == zlib.crc32(filedata):
            return fn
        raise "Too big maybe?"
    
    def reveal(self, filename):
        return lsb.reveal(filename)

class Mail:
    def __init__(self, server_hostname):
        self.server = imaplib.IMAP4_SSL(host=server_hostname)
        self.output = []
        self.username = ''
        
    def login(self, username, password):
        self.server.login(username, password)
        self.username = username
        self.server.select()
        
    def retrieve_query(self, query='ALL'):
        typ, data = self.server.search(None, query)
        for num in data[0].split():
            typ, data = self.server.fetch(num, '(RFC822)')
            msg = email.message_from_bytes(data[0][1])
            if msg.is_multipart():
                for part in msg.walk():
                    self.output.append(part.get_payload(decode=True))
                    
    def place(self, attachment, subject='subject', message_body='message body'):
        msg = MIMEMultipart()
        msg['From'] = self.username
        msg['Subject'] = subject
        msg.attach(MIMEText(message_body))
        part = MIMEApplication(attachment, name='attachment.bin')
        part['Content-Disposition'] = 'attachment; filename=attachment.bin'
        msg.attach(part)
        self.server.append('INBOX', '', imaplib.Time2Internaldate(time.time()), msg.as_bytes())
    def close(self):
        self.server.close()
        self.server.logout()

class ImageHost:
    def __init__(self, base_url):
        self.base_url = base_url

    def get_config(self):
        response = requests.get(self.base_url)
        self.json_url = re.search(r'obj.config.json_api="(.*?)"', response.text).group(1)
        self.auth_token = re.search(r'obj.config.auth_token="(.*?)"', response.text).group(1)
        self.user_id = re.search(r'"id":"(.*?)"', response.text).group(1)
    def get_photos(self):
        response = requests.post(
            self.json_url,
            data={
                'list': 'images',
                'sort': 'date_desc',
                'page': '1',
                'action': 'list',
                'userid': self.user_id,
                'params_hidden[userid]': self.user_id,
                'params_hidden[from]': 'user',
                'auth_token': self.auth_token
            }
        )

        objs = re.findall(r'data-object=["\'](.*?)["\']', response.json()['html'], re.M)
        output = []
        for url in [(json.loads(urllib.parse.unquote(o))['image']['url']) for o in objs]:
            response = requests.get(url)
            name = generate_tmp_name()
            output.append(name)
            with open(name, 'wb') as f:
                f.write(response.content)
        return output

    def push(self, w_apikey, data):
        response = requests.post(
            'https://api.imgbb.com/1/upload',
            params={'key': w_apikey},
            files={'image': data}
        )
        print(response.text)

                                 
        
def usage():
    print(
        sys.argv[0],
        '[push-email|push-image|pull-email|pull-image]\n', '-H [email/imagebb host] -u [email username] -p [email password] -k [imgbb api key]\n'
        '--cryptopass --rawfile'
    )


try:
    command = sys.argv[1]
    if command in ['push-email', 'push-image', 'pull-email', 'pull-image']:
        opts, args = getopt.getopt(sys.argv[2:], 'u:p:k:H:h', ['rawfile=', 'cryptopass='])
    else:
        raise IndexError
except Exception as e:
    print(e)
    usage()
    sys.exit(2)
    
for o, a in opts:
    a
    if o == '-h':
        usage()
    if o == '-u':
        username = a
    elif o == '-p':
        password = a
    elif o == '-H':
        host = a

    if o == '-k':
        w_apikey = a
   
    if o == '--rawfile':
        filename = a

    if o == '--cryptopass':
        enc_password = a


if command == 'push-email':
    with open(filename, 'rb') as f:
        data = base64.b64decode(encrypt(f.read(), enc_password))
        
    e = Mail(host)
    e.login(username, password)
    e.place(data)
    e.close()

if command == 'pull-email':
    e = Mail(host)
    e.login(username, password)
    e.retrieve_query(query='(FROM "{}")'.format(username))
    for o in e.output:
        try:
            name = generate_tmp_name(ext='.bin')
            with open(name, 'wb') as f:
                f.write(decrypt(base64.b64encode(o), enc_password))
                print(name)
        except Exception as e:
            print(e)

if command == 'push-image':
    im = GenerateImage()
    with open(filename, 'rb') as f:
        enc = encrypt(base64.b64encode(f.read()).decode(), enc_password)
    fn = im.create(enc)
    ih = ImageHost(host)
    with open(fn, 'rb') as f:
        ih.push(w_apikey, f.read())

if command == 'pull-image':
    im = GenerateImage()
    ih = ImageHost(host)
    ih.get_config()
    for photo_fn in ih.get_photos():
        try:
            with open(photo_fn+'.out', 'wb') as f:
                f.write(decrypt(im.reveal(photo_fn), enc_password))
            print(photo_fn+'.out')
        except Exception as e:
            print(e)
