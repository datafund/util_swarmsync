#!/usr/bin/env python3
from tqdm import tqdm
import time, sys, logging, os, json, mimetypes, math, argparse, aiohttp, aiofiles, asyncio
from itertools import cycle, islice
from pathlib import Path
from secrets import token_hex

__version__ = '0.0.4.b2'

### init paths and homedir
home=Path.home() / '.swarmsync'
ALLFILES=Path.home() / '.swarmsync/allfiles.json'
TODO=Path.home() / '.swarmsync/todo.json'
ADDRESS=Path.home() / '.swarmsync/address'
TAG=Path.home() / '.swarmsync/tag.json'
RESPONSES=Path.home() / '.swarmsync/responses.json'
RETRIEVABLE=Path.home() / '.swarmsync/retrievable.json'
Path(home).mkdir(exist_ok=True)
yes = {'yes','y', 'ye', ''}
no = {'no','n'}
address=""
tag={}
urll=[]

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

def prepare():
  global pin,stamp
  pin=args.pin
  stamp=args.stamp

  FILES=sorted(list(filter(lambda x: x.is_file(), Path(args.path).rglob(args.search))))
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
                yield chunk
                chunk = await f.read(chunk_size)
            self.pbar.close()

def get_size():
    get = read_dict(RESPONSES)
    calc=[]
    for x in get:
        for y in x['item']:
          calc.append(y['size'])
    total = sum(calc)
    print('Total size of uploaded data: ', convert_size(total))

def response_dict(file, a_dict):
  l_dict = [a_dict]
  o_dict = read_dict(file)
  if o_dict is not None:
    o_dict.append(a_dict)
    write_dict(file, str(o_dict).replace("'",'"'))
  else:
    write_dict(file, str(l_dict).replace("'",'"'))

async def aioget(ref, url: str, session: aiohttp.ClientSession, sem):
    global display
    resp_dict = []
    try:
        async with sem, session.get(url + ref) as res:
            if 200 <= res.status <= 300:
                response = await res.json()
                result = response['isRetrievable']
                quoted_result = f'{result}'
                resp_dict = { "item": [ { "reference": ref, "isRetrievable": quoted_result, } ] }
                response_dict(RETRIEVABLE, resp_dict)
            return res
    except Exception as e:
        # handle error(s) according to your needs
        print(e)
    finally:
        sem.release()
        display.update()

async def aiodownload(ref, file: str, url: str, session: aiohttp.ClientSession, sem):
    global display
    try:
        async with sem, session.get(url + '/' + ref + '/') as res:
            r_data = await res.read()
            if not 200 <= res.status <= 201:
                print(f"Download failed: {res.status}")
                return res
            Path(file).parent.mkdir(exist_ok=True)
        async with aiofiles.open(file, mode='wb') as f:
            await f.write(r_data)
        return res
    except Exception as e:
        # handle error(s) according to your needs
        print(e)
    finally:
        sem.release()
        display.update()

async def aioupload(file: FileManager, url: str, session: aiohttp.ClientSession, sem):
    resp_dict = []
    (MIME,_ )=mimetypes.guess_type(file.name, strict=False)
    if MIME is None:
        MIME = "application/octet-stream"

    headers={"Content-Type": MIME, "swarm-deferred-upload": "false", "swarm-pin": pin,
             "swarm-postage-batch-id": stamp }
    if tag['uid']:
        headers.update=({ "swarm-tag": json.dumps(tag['uid']) })

    try:
        async with sem, session.post(url + '?name=' + os.path.basename(file.name),
                                headers=headers, data=file.file_reader()) as res:
            scheduled.remove(file.name)
            if 200 <= res.status <= 300:
              response = await res.json()
              ref = response['reference']
              resp_dict = { "item": [ { "file": file.name, "reference": ref, "size": file.size} ] }
              # if we have a reference we can asume upload was sucess
              # so remove from todo list
              if len(ref) == 64:
                todo.remove({"file": file.name })
                write_list(TODO, todo)
            #else:
              #print(res.status)
            response_dict(RESPONSES, resp_dict)
            return res
    except Exception as e:
        # handle error(s) according to your needs
        print(e)
    finally:
        sem.release()

