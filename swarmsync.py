#!/usr/bin/env python3
# encoding: utf-8
from tqdm import tqdm
import time, sys, logging, os, json, mimetypes, math, argparse, aiohttp, aiofiles, asyncio
import re,hashlib,tempfile,shutil,signal,random
from prometheus_client import push_to_gateway, Summary, Counter, Gauge, Histogram, CollectorRegistry
from prometheus_client.exposition import basic_auth_handler
from itertools import cycle, islice
from pathlib import Path
from secrets import token_hex
from termcolor import colored
from collections import OrderedDict
from pymantaray import MantarayIndex,Entry,MantarayIndexHTMLGenerator
from typing import List
from aiohttp import web


__version__ = '0.0.5.r3'

yes = {'yes','y', 'ye', ''}
no = {'no','n'}
address=""
tag={}
urll=[]
all_errors=[]
failed_downloads = []
all_ok=""

##prometheus
# Create a metric to track time spent and requests made.
def pgw_auth_handler(url, method, timeout, headers, data):
    username = 'datafund'
    password = os.getenv('PGW_PW')
    return basic_auth_handler(url, method, timeout, headers, data, username, password)

registry = CollectorRegistry()
REQUEST_TIME = Summary('swarmsync_upload_time',
                       'Time spent processing request',
                       labelnames=['status', 'encryption', 'deferred', 'concurrency'],
                       registry=registry)
REQUEST_SIZE = Summary('swarmsync_upload_size',
                       'Uploaded file sizes',
                       labelnames=['status', 'encryption', 'deferred', 'concurrency'],
                       registry=registry)
DOWNLOAD_TIME = Summary('swarmsync_download_time',
                       'Time spent downloading request',
                       labelnames=['status', 'concurrency'],
                       registry=registry)
DOWNLOAD_SIZE = Summary('swarmsync_download_size',
                       'Downloaded file sizes',
                       labelnames=['status', 'concurrency'],
                       registry=registry)

HTTP_STATUS_COUNTER = Counter('swarmsync_status_count',
                              'Total HTTP Requests',
                              labelnames=['status', 'encryption', 'deferred', 'concurrency'],
                              registry=registry)

HTTP_STATUS_DL_COUNTER = Counter('swarmsync_dl_status_count',
                              'Total HTTP Requests',
                              labelnames=['status', 'concurrency'],
                              registry=registry)

SWARMSYNC_TIME_HISTOGRAM = Histogram(
    'swarmsync_upload_time_histogram',
    'Time consumed per file uploaded',
    labelnames=['status', 'encryption', 'deferred', 'concurrency'],
    buckets=(
        1,
        10,
        30,
        60,
        90,
        120,
        180,
        300,
        600,
        1800,
        3600,
        7200,
    ),
    registry=registry,
)

SWARMSYNC_SIZE_HISTOGRAM = Histogram(
    'swarmsync_upload_size_histogram',
    'file size uploaded',
    labelnames=['status', 'encryption', 'deferred', 'concurrency'],
    buckets=(
        1000,    #   1KB
        10000,    #   10KB
        100000,   #   100KB
        1000000,  #   1MB
        5000000,  #   5MB
        10000000,  #   10MB
        20000000,  #   20MB
        30000000,  #   30MB
        40000000,  #   40MB
        50000000,  #   50MB
        100000000,  # 100MB
        200000000,
        300000000,
        500000000,
        1000000000,  # 1GB
        2000000000,  # 2GB
        5000000000,  # 5GB
    ),
    registry=registry,
)

SWARMSYNC_DL_TIME_HISTOGRAM = Histogram(
    'swarmsync_download_time_histogram',
    'Time consumed per file downloaded',
    labelnames=['status', 'concurrency'],
    buckets=(
        1,
        10,
        30,
        60,
        90,
        120,
        180,
        300,
        600,
        1800,
        3600,
        7200,
    ),
    registry=registry,
)

SWARMSYNC_DL_SIZE_HISTOGRAM = Histogram(
    'swarmsync_download_size_histogram',
    'file size download histogram',
    labelnames=['status', 'concurrency'],
    buckets=(
        1000,    #   1KB
        10000,    #   10KB
        100000,   #   100KB
        1000000,  #   1MB
        5000000,  #   5MB
        10000000,  #   10MB
        20000000,  #   20MB
        30000000,  #   30MB
        40000000,  #   40MB
        50000000,  #   50MB
        100000000,  # 100MB
        200000000,
        300000000,
        500000000,
        1000000000,  # 1GB
        2000000000,  # 2GB
        5000000000,  # 5GB
    ),
    registry=registry,
)

