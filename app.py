#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
import time, sys, getopt, logging, os, functools, json, mimetypes
from urllib.parse import urlparse
from urllib.parse import parse_qs
from pathlib import Path
from requests.exceptions import HTTPError
import requests
import argparse
from deepdiff import DeepDiff
import upload
import itertools
import asyncio


# Initialize parser
parser = argparse.ArgumentParser()
# Adding optional argument
parser.add_argument("-p", "--path",type=str, help = "path to upload", default=".")
parser.add_argument("-u", "--beeurl", type=str, help = "beeurl", default="http://0:1633/bzz")
parser.add_argument("-c", "--count", type=int, help = "number of concurrent uploads", default=5)
parser.add_argument("-s", "--search", type=str, help = "search param(* or *.jpg or somename.txt", default="*.*")
parser.add_argument("-S", "--stamp", type=str, help = "bee batch", default="57819a5ac47d3a8bd4a9817c23a40e2105e27fcb9c1073e53a490a562879e0c9")
parser.add_argument("-P", "--pin", type=str, help = "pin", default="False")

# Read arguments from command line
if len(sys.argv)==1:
    parser.print_help(sys.stderr)
    sys.exit(1)
args = parser.parse_args()

if args.path:
    print ("path: ", args.path)
if args.count:
    print ("count: ", args.count)
if args.search:
    print ("search: ", args.search)
if args.stamp:
    print ("stamp: ", args.stamp)
if args.pin:
    print ("pin: ", args.pin)
if args.beeurl:
#    args.beeurl = os.path.join(args.beeurl, '')
    print ("url: ", args.beeurl)

url=args.beeurl
pin=args.pin
stamp=args.stamp
home=Path.home() / '.swarmsync'
ALLFILES=Path.home() / '.swarmsync/allfiles.json'
TODO=Path.home() / '.swarmsync/todo.json'
Path(home).mkdir(exist_ok=True)
yes = {'yes','y', 'ye', ''}
no = {'no','n'}
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

def write_list(file, a_list):
    print("Started writing list data into a json file")
    with open(file, "w") as fp:
        json.dump(a_list, fp)
        print("Done writing JSON data into .json file")

# Read list to memory
def read_list(file):
    # for reading also binary mode is important
    with open(file, 'r') as fp:
        n_list = json.load(fp)
        return n_list

class Object:
    def toJSON(self):
        return json.dump(self, default=lambda o: o.__dict__, 
            sort_keys=True, indent=4)

FILES=sorted(list(filter(lambda x: x.is_file(), Path(args.path).rglob(args.search))))
jsonList = []
for f in FILES:
    jsonList.append({ "file": str(os.fspath(f))})

if Path(ALLFILES).is_file():
  oldList = read_list(ALLFILES)
  if jsonList != oldList:
    print('New files list differs from the old..')
    choice = input('Do you want to overwrite list and todo ? [Y]es/[n]o:').lower()
    if choice in yes:
      write_list(ALLFILES, jsonList)
      write_list(TODO, jsonList)
else:
  write_list(ALLFILES, jsonList)
  print("same files. lets continue...\n")

if Path(TODO).is_file():
  todo = read_list(TODO)
  print ('todo exists. lets continue...')
else:
  write_list(TODO, jsonList)

def upload_to_swarm(file):
  print(f'file {file}')
  basename=os.path.basename(file)
  (MIME,_ )=mimetypes.guess_type(basename, strict=False)
  headers={"Content-Type": MIME, "swarm-deferred-upload": "false", "swarm-pin": args.pin,
          "swarm-postage-batch-id": args.stamp }
  send_files = {'file': open(file, "rb")}
  try:
    response=requests.post(args.beeurl + '?name=' + basename,
                           headers=headers, files = send_files )
    response.raise_for_status()
    print(response.json())
  except HTTPError as http_err:
    print(f'HTTP error occurred: {http_err}')
  except Exception as err:
      print(f'Other error occurred: {err}')

listlen=len(todo)
print(listlen)
count = 1
for x in range(0,listlen,1):
  if count > args.count:
    time.sleep(5)
    print('waiting')
  print(todo[x]['file'])
  count += 1
  asyncio.run(upload.async_upload(todo[x]['file']))
  #  upload_to_swarm(x['file'])
  #  asyncio.run(async_upload(x['file'])
