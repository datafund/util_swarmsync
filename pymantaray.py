#!/usr/bin/env python3
# encoding: utf-8

import json
import hashlib
import os
from typing import List, Dict, Tuple, Set

class Entry:
    def __init__(self, file, reference, decrypt, size, sha256, content_type):
        self.file = file
        self.reference = reference
        self.decrypt = decrypt
        self.size = size
        self.sha256 = sha256
        self.content_type = content_type

    def to_dict(self):
        return {
            "file": self.file,
            "reference": self.reference,
            "decrypt": self.decrypt,
            "size": self.size,
            "sha256": self.sha256,
            "content-type": self.content_type
        }

class MantarayIndex:
    def __init__(self, index_file=None):
        self.index = set()
        self.index_file = index_file or 'mantaray.json'
        self.index = self.load_index()

    def load_index(self) -> Dict:
        if os.path.isfile(self.index_file):
            with open(self.index_file, 'r') as f:
                index_data = json.load(f)
                for entry_data in index_data.values():
                    # Add a default value of None for the content_type key if it is missing
                    entry_data.setdefault('content_type', "application/octet-stream")
                return index_data
        else:
            return {}

    def save_index(self):
        with open(self.index_file, 'w') as f:
            json.dump(self.index, f)

    def add_entry(self, entry: Dict):
        entry_hash = self._get_entry_hash(entry)
        self.index[entry_hash] = entry

    def get_entry(self, entry_hash: str) -> Dict:
        return self.index.get(entry_hash)

    def get_entries(self):
        entries = []
        for entry in self.index.values():
            entries.append(Entry(entry['file'], entry['reference'], entry['decrypt'], entry['size'], entry['sha256'], entry['content-type']))
        return entries

    def delete_entry(self, entry_hash: str):
        if entry_hash in self.index:
            del self.index[entry_hash]
            self.save_index()

    def search(self, query: Dict) -> List[Tuple[str, Dict]]:
        results = []
        for entry_hash, entry in self.index.items():
            for key, value in query.items():
                if key not in entry or entry[key] != value:
                    break
            else:
                results.append((entry_hash, entry))
        return results

    def _get_entry_hash(self, entry: Dict) -> str:
        data = json.dumps(entry, sort_keys=True).encode()
        return hashlib.sha3_256(data).hexdigest()

    def __len__(self):
        return len(self.index)

    def get_existing_references(self) -> List[Dict]:
        entries = []
        if 'entries' in self.index:
            for entry_hash in self.index['entries']:
                entry = self.get_entry(entry_hash)
                if entry and 'reference' in entry:
                    entries.append(entry)
        return entries