def signal_handler(sig, frame):
    # This function will be called when Ctrl+C is pressed
    print("Ctrl+C pressed. Cleaning up or running specific code...")
    cleanup_prometheus()
    if args.stats:
        push_to_gateway(args.stats, job='swarmsync', registry=registry, handler=pgw_auth_handler)
    sys.exit(0)  # Exit the script gracefully

def append_list(file, a_list):
    with open(file, "a") as fp:
        json.dump(a_list, fp)

def write_list(file, a_list):
    with open(file, "w") as fp:
        json.dump(a_list, fp)

def write_dict(file, a_dict):
    with open(file, "w") as f:
        f.write(str(a_dict))

# Read list to memory
def read_dict(file):
    try:
        with open(file, 'r') as fp:
            n_list = json.load(fp)
            return n_list
    except OSError:
        return None

class Object:
    def toJSON(self):
        return json.dump(self, default=lambda o: o.__dict__,
            sort_keys=True, indent=4)

class q_dict(dict):
    def __str__(self):
        return json.dumps(self, ensure_ascii=False)

    def __repr__(self):
        return json.dumps(self, ensure_ascii=False)

def init_paths(local):
    global home, ALLFILES, TODO, ADDRESS, TAG, RESPONSES, RETRIEVABLE, RETRY, MANTARAY, INDEX, FAILED_DL
    if local != True:
        home = Path('.').resolve() / '.swarmsync'
    else:
        home = Path.home() / '.swarmsync'

    ALLFILES = home / 'allfiles.json'
    TODO = home / 'todo.json'
    FAILED_DL = home / 'failed_dl.json'
    ADDRESS = home / 'address'
    TAG = home / 'tag.json'
    RESPONSES = home / 'responses.json'
    RETRIEVABLE = home / 'retrievable.json'
    RETRY = home / 'retry.json'
    MANTARAY = home / 'mantaray.json'
    INDEX = home / 'index.html'

    home.mkdir(exist_ok=True)
    if not RETRIEVABLE.is_file():
        write_dict(RETRIEVABLE, '[]')
    if not RESPONSES.is_file():
        write_dict(RESPONSES, '[]')

def prepare():
  global pin,stamp
  global home,ALLFILES,TODO,FAILED_DL,ADDRESS,TAG,RESPONSES,RETRIEVABLE,RETRY
  pin=args.pin
  stamp=args.stamp

  FILES=sorted(list(filter(lambda x: x.is_file(), Path(args.path).rglob(args.search))))
  FILES=filter(lambda x: not any((part for part in x.parts if part.startswith("."))), FILES)
  jsonList = []
  for f in FILES:
      jsonList.append({ "file": f.as_posix() })

  if Path(ALLFILES).is_file():
    oldList = read_dict(ALLFILES)
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
    todo = read_dict(TODO)
    print ('todo exists. lets continue...')
  else:
    write_list(TODO, jsonList)

def convert_size(size_bytes):
   if size_bytes == 0:
       return "0B"
   size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
   i = int(math.floor(math.log(size_bytes, 1024)))
   p = math.pow(1024, i)
   s = round(size_bytes / p, 2)
   return "%s %s" % (s, size_name[i])

class FileManager():
    def __init__(self, file_name: str):
        self.name = file_name
        self.size = os.path.getsize(self.name)
        self.sha256 = hashlib.sha256()
        self.pbar = None

    def __init_pbar(self):
        self.pbar = tqdm(
            total=self.size,
            desc=self.name,
            unit='B',
            unit_scale=True,
            unit_divisor=1024,
            colour='#ff8c00',
            dynamic_ncols=True,
            leave=False)

    async def file_reader(self):
        self.__init_pbar()
        chunk_size = 64*1024
        async with aiofiles.open(self.name, 'rb') as f:
            chunk = await f.read(chunk_size)
            while chunk:
                self.pbar.update(chunk_size)
                self.sha256.update(chunk)
                yield chunk
                chunk = await f.read(chunk_size)
                self.sha256.update(chunk)
            self.pbar.close()

def get_size():
    get = read_dict(RESPONSES)
    calc=[]
    for x in get:
        calc.append(x['size'])
    total = sum(calc)
    print('Total size of uploaded data: ', convert_size(total))

def response_dict(file, a_dict):
  o_dict = read_dict(file)
  for i in range(len(o_dict)):
      o_dict[i] = q_dict(o_dict[i])
  o_dict.append(q_dict(a_dict))
  write_dict(file, str(o_dict))

