#!/usr/bin/env python3
# encoding: utf-8
from tqdm import tqdm
import time, sys, logging, os, json, mimetypes, math, argparse, aiohttp, aiofiles, asyncio
import re,hashlib
from itertools import cycle, islice
from pathlib import Path
from secrets import token_hex
from termcolor import colored
from collections import OrderedDict
from pymantaray import MantarayIndex,Entry,MantarayIndexHTMLGenerator

__version__ = '0.0.5.r3'

yes = {'yes','y', 'ye', ''}
no = {'no','n'}
address=""
tag={}
urll=[]
all_errors=[]
all_ok=""

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
    global home, ALLFILES, TODO, ADDRESS, TAG, RESPONSES, RETRIEVABLE, RETRY, MANTARAY, INDEX
    if local != True:
        home = Path('.').resolve() / '.swarmsync'
    else:
        home = Path.home() / '.swarmsync'

    ALLFILES = home / 'allfiles.json'
    TODO = home / 'todo.json'
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
  global home,ALLFILES,TODO,ADDRESS,TAG,RESPONSES,RETRIEVABLE,RETRY
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
                quit()
            await asyncio.sleep(2)
            return res
    except Exception as e:
        # handle error(s) according to your needs
        print(e)
    finally:
        display.update()
        sem.release()

async def aiodownload(ref, file: str, url: str, session: aiohttp.ClientSession, sem, sha256):
    global display
    await sem.acquire()
    try:
        async with session.get(url + '/' + ref + '/') as res:
            r_data = await res.read()
            if not 200 <= res.status <= 299:
                return res
        if sha256:
            if sha256 == hashlib.sha256(r_data).hexdigest():
                Path(file).parent.mkdir(exist_ok=True)
                async with aiofiles.open(file, mode='wb') as f:
                    await f.write(r_data)
            else:
                res.status = 409
                res.reason = 'sha256'
        else:
            Path(file).parent.mkdir(exist_ok=True)
            async with aiofiles.open(file, mode='wb') as f:
                await f.write(r_data)
        return res
    except Exception as e:
        # handle error(s) according to your needs
        print(e)
    finally:
        display.update()
        sem.release()

async def aioupload(file: FileManager, url: str, session: aiohttp.ClientSession, sem):
    global scheduled,todo,tag
    await sem.acquire()
    resp_dict = {}
    (MIME,_ )=mimetypes.guess_type(file.name, strict=False)
    if MIME is None:
        MIME = "application/octet-stream"

    headers={"Content-Type": MIME, "swarm-deferred-upload": "false",
             "swarm-postage-batch-id": stamp }
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
    try:
        async with session.post(url + '?name=' + n_file,
                                headers=headers, data=file.file_reader()) as res:
            scheduled.remove(file.name)
            if 200 <= res.status <= 300:
                response = await res.json()
                ref = response['reference']
                if len(ref) == 64 and not args.reupload:
                    # if we have a reference we can asume upload was sucess
                    # so remove from todo list
                    todo.remove({ "file": file.name })
                    write_list(TODO, todo)

                if len(ref) > 64:
                    # if we have a reference and its longer than 64 then we can asume its encrypted upload
                    resp_dict = { "file": file.name, "reference": ref[:64], "decrypt": ref[64:], "size": file.size, "sha256": file.sha256.hexdigest(), "Content-Type": MIME }
                    todo.remove({ "file": file.name })
                    write_list(TODO, todo)
                if len(ref) == 64:
                    resp_dict = { "file": file.name, "reference": ref, "size": file.size, "sha256": file.sha256.hexdigest(), "Content-Type": MIME }
                if len(ref) < 64:
                    #something is wrong
                    print('Lenght of response is not correct! ', res.status)
                    cleanup(RESPONSES)
            else:
                print('\n\n An error occured: ', res.status)
                # better quit on error
                cleanup(RESPONSES)
            #everything passed, write response
            response_dict(RESPONSES, resp_dict)
            return res
    except Exception as e:
        # handle error(s) according to your needs
        print(e)
    finally:
        sem.release()

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