async def async_check(scheduled, url: str):
    global display
    sem = asyncio.Semaphore(args.count)
    session_timeout=aiohttp.ClientTimeout(total=14400)
    async with sem, aiohttp.ClientSession(timeout=session_timeout) as session:
        res = await asyncio.gather(*[aioget(ref, url, session, sem) for ref in scheduled])
    display.close()
    print(f'items checked ({len(res)})')

async def async_upload(scheduled, urll):
    l_url = list(islice(cycle(urll), len(scheduled)))
    scheduled = [FileManager(file) for file in scheduled]
    sem = asyncio.Semaphore(args.count)
    session_timeout=aiohttp.ClientTimeout(total=14400)
    async with sem, aiohttp.ClientSession(timeout=session_timeout) as session:
        res = await asyncio.gather(*[aioupload(file, url, session, sem) for file, url in zip(scheduled, l_url)])
    print(f'items uploaded ({len(res)})')

async def async_download(references, paths, urll):
    global display
    l_url = list(islice(cycle(urll), len(references)))
    sem = asyncio.Semaphore(args.count)
    session_timeout=aiohttp.ClientTimeout(total=14400)
    async with sem, aiohttp.ClientSession(timeout=session_timeout) as session:
        res = await asyncio.gather(*[aiodownload(reference, file, url, session, sem) for reference, file, url in zip(references, paths, l_url)])
    display.close()
    print(f'items downloaded ({len(res)})')

def lst_to_dict(lst):
    res_dct = {}
    length=len(lst)
    for x in range(length):
        jsd=json.dumps(lst[x])
        res_dct[jsd]=jsd
    return res_dct

def clean_responses():
    get = read_dict(RESPONSES)
    if get:
      clean=lst_to_dict(get)
      clean=clean.values()
      clean=str(clean).replace("dict_values(", '')
      clean=str(clean).replace(")", '')
      clean=str(clean).replace("'", "")
      write_dict(RESPONSES, clean)

def cleanup(file):
    #sanitze responses if there was a failure
    clean = read_dict(file)
    if clean is not None:
      clean = str_list = list(filter(None, clean))
      write_dict(file, str(clean).replace("'",'"'))
    clean_responses();

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
    tag = {}
    if Path(TAG).is_file():
        tag = read_dict(TAG)
    else:
        params = json.dumps({ "address": addr })
        headers = { "Content-Type": "application/json" }
        async with aiohttp.ClientSession() as session:
            async with session.post(normalize_url(url, 'tags'), headers=headers, data=params) as resp:
                if 200 <= resp.status <= 300:
                    tag = await resp.json()
                    write_list(TAG, tag)
    return tag

def main():
    global scheduled,todo
    cleanup(RESPONSES)
    todo = read_dict(TODO)
    print('\n\n\n')
    scheduled=[]
    for x in todo:
      scheduled.append(x['file'])

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
                print ('using existing address')
            else:
                choice = input('No address detected. Create a random address ? [Y]es/[n]o:').lower()
                if choice in yes:
                  address = token_hex(32)
                else:
                  print('Error: Enter an address as argument')
            if address:
                tag = asyncio.run(get_tag(args.beeurl, address))
                write_list(ADDRESS, address)
                print ("saving address: ", address)
            else:
                print('Error: could not post tag to bee without an address')
                quit()
    print ("TAG uid: ", tag['uid'])
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