async def create_tag():
    global address
    params = json.dumps({ "address": address })
    headers = { "Content-Type": "application/json" }
    if args.xbee_header:
        headers.update({ "x-bee-node": args.xbee_header })
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(normalize_url(args.beeurl, 'tags'), headers=headers, data=params) as resp:
                if 200 <= resp.status <= 300:
                    tag = await resp.json()
                    write_dict(TAG, json.dumps(tag['uid']))
                    return(tag['uid'])
                else:
                    print('Can not create tag!')
                    quit()
    except Exception as e:
        # handle error(s) according to your needs
        print(e)

async def aioget(ref, url: str, session: aiohttp.ClientSession, sem):
    global display
    resp_dict = []
    await sem.acquire()
    try:
        async with session.get(url + ref) as res:
            if 200 <= res.status <= 299:
                response = await res.json()
                result = response['isRetrievable']
                quoted_result = f'{result}'
                resp_dict = { "reference": ref,
                                         "isRetrievable": quoted_result, }
                response_dict(RETRIEVABLE, resp_dict)
                if result != True:
                    all_errors.append({ "reference": ref, "isRetrievable": quoted_result, })
            else:
                print('Error occured :', res.status)
                display.clear(nolock=False)
                quit()
            await asyncio.sleep(2)
            return res
    except Exception as e:
        # handle error(s) according to your needs
        print(e)
    finally:
        display.update()
        sem.release()


async def aiodownload(ref, file: str, url: str, session: aiohttp.ClientSession, sem, sha256, chunk_timeout=300, max_retries=32, retry_delay=1):
    global display
    temp_file = None

    headers = {
    "swarm-cache": str(args.cache).lower(),
    "swarm-redundancy-strategy": str(args.redundancy_strategy),
    "swarm-redundancy-fallback-mode": str(args.redundancy_fallback).lower(),
    "swarm-chunk-retrieval-timeout": args.chunk_timeout
    }

    try:
        start_time = time.time()  # Record the start time
        file_size = 0
        async with sem:  # Acquire the semaphore
            async with session.get(url + '/' + ref + '/', headers=headers) as res:
                if not 200 <= res.status <= 299:
                    failed_downloads.append({'file': file})
                    return res

                # Get the file size from the Content-Length header
                file_size = int(res.headers.get('Content-Length', 0))

                Path(file).parent.mkdir(exist_ok=True)

                buffer_size = 65536  # Adjust the buffer size according to your needs

                # Create a temporary file to store the downloaded content
                temp_file = tempfile.NamedTemporaryFile(mode='wb', delete=False)
                async with aiofiles.open(temp_file.name, mode='wb') as f:
                    while True:
                        for retry_attempt in range(max_retries):
                            try:
                                chunk = await asyncio.wait_for(res.content.read(buffer_size), timeout=chunk_timeout)
                                if not chunk:
                                    break
                                await f.write(chunk)
                                break  # Successfully downloaded chunk, exit retry loop
                            except asyncio.TimeoutError:
                                if retry_attempt < max_retries - 1:
                                    await asyncio.sleep(retry_delay)
                                else:
                                    if temp_file is not None and os.path.exists(temp_file.name):
                                        os.remove(temp_file.name)
                                    failed_downloads.append({'file': file})
                                    res = web.Response(status=408, reason='timeout')
                                    return res
                        if not chunk:
                            break

                # Calculate the SHA-256 hash of the downloaded file
                if sha256:
                    file_sha256 = hashlib.sha256()  # Create a new sha256 hash object
                    with open(temp_file.name, 'rb') as f:
                        while True:
                            chunk = f.read(buffer_size)
                            if not chunk:
                                break
                            file_sha256.update(chunk)

                    # Compare the calculated hash with the provided hash
                    if sha256 != file_sha256.hexdigest():
                        os.remove(temp_file.name)
                        res.status = 409
                        res.reason = 'sha256'
                        failed_downloads.append({'file': file})
                        return res

                # Move the temporary file to the final destination
                shutil.move(temp_file.name, file)

        return res
    except Exception as e:
        if "Response payload is not completed" in str(e):
            if temp_file is not None and os.path.exists(temp_file.name):
                os.remove(temp_file.name)
            failed_downloads.append({'file': file})
            res = web.Response(status=410, reason='empty_file')
            return res
        else:
            print(f"Error during hash check or file move: {e}")
            if temp_file is not None and os.path.exists(temp_file.name):
                os.remove(temp_file.name)
            failed_downloads.append({'file': file})
            return None
    finally:
        if sem.locked():
            sem.release()
        display.update()
        # Record the timing information with labels
        end_time = time.time()  # Record the end time
        duration = end_time - start_time
        DOWNLOAD_TIME.labels(status=res.status, concurrency=int(args.count) -1).observe(duration)
        DOWNLOAD_SIZE.labels(status=res.status, concurrency=int(args.count) -1).observe(file_size)
        SWARMSYNC_DL_TIME_HISTOGRAM.labels(status=res.status, concurrency=int(args.count) -1).observe(duration)
        SWARMSYNC_DL_SIZE_HISTOGRAM.labels(status=res.status, concurrency=int(args.count) -1).observe(file_size)
        HTTP_STATUS_DL_COUNTER.labels(status=res.status, concurrency=int(args.count) -1).inc()
        if args.stats:
            push_to_gateway(args.stats, job='swarmsync', registry=registry, handler=pgw_auth_handler)
        write_list(FAILED_DL, failed_downloads)