async def async_download(references, paths, urll, sha256l):
    global display,args
    l_url = list(islice(cycle(urll), len(references)))
    sem = asyncio.Semaphore(args.count)
    session_timeout=aiohttp.ClientTimeout(total=14400)
    async with sem, aiohttp.ClientSession(timeout=session_timeout) as session:
        res = await asyncio.gather(*[aiodownload(reference, file, url, session, sem, sha256) for reference, file, url, sha256 in zip(references, paths, l_url, sha256l)])
    display.close()
    print(f'\nitems to download ({len(res)})')
    status = []
    for i in res:
        status.append(i.status)
    status = [str(x) for x in status]
    print(f'sha256 checksum mismatches ({status.count("409")})')
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
    #sanitze responses if there was a failure
    clean = read_dict(file)
    for i in range(len(clean)):
        clean[i] = q_dict(clean[i])
    if clean is not None:
        clean = str_list = list(filter(None, clean))
        write_dict(file, str(clean))
    clean_responses(file);

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
            size = entry_data.get('size')
            sha256 = entry_data.get('sha256')
            content_type = entry_data.get('content_type', 'application/octet-stream')
            entry = Entry(file, reference, size, sha256, content_type)
            index.add_entry(entry.to_dict())
    else:
        # Open the existing index file
        index = MantarayIndex(index_file)

        # add any new entries to the index
        existing_references = {entry['reference'] for entry in index.get_existing_references()}
        for entry_data in json_data:
            if entry_data['reference'] not in existing_references:
                content_type = entry_data.get('content_type', 'application/octet-stream')
                entry = Entry(entry_data['file'], entry_data['reference'], entry_data['size'], entry_data['sha256'], content_type)
                index.add_entry(entry.to_dict())

    # Save the index to disk
    try:
        index.save_index()
    except:
        return False

    return True

def main():
    global scheduled,todo
    cleanup(RESPONSES)
    if args.reupload:
        scheduled = read_dict(RETRY)
    else:
        todo = read_dict(TODO)
        scheduled=[]
        for x in todo:
          scheduled.append(x['file'])

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

def upload():
    global tag,address
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
    if args.address:
        address=args.address
    if args.tag:
        tag=args.tag
    if args.beeurl:
        urls = args.beeurl.split(",")
        if len(urls) > 1 and args.no_tag != True:
            choice = input('Tagging with multiple bees is not supported. Continue without tagging? [Y]es/[N]o: ').lower()
            if choice in yes:
                args.no_tag = True
            else:
                quit()
        if len(urls) > 1 and args.stamp:
            choice = input('Uploading to multiple bees is supported only without stamp (use gateway-proxy). Continue without? [Y]es/[N]o: ').lower()
            if choice in yes:
                args.stamp = ""
            else:
                quit()
        for l in urls:
            urll.append(normalize_url(l, 'bzz'))
        print ("url: ", urll)
    if args.no_tag != True:
        if args.tag == "" or not args.tag:
            if Path(ADDRESS).is_file() and not address:
                address = read_dict(ADDRESS)
                print ('using existing address :', address)
            else:
                choice = input('No address detected. Create a random address ? [Y]es/[n]o:').lower()
                if choice in yes:
                  address = token_hex(32)
                else:
                  print('Error: Enter an address as argument')
            if address:
                tag = asyncio.run(get_tag(args.beeurl, address))
                write_list(ADDRESS, address)
            else:
                print('Error: could not post tag to bee without an address')
                quit()
    prepare()
    main()

def show():
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

def check():
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

def download():
    global display
    if args.count:
        print ("count: ", args.count)
    if args.beeurl:
        urls = args.beeurl.split(",")
        for l in urls:
            urll.append(normalize_url(l, 'bzz'))
        print ("url: ", urll)
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

def mantaray():
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

# Initialize parser
parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers()

