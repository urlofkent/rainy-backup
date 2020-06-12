# Rainy Backup

You never know if it's going to rain!

Using email and image hosts to back up files.

## example
$ python3 main.py push-image -H rainybackup.imgbb.com -k [key] --cryptopass 'password' --rawfile input.dat

$ python3 main.py pull-image -H rainybackup.imgbb.com --cryptopass 'password'
> /tmp/outfile.bin