class MantarayIndexHTMLGenerator:
    def __init__(self, index_file_path, output_html_path, baseurl=''):
        self.index_file_path = index_file_path
        self.output_html_path = output_html_path
        self.baseurl = baseurl

    def generate(self):
        with open(self.index_file_path, "r") as index_file:
            index_data = index_file.read()
    
        with open(self.output_html_path, 'w') as f:
            f.write('<html>\n<head>\n<title>Swarmsync Index</title>\n')
            f.write('</head>\n<body>\n')
            f.write('<style>\n')
            f.write('body {\n')
            f.write('  background: #000 url("https://gateway.fairdatasociety.org/bzz/7c824651b2d82281944830fc0b261f10d26dbbd5b24efa8f030f55d8e5c2e1ef/") repeat center center scroll;\n')
            f.write('  background-size: cover;\n')
            f.write('  font-family: monospace;\n')
            f.write('  color: #fff;\n')
            f.write('}\n')
            f.write('.background {\n')
            f.write('  position: fixed;\n')
            f.write('  z-index: -1;\n')
            f.write('  top: 0;\n')
            f.write('  left: 0;\n')
            f.write('  width: 100%;\n')
            f.write('  height: 100%;\n')
            f.write('  background: #000 url("https://gateway.fairdatasociety.org/bzz/7c824651b2d82281944830fc0b261f10d26dbbd5b24efa8f030f55d8e5c2e1ef/") repeat center center scroll;\n')
            f.write('  background-size: cover;\n')
            f.write('}\n')
            f.write('h1 {\n')
            f.write('  text-align: center;\n')
            f.write('}\n')
            f.write('ul {\n')
            f.write('  list-style: none;\n')
            f.write('  padding: 0;\n')
            f.write('  margin: 0;\n')
            f.write('}\n')
            f.write('li {\n')
            f.write('  padding: 10px 0;\n')
            f.write('}\n')
            f.write('a {\n')
            f.write('  color: #fff;\n')
            f.write('  text-decoration: none;\n')
            f.write('}\n')
            f.write('.hidden {\n')
            f.write('  display: none;\n')
            f.write('}\n')
            f.write('input, button {\n')
            f.write('  font-family: monospace;\n')
            f.write('}\n')
            f.write('.index {\n')
            f.write('}\n')
            f.write('.show .index {\n')
            f.write('  display: block;\n')
            f.write('}\n')
            f.write('#container {\n')
            f.write('  background-color: transparent;\n')
            f.write('}\n')
            f.write('#indexContainer {\n')
            f.write('  position: relative;\n')
            f.write('  z-index: 1;\n')
            f.write('  opacity: 0.8;\n')
            f.write('}\n')
            f.write('#spinner {\n')
            f.write('  background-color: transparent;\n')
            f.write('  background: transparent;\n')
            f.write('  position: absolute;\n')
            f.write('  top: 50%;\n')
            f.write('  left: 50%;\n')
            f.write('  transform: translate(-50%, -50%);\n')
            f.write('  z-index: 9999;\n')
            f.write('}\n')
            f.write('#spinner img {\n')
            f.write('  background-color: transparent;\n')
            f.write('}\n')
            f.write('#search {n')
            f.write('  display: inline-block;n')
            f.write('  margin-left: 10px;n')
            f.write('  font-family: monospace;n')
            f.write('  padding: 5px 10px;n')
            f.write('  border-radius: 5px;n')
            f.write('  border: none;n')
            f.write('  background-color: #fff;n')
            f.write('  color: #000;n')
            f.write('  cursor: pointer;n')
            f.write('}n')
            f.write('</style>\n')
            f.write('</head>\n')
            f.write('<div id="spinner" style="display: none">\n')
            f.write('  <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" style="margin: auto; display: block; shape-rendering: auto; animation-play-state: running; animation-delay: 0s;" width="200px" height="200px" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid">\n')
            f.write('    <path d="M19 50A31 31 0 0 0 81 50A31 36.3 0 0 1 19 50" fill="#ff9d00" stroke="none" style="animation-play-state: running; animation-delay: 0s;">\n')
            f.write('      <animateTransform attributeName="transform" type="rotate" dur="0.27472527472527475s" repeatCount="indefinite" keyTimes="0;1" values="0 50 52.65;360 50 52.65" style="animation-play-state: running; animation-delay: 0s;"/>\n')
            f.write('    </path>\n')
            f.write('  </svg>\n')
            f.write('</div>\n')

            f.write('<div class="background"></div>\n')
            
            f.write('<h1><a href="#show">Swarmsync Index</a></h1>\n')
            f.write('<input type="text" id="uri-input" onkeyup="searchEntries()" placeholder="Enter file URI...">\n')
            f.write('<button onclick="openFileByUri()">Open File</button>\n')
    
            f.write('<div id="indexContainer" class="index hidden">\n')

            f.write('<ul>\n')
    
            for entry in json.loads(index_data).values():
                uri = entry['file']
                size = entry['size']
                reference = entry['reference']
                sha256 = entry['sha256']
                decrypt_key = entry['decrypt']
                if decrypt_key is not None:
                    reference = reference + decrypt_key
                f.write(f'<li><a href="#" onclick="loadFileByReference(\'{reference}\')">{uri}</a> ({size} bytes, sha256={sha256})</li>\n')
            f.write('</ul>\n')
    
            f.write('<script>\n')
            f.write('const mantarayData = ' + index_data + ';\n')
    
            f.write('function getUriToReference(data) {\n')
            f.write('  const uriToReference = {};\n')
            f.write('  for (const entry of Object.values(data)) {\n')
            f.write('    let reference = entry.reference;\n')
            f.write('    if (entry.decrypt) {\n')
            f.write('      const decryptKey = entry.decrypt;\n')
            f.write('      reference = `${reference}${decryptKey}`;\n')
            f.write('    }\n')
            f.write('    uriToReference[entry.file] = reference;\n')
            f.write('  }\n')
            f.write('  return uriToReference;\n')
            f.write('}\n')
            
            f.write('const uriToReference = getUriToReference(mantarayData);\n')
            
            f.write('function loadFileByReference(reference, uri) {\n')
            f.write('  var xhr = new XMLHttpRequest();\n')
            f.write('  xhr.open("GET", window.location.origin + "/bzz/" + reference + "/", true);\n')

            f.write('  xhr.responseType = "blob";\n')
            f.write('  const spinner = document.getElementById("spinner");\n')
            f.write('  spinner.style.display = "block";\n')
            f.write('  xhr.onload = function (event) {\n')
            f.write('    var blob = xhr.response;\n')
            f.write('    var url = URL.createObjectURL(blob);\n')
            f.write('    var viewer = window.open(url, "_blank");\n')
            f.write('    viewer.onload = function () {\n')
            f.write('      URL.revokeObjectURL(url);\n')
            f.write('      viewer.document.body.style.background =\n')
            f.write('        "#000 url(\'https://gateway.fairdatasociety.org/bzz/7c824651b2d82281944830fc0b261f10d26dbbd5b24efa8f030f55d8e5c2e1ef/\') repeat center center scroll";\n')
            f.write('      viewer.document.body.style.backgroundSize = "cover";\n')
            f.write('      viewer.document.body.style.backgroundPosition = "center center";\n')
            f.write('      spinner.style.display = "none";\n')
            f.write('    };\n')
            f.write('  };\n')
            f.write('  xhr.send();\n')
            f.write('  if (uri && uri.includes("#")) {\n')
            f.write('    window.location.hash = "#" + encodeURIComponent(uri.split("#")[1]);\n')
            f.write('  } else {\n')
            f.write('    window.location.hash = "";\n')
            f.write('  }\n')
            f.write('  if (!reference) {\n')
            f.write('    alert("File not found: " + uri);\n')
            f.write('  }\n')
            f.write('}\n')
            
            f.write('function openFileByUri() {\n')
            f.write('  const uriInput = document.getElementById("uri-input");\n')
            f.write('  const uri = uriInput.value || decodeURIComponent(window.location.hash.slice(1));\n')
            f.write('  \n')
            f.write('  if (uri === "show") {\n')
            f.write('    document.querySelector(".index").classList.toggle("hidden");\n')
            f.write('    return;\n')
            f.write('  }\n')
            f.write('\n')
            f.write('  const reference = uriToReference[uri];\n')
            f.write('  \n')
            f.write('  if (!uri || typeof uri !== "string") {\n')
            f.write('    return;\n')
            f.write('  }\n')
            f.write('\n')
            f.write('  if (reference) {\n')
            f.write('    loadFileByReference(reference, uri);\n')
            f.write('  } else {\n')
            f.write('    // check if input value is a search query\n')
            f.write('    const filter = uri.toUpperCase();\n')
            f.write('    const ul = document.getElementById("indexContainer");\n')
            f.write('    const li = ul.getElementsByTagName("li");\n')
            f.write('    let matchFound = false;\n')
            f.write('\n')
            f.write('    for (let i = 0; i < li.length; i++) {\n')
            f.write('      const a = li[i].getElementsByTagName("a")[0];\n')
            f.write('      const textValue = a.textContent || a.innerText;\n')
            f.write('\n')
            f.write('      if (textValue.toUpperCase().indexOf(filter) > -1) {\n')
            f.write('        li[i].style.display = "";\n')
            f.write('        if (!matchFound) {\n')
            f.write('          matchFound = true;\n')
            f.write('        }\n')
            f.write('      } else {\n')
            f.write('        li[i].style.display = "none";\n')
            f.write('      }\n')
            f.write('    }\n')
            f.write('\n')
            f.write('    if (!matchFound) {\n')
            f.write('      alert("File not found: " + uri);\n')
            f.write('    }\n')
            f.write('  }\n')
            f.write('}\n')

            f.write('function toggleIndexVisibility() {\n')
            f.write('  const indexContainer = document.getElementById("indexContainer");\n')
            f.write('  const show = window.location.hash === "#show";\n')
            f.write('\n')
            f.write('  if (show) {\n')
            f.write('    indexContainer.style.display = "block";\n')
            f.write('    indexContainer.style.background = "#000 url(\'https://gateway.fairdatasociety.org/bzz/7c824651b2d82281944830fc0b261f10d26dbbd5b24efa8f030f55d8e5c2e1ef/\') repeat center center scroll";\n')
            f.write('    indexContainer.style.backgroundSize = "cover";\n')
            f.write('    indexContainer.addEventListener("click", function (event) {\n')
            f.write('      event.stopPropagation();\n')
            f.write('    });\n')
            f.write('  } else {\n')
            f.write('    indexContainer.style.display = "none";\n')
            f.write('    indexContainer.removeEventListener("click", function (event) {\n')
            f.write('      event.stopPropagation();\n')
            f.write('    });\n')
            f.write('  }\n')
            f.write('  indexContainer.style.position = show ? "" : "absolute";\n')
            f.write('  indexContainer.style.visibility = show ? "" : "hidden";\n')
            f.write('}\n')

            f.write('function searchEntries() {\n')
            f.write('  const input = document.getElementById("uri-input");\n')
            f.write('  const filter = input.value.toUpperCase();\n')
            f.write('  const ul = document.getElementById("indexContainer");\n')
            f.write('  const li = ul.getElementsByTagName("li");\n')
            f.write('  let matchFound = false;\n')
            f.write('\n')
            f.write('  for (let i = 0; i < li.length; i++) {\n')
            f.write('    const a = li[i].getElementsByTagName("a")[0];\n')
            f.write('    const textValue = a.textContent || a.innerText;\n')
            f.write('    if (textValue.toUpperCase().indexOf(filter) > -1) {\n')
            f.write('      li[i].style.display = "";\n')
            f.write('      if (!matchFound) {\n')
            f.write('        a.addEventListener("click", function (event) {\n')
            f.write('          event.preventDefault();\n')
            f.write('          input.value = a.getAttribute("data-href");\n')
            f.write('          loadFileByReference(a.getAttribute("data-href"));\n')
            f.write('        });\n')
            f.write('        matchFound = true;\n')
            f.write('      }\n')
            f.write('    } else {\n')
            f.write('      li[i].style.display = "none";\n')
            f.write('    }\n')
            f.write('  }\n')
            f.write('}\n')
            f.write('window.addEventListener("load", toggleIndexVisibility);\n')
            f.write('window.addEventListener("hashchange", toggleIndexVisibility, false);\n')
            f.write('window.addEventListener("load", openFileByUri);\n')
            f.write('window.addEventListener("hashchange", openFileByUri, false);\n')

            f.write('</script>\n</body>\n</html>\n')
    
        print(f"Generated index file {self.output_html_path}")