async def aioupload(file: FileManager, url: str, session: aiohttp.ClientSession, sem):
    global scheduled,todo,tag
    await sem.acquire()
    resp_dict = {}
    res = None  # Initialize res to None
    (MIME,_ )=mimetypes.guess_type(file.name, strict=False)
    if MIME is None:
        MIME = "application/octet-stream"

    headers={"Content-Type": MIME, "swarm-deferred-upload": str(args.deferred),
             "swarm-postage-batch-id": stamp, "swarm-redundancy-level": str(args.redundancy) }
    if tag is not None:
        if bool(tag) != False:
            headers.update({ "swarm-tag": tag.__str__() })
    if args.encrypt:
        headers.update({ "swarm-encrypt": "True" })
    if args.pin:
        headers.update({ "swarm-pin": "True" })
    if args.xbee_header:
        headers.update({ "x-bee-node": args.xbee_header })
    n_file=re.sub('[^A-Za-z0-9-._]+', '_', os.path.basename(file.name))
    start_time = time.time()  # Record the start time
    try:
        async with session.post(url + '?name=' + n_file,
                                headers=headers, data=file.file_reader()) as res:
            scheduled.remove(file.name)
            if 200 <= res.status <= 300:
                response = await res.json()
                ref = response.get('reference', 'null')
                if len(ref) == 64 and not args.reupload:
                    # if we have a reference we can asume upload was sucess
                    # so remove from todo list
                    todo.remove({ "file": file.name })
                    write_list(TODO, todo)

                if len(ref) > 64:
                    # if we have a reference and its longer than 64 then we can asume its encrypted upload
                    resp_dict = { "file": file.name, "reference": ref[:64], "decrypt": ref[64:], "size": file.size, "sha256": calculate_sha256(file.name), "contentType": MIME }
                    todo.remove({ "file": file.name })
                    write_list(TODO, todo)
                if len(ref) == 64:
                    resp_dict = { "file": file.name, "reference": ref, "size": file.size, "sha256": calculate_sha256(file.name), "contentType": MIME }
                if len(ref) < 64:
                    #something is wrong
                    print('Lenght of response is not correct! ', res.status)
                    cleanup(RESPONSES)
            else:
                print('\n\n An error occured: ', res.status)
                # better quit on error
                ref='null'
                cleanup(RESPONSES)

            #everything passed, write response
            response_dict(RESPONSES, resp_dict)
            return res
    except Exception as e:
        # handle error(s) according to your needs
        print(e)
    finally:
        if res and res.status is not None:  # Check if res is defined and has a status attribute
            # Record the timing information with labels
            end_time = time.time()  # Record the end time
            duration = end_time - start_time
            if res.status is not None:
                REQUEST_TIME.labels(status=res.status, encryption=args.encrypt, deferred=args.deferred, concurrency=int(args.count) -1).observe(duration)
                REQUEST_SIZE.labels(status=res.status, encryption=args.encrypt, deferred=args.deferred, concurrency=int(args.count) -1).observe(file.size)
                SWARMSYNC_TIME_HISTOGRAM.labels(status=res.status, encryption=args.encrypt, deferred=args.deferred, concurrency=int(args.count) -1).observe(duration)
                SWARMSYNC_SIZE_HISTOGRAM.labels(status=res.status, encryption=args.encrypt, deferred=args.deferred, concurrency=int(args.count) -1).observe(file.size)
                HTTP_STATUS_COUNTER.labels(status=res.status, encryption=args.encrypt, deferred=args.deferred, concurrency=int(args.count) -1).inc()
            if args.stats:
                push_to_gateway(args.stats, job='swarmsync', registry=registry, handler=pgw_auth_handler)
        sem.release()

