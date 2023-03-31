#!/usr/bin/env python3
# encoding: utf-8

import json
import hashlib
import os
from typing import List, Dict, Tuple, Set

class Entry:
    def __init__(self, file, reference, size, sha256, content_type):
        self.file = file
        self.reference = reference
        self.size = size
        self.sha256 = sha256
        self.content_type = content_type

    def to_dict(self):
        return {
            "file": self.file,
            "reference": self.reference,
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
            entries.append(Entry(entry['file'], entry['reference'], entry['size'], entry['sha256'], entry['content-type']))
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
            f.write('<h1>Swarmsync Index</h1>\n')
            f.write('<input id="uri-input" type="text" placeholder="Enter file URI" />\n')
            f.write('<button onclick="openFileByUri()">Open File</button>\n')
            f.write('<ul>\n')
    
            for entry in json.loads(index_data).values():
                uri = entry['file']
                size = entry['size']
                reference = entry['reference']
    
                f.write(f'<li><a href="#" onclick="loadFileByReference(\'{reference}\')">{uri}</a> ({size} bytes, reference={reference})</li>\n')
            f.write('</ul>\n')
    
            f.write('<script>\n')
            f.write('const mantarayData = ' + index_data + ';\n')
    
            f.write('function getUriToReference(data) {\n')
            f.write('  const uriToReference = {};\n')
            f.write('  for (const entry of Object.values(data)) {\n')
            f.write('    uriToReference[entry.file] = entry.reference;\n')
            f.write('  }\n')
            f.write('  return uriToReference;\n')
            f.write('}\n')
    
            f.write('const uriToReference = getUriToReference(mantarayData);\n')
    
            f.write('function loadFileByReference(reference) {\n')
            f.write('  var xhr = new XMLHttpRequest();\n')
            f.write('  xhr.open("GET", window.location.origin + "/bzz/" + reference + "/", true);\n')
            f.write('  xhr.responseType = "blob";\n')
            f.write('  xhr.onload = function(event) {\n')
            f.write('    var blob = xhr.response;\n')
            f.write('    var url = URL.createObjectURL(blob);\n')
            f.write('    var viewer = window.open(url, "_blank");\n')
            f.write('    viewer.onload = function() {\n')
            f.write('      URL.revokeObjectURL(url);\n')
            f.write('    };\n')
            f.write('  };\n')
            f.write('  xhr.send();\n')
            f.write('}\n')
    
            f.write('function openFileByUri() {\n')
            f.write('  const uriInput = document.getElementById("uri-input");\n')
            f.write('  const uri = uriInput.value;\n')
            f.write('  const reference = uriToReference[uri];\n')
    
            f.write('  if (reference) {\n')
            f.write('    loadFileByReference(reference);\n')
            f.write('  } else {\n')
            f.write('    alert("File not found: " + uri);\n')
            f.write('  }\n')
            f.write('}\n')
    
            f.write('</script>\n</body>\n</html>\n')
    
        print(f"Generated index file {self.output_html_path}")