parser.add_argument('-v', '--version', action='version',
                    version='%(prog)s {version}'.format(version=__version__))

parser.add_argument('--no-local', action='store_true', help='save swarmsync files in home folder')

### show
parser_show = subparsers.add_parser('show',
                                    help='print values of todo,responses or retrievables')
parser_show.add_argument('s', type=str, help = """enter string string name to display.
                         options: todo, responses, retrievable""",
                         choices=['todo', 'responses', 'retrievable', 'size'],
                         metavar='show', default='responses')
parser_show.add_argument("-s", "--saved-tag", action=argparse.BooleanOptionalAction, help="check the existing/stored tag uid", required=False, default=False)
parser_show.add_argument("-t", "--tag", type=str, required=False, help="enter tag uid to fetch info about", default="")
parser_show.set_defaults(func=show)

### download
parser_download = subparsers.add_parser('download',
                                    help='download everything from responses list')
parser_download.add_argument("-u", "--beeurl", type=str, help =  """enter http address of bee.
                          ie. http://0:1633""", default="http://0:1633")
parser_download.add_argument("-c", "--count", type=int, required=False,
                          help = "number of concurrent download", default=10)
parser_download.set_defaults(func=download)

#parser_test = subparsers.add_parser('test', help='test')
#parser_test.set_defaults(func=test)

### check
parser_check = subparsers.add_parser('check',
                                     help='check if files can be downloaded using stewardship or check tag status')
parser_check.set_defaults(func=check)
parser_check.add_argument("-u", "--beeurl", type=str, help =  """enter http address of bee.
                          ie. http://0:1633""", default="http://0:1633")
parser_check.add_argument("-c", "--count", type=int, required=False,
                          help = "number of concurrent uploads", default=10)
### upload
parser_upload = subparsers.add_parser('upload', help='upload folder and subfolders')
parser_upload.add_argument("-p", "--path",type=str,
                           help = "enter path to folder to be uploaded.", default=".")
parser_upload.add_argument("-u", "--beeurl", type=str, help = """enter http address of bee. separate multiple bees with comma.
                          ie. http://0:1633""", default="http://0:1633")
parser_upload.add_argument("-c", "--count", type=int,
                           help = "number of concurrent uploads", default=10)
parser_upload.add_argument("-s", "--search", type=str,
                           help = "search param(* or *.jpg or somename.txt", default="*.*")
parser_upload.add_argument("-S", "--stamp", type=str,
                           help = "enter bee stamp id",
                           default="0000000000000000000000000000000000000000000000000000000000000000")
parser_upload.add_argument("-P", "--pin", action=argparse.BooleanOptionalAction, help="should files be pinned", required=False, default=False)
parser_upload.add_argument("-t", "--tag",
                           help = """enter a uid tag for upload. if empty a new tag will be created.
                                     use --no-tag if you dont want any tag.""")
parser_upload.add_argument("--no-tag", action='store_true', help="Disable tagging")
parser_upload.add_argument("-a", "--address", type=str, help="Enter a eth address or hex of lenght 64",
                           default="")
parser_upload.add_argument("-x", "--xbee-header", type=str, help="add x-bee-node header",
                           default="")
parser_upload.add_argument("-E", "--encrypt", action=argparse.BooleanOptionalAction, help="Encrypt data", required=False, default=False)
parser_upload.add_argument("-r", "--reupload", action=argparse.BooleanOptionalAction, help="reupload items that are not retrievable", required=False, default=False)
parser_upload.set_defaults(func=upload)
### mantaray
parser_mantaray = subparsers.add_parser('mantaray', help='manage mantaray index')
parser_mantaray.add_argument("-p", "--path",type=str,
                           help = "enter path to folder to be uploaded.", default=".")
parser_mantaray.set_defaults(func=mantaray)

if len(sys.argv)==1:
  parser.print_help(sys.stderr)
  sys.exit(1)

args = parser.parse_args()
init_paths(args.no_local)
if args.func:
    args.func()

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