async def directupload(file: FileManager, url: str, session: aiohttp.ClientSession):
    global tag
    res=None
    MIME = "text/html"

    headers={"Content-Type": MIME, "swarm-deferred-upload": str(args.deferred),
             "swarm-postage-batch-id": args.stamp }
    if tag is not None:
        if bool(tag) != False:
            headers.update({ "swarm-tag": tag.__str__() })
    headers.update({ "swarm-pin": "True" })
    if args.xbee_header:
        headers.update({ "x-bee-node": args.xbee_header })
    n_file = re.sub('[^A-Za-z0-9-._]+', '_', os.path.basename(file.name))
    try:
        async with session.post(url + '?name=' + n_file,
                                headers=headers, data=file.file_reader()) as res:
            if 200 <= res.status <= 300:
                ref = await res.text()
                if len(ref) < 64:
                    #something is wrong
                    print('Lenght of response is not correct! ', res.status)
                else:
                    print('Reference: ', ref)
            else:
                print('\n\n An error occured: ', res.status)
    except Exception as e:
        print(e)
    finally:
        return res

async def async_check(scheduled, url: str):
    global display,args
    sem = asyncio.Semaphore(args.count)
    session_timeout=aiohttp.ClientTimeout(total=14400)
    async with sem, aiohttp.ClientSession(timeout=session_timeout) as session:
        res = await asyncio.gather(*[aioget(ref, url, session, sem) for ref in scheduled])
    display.close()
    cleanup(RETRIEVABLE)
    return res

async def async_upload(scheduled, urll):
    global args
    l_url = list(islice(cycle(urll), len(scheduled)))
    scheduled = [FileManager(file) for file in scheduled]
    sem = asyncio.Semaphore(args.count)
    session_timeout=aiohttp.ClientTimeout(total=14400)
    async with sem, aiohttp.ClientSession(timeout=session_timeout) as session:
        res = await asyncio.gather(*[aioupload(file, url, session, sem) for file, url in zip(scheduled, l_url)])
    print(f'\nitems uploaded ({len(res)})')

async def oneupload(scheduled: List[Path], urll):
    global args
    l_url = list(islice(cycle(urll), len(scheduled)))
    async with aiohttp.ClientSession() as session:
        res = await asyncio.gather(*[directupload(FileManager(str(file)), url, session) for file, url in zip(scheduled, l_url)])
        return res

async def async_download(references, paths, urll, sha256l):
    global display,args
    l_url = list(islice(cycle(urll), len(references)))
    sem = asyncio.Semaphore(args.count)
    session_timeout=aiohttp.ClientTimeout(total=86400)
    async with aiohttp.ClientSession(timeout=session_timeout) as session:
        res = await asyncio.gather(*[aiodownload(reference, file, url, session, sem, sha256) for reference, file, url, sha256 in zip(references, paths, l_url, sha256l)],
            return_exceptions=True)
    display.close()
    print(f'\nitems to download ({len(res)})')
    status = []
    for i in res:
        if i is not None:
            if isinstance(i, Exception):
                # Handle exceptions or print the exception message
                print(f"Error: {i}")
            else:
                status.append(i.status)
    status = [str(x) for x in status]
    print(f'sha256 checksum mismatches ({status.count("409")})')
    print(f'410 content-leght 0 ({status.count("410")})')
    print(f'408 Timeout ({status.count("408")})')
    print(f'404 errors ({status.count("404")})')
    status_filtered = list(filter(lambda v: re.match('50.', v), status))
    print(f'50x ({len(status_filtered)})')
    status_filtered = list(filter(lambda v: re.match('20.', v), status))
    print(f'OK ({len(status_filtered)})')


def lst_to_dict(lst):
    res_dct = {}
    length=len(lst)
    for x in range(length):
        jsd=lst[x]
        res_dct[jsd]=jsd
    return res_dct

def calculate_sha256(file_path):
    sha256_hash = hashlib.sha256()
    
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    
    return sha256_hash.hexdigest()

def clean_responses(file):
    data = read_dict(file)
    for i in range(len(data)):
        data[i] = q_dict(data[i])
    if data:
      clean = OrderedDict((frozenset(item.items()),item) for item in data).values()
      clean=str(clean).replace("odict_values(", "")
      clean=''.join(clean.rstrip(')'))
      write_dict(file, str(clean))

def cleanup(file):
    # Sanitize responses if there was a failure
    clean = read_dict(file)
    
    correct_sha_count = 0
    for i in range(len(clean)):
        clean[i] = q_dict(clean[i])
        
        if correct_sha_count < 10 and 'file' in clean[i] and os.path.exists(clean[i]['file']):
            file_sha256 = calculate_sha256(clean[i]['file'])

            if 'sha256' not in clean[i] or clean[i]['sha256'] != file_sha256:
                clean[i]['sha256'] = file_sha256
            else:
                correct_sha_count += 1

    if clean is not None:
        clean = list(filter(None, clean))
        write_list(file, clean)
    
    clean_responses(file)

