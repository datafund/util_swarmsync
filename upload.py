import os
import asyncio
import aiohttp
import aiofiles
import mimetypes
import app
from tqdm import tqdm


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
            leave=True)

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


async def upload(file: FileManager, url: str, session: aiohttp.ClientSession):
    basename=os.path.basename(file)
    (MIME,_ )=mimetypes.guess_type(basename, strict=False)
    headers={"Content-Type": MIME, "swarm-deferred-upload": "false", "swarm-pin": app.pin,
            "swarm-postage-batch-id": app.stamp }

    try:
        async with session.post(url, headers=headers, data=file.file_reader()) as res:
            # NB: if you also need the response content, you have to await it
            return res
    except Exception as e:
        # handle error(s) according to your needs
        print(e)


async def async_upload(files):
    print(f'aync_received: {files}')
    files = FileManager(files)

    async with aiohttp.ClientSession() as session:
        res = await asyncio.gather(upload(files, app.url + '?name=' + basename,
                                   session))

    print(f'All files have been uploaded ({len(res)})')
    print(res.json())