def check():
    global url,display
    if args.count:
      print ("count: ", args.count)
    if args.beeurl:
      url = normalize_url(args.beeurl, 'stewardship/')
      print ("url: ", url)
    if args.tag or args.e:
        print('\n\n\n')
        asyncio.run(check_tag(normalize_url(args.beeurl, 'tags/'), args.tag))
        quit()

    global scheduled
    checklist = read_dict(RESPONSES)
    scheduled=[]
    for x in checklist:
        for y in x['item']:
          scheduled.append(y['reference'])
    print('\n\n\n')
    print('Checking stewardship...')
    display=tqdm(
        total=len(scheduled),
        desc='checking',
        unit='references',
        colour='#ff8c00',
        leave=True)
    asyncio.run(async_check(scheduled, url))

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
    for x in download:
        for y in x['item']:
          references.append(y['reference'])
          paths.append(y['file'])

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
    loop.run_until_complete(async_download(references, paths, urll))
    end = time.time()
    loop.run_until_complete(asyncio.sleep(0.250))
    loop.close()
    print('Time spent downloading:', time.strftime("%H:%M:%S", time.gmtime(end-start)))

# init file
if not Path(RETRIEVABLE).is_file():
    write_dict(RETRIEVABLE, '[]')

# Initialize parser
parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers()

parser.add_argument('-v', '--version', action='version',
                    version='%(prog)s {version}'.format(version=__version__))

parser_show = subparsers.add_parser('show',
                                    help='print values of todo,responses or retrievables')
parser_show.add_argument('s', type=str, help = """enter string string name to display.
                         options: todo, responses, retrievable""",
                         choices=['todo', 'responses', 'retrievable', 'size'],
                         metavar='<name_of_list>', default='responses')
parser_show.set_defaults(func=show)

parser_download = subparsers.add_parser('download',
                                    help='download everything from responses list')
parser_download.add_argument("-u", "--beeurl", type=str, help =  """enter http address of bee.
                          ie. http://0:1633""", default="http://0:1633")
parser_download.add_argument("-c", "--count", type=int, required=False,
                          help = "number of concurrent download", default=10)
parser_download.set_defaults(func=download)

#parser_test = subparsers.add_parser('test', help='test')
#parser_test.set_defaults(func=test)

parser_check = subparsers.add_parser('check',
                                     help='check if files can be downloaded using stewardship or check tag status')
parser_check.set_defaults(func=check)
parser_check.add_argument("-u", "--beeurl", type=str, help =  """enter http address of bee.
                          ie. http://0:1633""", default="http://0:1633")
parser_check.add_argument("-c", "--count", type=int, required=False,
                          help = "number of concurrent uploads", default=10)
parser_check.add_argument("-e", action=argparse.BooleanOptionalAction, help="check the existing/stored tag uid", required=False, default=False)
parser_check.add_argument("-t", "--tag", type=str, required=False, help="enter tag uid to fetch info about", default="")

parser_upload = subparsers.add_parser('upload', help='upload folder and subfolders')
parser_upload.add_argument("-p", "--path",type=str,
                           help = "enter path to folder to be uploaded.", default=".")
parser_upload.add_argument("-u", "--beeurl", type=str, help = """enter http address of bee. separate multiple bees with comma.
                          ie. http://0:1633""", default="http://0:1633")
parser_upload.add_argument("-c", "--count", type=int,
                           help = "number of concurrent uploads", default=5)
parser_upload.add_argument("-s", "--search", type=str,
                           help = "search param(* or *.jpg or somename.txt", default="*.*")
parser_upload.add_argument("-S", "--stamp", type=str,
                           help = "enter bee stamp id",
                           default="0000000000000000000000000000000000000000000000000000000000000000")
parser_upload.add_argument("-P", "--pin", type=str,
                           help = "should files be pinned True or False",
                           choices=['true', 'false'], default="False")
parser_upload.add_argument("-t", "--tag",
                           help = """enter a uid tag for upload. if empty a new tag will be created.
                                     use --no-tag if you dont want any tag.""")
parser_upload.add_argument("--no-tag", action='store_true', help="Disable tagging")
parser_upload.add_argument("-a", "--address", type=str, help="Enter a eth address or hex of lenght 64",
                           default="")
parser_upload.set_defaults(func=upload)

if len(sys.argv)==1:
  parser.print_help(sys.stderr)
  sys.exit(1)

args = parser.parse_args()
if args.func:
    args.func()

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