def normalize_url(base: str, path: str):
    url = os.path.join(base, '')
    url = url + path
    return url

async def check_tag(url: str, u_tag: str):
    if not u_tag:
        if Path(TAG).is_file():
            tag = read_dict(TAG)
            u_tag = str(tag['uid'])
        else:
            print('Error, no tag is saved')
            quit()
    async with aiohttp.ClientSession() as session:
        async with session.get(url + u_tag) as resp:
            if 200 <= resp.status <= 300:
                tag = await resp.json()
                print(json.dumps(tag, indent=4))
            else:
                print('Error in getting tag')

async def get_tag(url: str, addr: str):
    if Path(TAG).is_file():
        u_tag = read_dict(TAG)
        if u_tag is None:
            u_tag=await create_tag()
        tag = json.dumps(u_tag)
    else:
        tag = await create_tag()
    return tag

async def create_mantaray_index(json_file_path: str, index_file_path: str) -> bool:
    # Load the JSON data from the file
    async with aiofiles.open(json_file_path, 'r') as f:
        json_str = await f.read()
    json_data = json.loads(json_str)

    # Set up the index file path
    index_file = Path(index_file_path)

    # Only create the index file if it doesn't exist
    if not index_file.is_file():
        # Create a new index file
        index = MantarayIndex(index_file)

        # add each entry to the index
        for entry_data in json_data:
            file = entry_data.get('file')
            reference = entry_data.get('reference')
            decrypt = entry_data.get('decrypt')
            size = entry_data.get('size')
            sha256 = entry_data.get('sha256')
            content_type = entry_data.get('contentType', 'application/octet-stream')
            entry = Entry(file, reference, decrypt, size, sha256, content_type)
            index.add_entry(entry.to_dict())
    else:
        # Open the existing index file
        index = MantarayIndex(index_file)

        # add any new entries to the index
        existing_references = {entry['reference'] for entry in index.get_existing_references()}
        for entry_data in json_data:
            if entry_data['reference'] not in existing_references:
                content_type = entry_data.get('content_type', 'application/octet-stream')
                entry = Entry(entry_data['file'], entry_data['reference'], entry_data.get('decrypt'), entry_data['size'], entry_data['sha256'], content_type)
                index.add_entry(entry.to_dict())

    # Save the index to disk
    try:
        index.save_index()
    except:
        return False

    return True

def cleanup_prometheus():
    REQUEST_TIME.clear()
    REQUEST_SIZE.clear()
    DOWNLOAD_TIME.clear()
    DOWNLOAD_SIZE.clear()
    SWARMSYNC_TIME_HISTOGRAM.clear()
    SWARMSYNC_SIZE_HISTOGRAM.clear()
    SWARMSYNC_DL_TIME_HISTOGRAM.clear()
    SWARMSYNC_DL_SIZE_HISTOGRAM.clear()
    if args.stats:
        push_to_gateway(args.stats, job='swarmsync', registry=registry, handler=pgw_auth_handler)

def main_common():
    global scheduled, todo, urll
    cleanup(RESPONSES)
    if args.reupload:
        scheduled = read_dict(RETRY)
    else:
        todo = read_dict(TODO)
        scheduled = [x['file'] for x in todo]

    print('\n\n\n')
    start = time.time()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(async_upload(scheduled, urll))
    end = time.time()
    loop.run_until_complete(asyncio.sleep(0.250))
    loop.close()
    cleanup(RESPONSES)
    get_size()
    print('Time spent uploding:', time.strftime("%H:%M:%S", time.gmtime(end-start)))
    cleanup_prometheus()

def main():
    main_common()

def process_common_args():
    global tag, address
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
    if args.tag:
        tag = args.tag
    if args.no_tag != 'True':
        handle_tag()
    if args.address:
        address = args.address
        print("eth address:", address)
    else:
        address = open(ADDRESS).read().strip('"')
        print("eth address:", address)
    if args.beeurl:
        handle_beeurl(args, args.command.__name__)

def handle_beeurl(args, command):
    global urll
    endpoints = {
        'upload': 'bzz',
        'feed': 'feeds',
        'check': 'stewardship',
        'download': 'bzz',
        'mantaray': 'bzz'
    }
    uri = endpoints.get(command, 'bzz')
    urls = args.beeurl.split(",")
    for l in urls:
        urll.append(normalize_url(l, uri))
    print("url: ", urll)

