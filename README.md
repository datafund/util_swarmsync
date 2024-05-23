# Swarmsync

Swarmsync is a Python script that provides a set of tools for managing files on the Ethereum Swarm network. It allows you to upload, download, check the status of uploaded files, and more. You can also create and manage tags for your uploaded files.

## Features

- Upload files to Ethereum Swarm network
- Download files from Ethereum Swarm network
- Check the status of uploaded files using stewardship
- Create and manage tags for uploaded files
- Encrypt and pin files during upload
- Monitor and send Prometheus statistics
- Generate html file from .json containing download references

## Getting Started

### Prerequisites

- Python 3.8 or higher
- [Bee client](https://docs.ethswarm.org/docs/installation/bee/getting-started/installation/)

### Installation

1. Clone this repository:

   ```bash
   git clone https://github.com/yourusername/swarmsync.git
   cd swarmsync
   ```

2. Install the required Python packages:

   ```bash
   pip install -r requirements.txt
   ```

### Usage

```bash
python3 <path-to-swarmsync.py> <command>
```

```bash
python3 <path-to-generate_html.py> <name-of-json-file> <name-of-footer.txt>
```

#### Show

You can use the `show` command to display information about the files you have uploaded and their status.

```bash
python swarmsync.py show [options]
```

Options:

- `-s, --saved-tag`: Check the existing/stored tag UID.
- `-t, --tag`: Enter a tag UID to fetch information about a specific tag.

#### Download

To download files from the Ethereum Swarm network, use the `download` command. You can specify the number of concurrent tasks and the Bee node URL.

```bash
python swarmsync.py download [options]
```

Options:

- `-c, --count`: Number of concurrent tasks for downloading.
- `-u, --beeurl`: Bee node URL(s) (comma-separated) to connect to.

#### Check

Use the `check` command to check if files are retrievable using stewardship or to check the status of a specific tag.

```bash
python swarmsync.py check [options]
```

Options:

- `-c, --count`: Number of concurrent tasks for checking.
- `-u, --beeurl`: Bee node URL to connect to.

#### Upload

The `upload` command allows you to upload files and folders to the Ethereum Swarm network. You can specify the path to the folder, whether to encrypt the data, and more.

```bash
python swarmsync.py upload [options]
```

Options:

- `-p, --path`: Path to the folder to be uploaded.
- `-s, --search`: Search parameter (e.g., `*`, `*.jpg`, `somename.txt`).
- `-P, --pin`: Should files be pinned during upload.
- `-t, --tag`: Specify a UID tag for the upload.
- `--no-tag`: Disable tagging for the upload.
- `-a, --address`: Enter an Ethereum address or hexadecimal string (64 characters).
- `-E, --encrypt`: Encrypt data during upload.
- `-r, --reupload`: Reupload items that are not retrievable.
- `-d, --deferred`: Sets Swarm deferred upload header to `False`.

#### Mantaray

The `mantaray` command allows you to manage a Mantaray index, which is a way to organize and access your files on the Swarm network.

```bash
python swarmsync.py mantaray [options]
```

Options:

- `-c, --count`: Number of concurrent tasks for uploading the Mantaray index.
- `-u, --beeurl`: Bee node URL(s) (comma-separated) to connect to.

### Examples

- To upload a folder with files and subfolders:

  ```bash
  python swarmsync.py upload -p /path/to/folder
  ```

- To download files from the Ethereum Swarm network:

  ```bash
  python swarmsync.py download -c 5 -u http://yourbeeurl:1633
  ```

- To check the status of uploaded files:

  ```bash
  python swarmsync.py check -c 10 -u http://yourbeeurl:1633
  ```

- To display information about uploaded files and their status:

  ```bash
  python swarmsync.py show responses
  ```

- To create and manage a Mantaray index:

  ```bash
  python swarmsync.py mantaray -u http://yourbeeurl:1633
  ```

### Additional Options

Swarmsync allows you to configure additional options by modifying the script. These options include the Prometheus statistics endpoint, xBee header usage, and more. Please refer to the script's source code for these advanced configurations.

## Generate HTML

If you want to show your set of data available on swarm in which inculdes several files, this tool helps you organize it in a comprehensible way.

```bash
python swarmsync.py [xyz.json] [footer.txt]
```

### Features

- `footer.txt`: after adding the .json fifle, any txt format file can be added to be the footer <br>
- `thumbnail.png`: in the working directory if there's a thumbnail with this specific name, it will be added to the html as full size header

- It will print the exact total size of all the data in megabytes, which can be downloaded.

- The output file name is the same to the .json it was created from

### Example

```bash
➜ python generate_html.py Stack-Exchange-Kiwix.bzz.json
Stack-Exchange-Kiwix.bzz.html file has been generated successfully.
Total size of files: 330160.76 MB
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