def handle_tag():
    global tag, address
    if Path(ADDRESS).is_file() and not address:
        address = read_dict(ADDRESS)
        print('using existing address :', address)
    else:
        choice = input('No address detected. Create a random address ? [Y]es/[n]o:').lower()
        if choice in yes:
            address = token_hex(32)
        else:
            print('Error: Enter an eth address as command argument')
    if address:
        write_list(ADDRESS, address)
        if not args.no_tag:
            tag = asyncio.run(get_tag(args.beeurl, address))


def upload():
    process_common_args()
    prepare()
    main()

def show(args):
    if 'todo' in args.s:
      get = read_dict(TODO)
      print(json.dumps(get, indent=4))
    if 'responses' in args.s:

      get = read_dict(RESPONSES)
      print(json.dumps(get, indent=4))
    if 'retrievable' in args.s:
      get = read_dict(RETRIEVABLE)
      print(json.dumps(get, indent=4))
    if 'size' in args.s:
      get_size()
    if args.tag or args.saved_tag:
        print('\n\n\n')
        asyncio.run(check_tag(normalize_url(args.beeurl, 'tags/'), args.tag))
        quit()

def check(args):
    global url,display
    if args.count:
      print ("count: ", args.count)
    if args.beeurl:
      url = normalize_url(args.beeurl, 'stewardship/')
      print ("url: ", url)

    global scheduled
    checklist = read_dict(RESPONSES)
    scheduled=[]
    for x in checklist:
        if 'decrypt' in x:
            l_ref = x['reference'] + x['decrypt']
            scheduled.append(x['reference'] + x['decrypt'])
        else:
            scheduled.append(x['reference'])
    print('\n\n\n')
    print('Checking stewardship...')
    display=tqdm(
        total=len(scheduled),
        desc='checking',
        unit='references',
        colour='#ff8c00',
        leave=True)
    res = asyncio.run(async_check(scheduled, url))
    if len(all_errors) != 0:
      print(colored(json.dumps(all_errors, indent=4), 'red'))
      print(colored('Failed items :', 'yellow'), colored(len(all_errors), 'red'))
    print(f'Total items checked :{len(res)}')
    retry=[]
    for i in all_errors:
        for x in checklist:
            if x['reference'] == i['reference']:
                retry.append(x['file'])
    if retry != []:
        write_list(RETRY, retry)

def download(args):
    global display
    if args.count:
        print ("count: ", args.count)
    if args.beeurl:
        urls = args.beeurl.split(",")
        for l in urls:
            urll.append(normalize_url(l, 'bzz'))
        print ("url: ", urll)
    cleanup(RESPONSES)
    download = read_dict(RESPONSES)
    references=[]
    paths=[]
    sha256=[]
    for x in download:
        if 'decrypt' in x:
            l_ref = x['reference'] + x['decrypt']
            references.append(x['reference'] + x['decrypt'])
        else:
            references.append(x['reference'])
        paths.append(x['file'])
        if 'sha256' in x:
            sha256.append(x['sha256'])

    display=tqdm(
        total=len(references),
        desc='Downloading',
        unit='item',
        colour='#ff8c00',
        leave=True)
    print('\n\n\n')
    print('Starting download...')
    get_size()
    start = time.time()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(async_download(references, paths, urll, sha256))
    end = time.time()
    loop.run_until_complete(asyncio.sleep(0.250))
    loop.close()
    print('Time spent downloading:', time.strftime("%H:%M:%S", time.gmtime(end-start)))
    cleanup_prometheus()

def mantaray(args):
    global display
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    index = loop.run_until_complete(create_mantaray_index(RESPONSES, MANTARAY))
    loop.close()
    if index:
        print('Index created or updated successfully!')
    else:
        print('Error creating or updating index.')
    index_html_generator = MantarayIndexHTMLGenerator(MANTARAY, INDEX, baseurl='./')
    index_html_generator.generate()
    choice = input('Do you want to upload the index.html [y]es/[n]o:').lower()
    if choice in yes:
        urll = []
        if args.beeurl != 'http://localhost:1633':
            urls = args.beeurl.split(",")
            for l in urls:
                urll.append(normalize_url(l, 'bzz'))
            print ("url: ", urll)
        else:
            choice = input('Enter beeurl: ').lower()
            urll = [normalize_url(choice, 'bzz')]

        start = time.time()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(oneupload([INDEX], urll))
        end = time.time()
        loop.run_until_complete(asyncio.sleep(0.250))
        loop.close()


# Initialize the parser and subparsers
parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers()

# Utility function to add common arguments to subparsers
def add_common_arguments(subparser):
    subparser.add_argument('--no-local', action='store_true', help='save swarmsync files in home folder', default=False)
    subparser.add_argument('-u', '--beeurl', type=str, help='enter http address of bee. i.e. http://localhost:1633', default='http://localhost:1633')
    subparser.add_argument('-c', '--count', type=int, help='number of concurrent tasks', default=10)
    subparser.add_argument("-S", "--stamp", type=str, help="enter bee stamp id", default="0000000000000000000000000000000000000000000000000000000000000000")
    subparser.add_argument('--xbee-header', action='store_true', help='add xbee header to the file')
    subparser.add_argument('--stats', type=str, help='send prometheus statistics to url', default='')



# Version argument
parser.add_argument('-v', '--version', action='version',
                    version='%(prog)s {version}'.format(version=__version__))

# Show subparser
parser_show = subparsers.add_parser('show', help='print values of todo, responses or retrievables')
parser_show.add_argument('s', type=str, help='enter string string name to display. options: todo, responses, retrievable',
                         choices=['todo', 'responses', 'retrievable', 'size'], metavar='show', default='responses')
parser_show.add_argument("-s", "--saved-tag", action=argparse.BooleanOptionalAction, help="check the existing/stored tag uid", required=False, default=False)
parser_show.add_argument("-t", "--tag", type=str, required=False, help="enter tag uid to fetch info about", default="")
add_common_arguments(parser_show)
parser_show.set_defaults(func=lambda parsed_args: show(parsed_args), command=show)


# Download subparser
parser_download = subparsers.add_parser('download', help='download everything from responses list')
parser_download.add_argument("--cache", action=argparse.BooleanOptionalAction, help="Cache the download data on the node", required=False, default=True)
parser_download.add_argument("-RS", "--redundancy-strategy", type=int, help="Redundancy strategy for data retrieval", choices=[0, 1, 2, 3], default=0)
parser_download.add_argument("--redundancy-fallback", action=argparse.BooleanOptionalAction, help="Use redundancy strategies in a fallback cascade", required=False, default=True)
parser_download.add_argument("--chunk-timeout", type=str, help="Timeout for chunk retrieval, e.g., '30s'", default="30s")
add_common_arguments(parser_download)
parser_download.set_defaults(func=lambda parsed_args: download(parsed_args), command=download)


# Check subparser
parser_check = subparsers.add_parser('check', help='check if files can be downloaded using stewardship or check tag status')
add_common_arguments(parser_check)
parser_check.set_defaults(func=lambda parsed_args: check(parsed_args), command=check)

# Upload subparser
parser_upload = subparsers.add_parser('upload', help='upload folder and subfolders')
parser_upload.add_argument("-p", "--path", type=str, help="enter path to folder to be uploaded.", default=".")
parser_upload.add_argument("-s", "--search", type=str, help="search param(* or *.jpg or somename.txt", default="*.*")
parser_upload.add_argument("-P", "--pin", action=argparse.BooleanOptionalAction, help="should files be pinned", required=False, default=False)
parser_upload.add_argument("-t", "--tag", help="enter a uid tag for upload. if empty a new tag will be created. use --no-tag if you dont want any tag.")
parser_upload.add_argument("--no-tag", action='store_true', help="Disable tagging", default=True)
parser_upload.add_argument("-a", "--address", type=str, help="Enter a eth address or hex of lenght 64",
                           default="")
parser_upload.add_argument("-E", "--encrypt", action=argparse.BooleanOptionalAction, help="Encrypt data", required=False, default=False)
parser_upload.add_argument("-r", "--reupload", action=argparse.BooleanOptionalAction, help="reupload items that are not retrievable", required=False, default=False)
parser_upload.add_argument("-d", "--deferred", action='store_false', help="sets swarm deferred upload header to False (default is True)")
parser_upload.add_argument("-R", "--redundancy", type=int, help="Redundancy level for uploaded data (0 - none, 4 - paranoid)", choices=[0, 1, 2, 3, 4], default=0)
add_common_arguments(parser_upload)
parser_upload.set_defaults(func=lambda parsed_args: upload(), command=upload)

# Mantaray subparser
parser_mantaray = subparsers.add_parser('mantaray', help='manage mantaray index')
parser_mantaray.add_argument("-d", "--deferred", action='store_false', help="sets swarm deferred upload header to False (default is True)")
add_common_arguments(parser_mantaray)
parser_mantaray.set_defaults(func=lambda parsed_args: mantaray(parsed_args), command=mantaray)

# Set up the signal handler
signal.signal(signal.SIGINT, signal_handler)

# Print help message and exit if no arguments are provided
if len(sys.argv) == 1:
    parser.print_help(sys.stderr)
    sys.exit(1)

# Parse the arguments, initialize paths, and call the function associated with the provided subparser
args = parser.parse_args()
init_paths(args.no_local)
if args.func:
    args.func(args)

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

