import sys
import re
import json
import os.path
import base64

def convert_bytes_to_mb(size_in_bytes):
    return round(size_in_bytes / (1024 * 1024), 2)

def generate_html(json_file, page_title="File Names and References", footer_file=None):
    # Extract the filename from the JSON file path
    output_filename = os.path.splitext(os.path.basename(json_file))[0] + ".html"

    # Read the JSON file
    with open(json_file, 'r') as f:
        json_data = f.read()

    # Parse the JSON data
    data = json.loads(json_data)

    # Extract the filenames, references, and sizes
    table_rows = ''
    total_size_mb = 0  # New variable to hold the total size in MB
    for obj in data:
        file_value = obj.get('file', '')
        filename = os.path.basename(file_value)
        reference = obj.get('reference', 'Unknown')
        size = obj.get('size', 0)
        total_size_mb += size  # Accumulate the size for total calculation

        link = f'https://pubee.datafund.io/bzz/{reference}'
        table_rows += f'<tr><td>{filename}</td><td><a href="{link}" target="_blank">{reference}</a></td><td style="text-align: right;">{convert_bytes_to_mb(size)}</td></tr>'

    # Embed the thumbnail image into base64 format
    thumbnail_image = ""
    if os.path.exists("thumbnail.png"):
        with open("thumbnail.png", "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
            thumbnail_image = f'<img src="data:image/png;base64,{encoded_image}" alt="Thumbnail Image" style="width: 100%; height: auto;">'

    # Read the content from the footer file
    footer_content = ""
    if footer_file:
        with open(footer_file, 'r') as f:
            footer_content = f.read()

    # Generate the HTML content
    html_content = f'''
    <html>
    <head>
        <title>{page_title}</title>
        <style>
            /* CSS styles go here */
            body {{
                font-family: Arial, sans-serif;
                background-color: #f5f5f5;
                color: #333;
            }}

            h1 {{
                text-align: center;
                color: #007bff;
                margin-top: 30px;
            }}

            table {{
                width: 90%;
                margin: 20px auto;
                border-collapse: collapse;
                background-color: #fff;
                box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
            }}

            table th, table td {{
                border: 1px solid #ddd;
                padding: 10px;
            }}

            table th {{
                background-color: #007bff;
                color: #fff;
                text-align: left;
                font-weight: bold;
            }}

            table td:first-child {{
                color: #007bff;
            }}

            input[type="text"] {{
                width: 90%;
                padding: 12px;
                margin: 20px auto;
                display: block;
                border: 2px solid #007bff;
                border-radius: 5px;
                box-sizing: border-box;
            }}

            input[type="text"]:focus {{
                outline: none;
                border-color: #0056b3;
            }}

            footer {{
                background-color: #007bff;
                color: #fff;
                text-align: center;
                padding: 5px 0;
                width: 100%;
                position: fixed;
                bottom: 0;
            }}
        </style>
        <script>
            function searchFile() {{
                var input, filter, table, tr, td, i, txtValue;
                input = document.getElementById("searchInput");
                filter = input.value.toUpperCase();
                table = document.getElementById("fileTable");
                tr = table.getElementsByTagName("tr");
                for (i = 0; i < tr.length; i++) {{
                    td = tr[i].getElementsByTagName("td")[0];
                    if (td) {{
                        txtValue = td.textContent || td.innerText;
                        if (txtValue.toUpperCase().indexOf(filter) > -1) {{
                            tr[i].style.display = "";
                            return;
                        }} else {{
                            tr[i].style.display = "none";
                        }}
                    }}
                }}
            }}
        </script>
    </head>
    <body>
        {thumbnail_image}
        <h1>{page_title}</h1>
        <input type="text" id="searchInput" onkeyup="searchFile()" placeholder="Search for file names...">
        <table id="fileTable">
            <tr>
                <th>File Name</th>
                <th>Swarm Reference Hash</th>
                <th style="text-align: right;">Size in MB</th>
            </tr>
            {table_rows}
        </table>
        <footer>
            {footer_content}
        </footer>
    </body>
    </html>
    '''

    # Write the HTML content to the output file named after the JSON file
    with open(output_filename, 'w') as f:
        f.write(html_content)

    # Print the HTML generation message along with the total size in MB
    print(f"{output_filename} file has been generated successfully.")
    print(f"Total size of files: {convert_bytes_to_mb(total_size_mb)} MB")

# Check if the JSON file location is provided as an argument
if len(sys.argv) < 2:
    print("Please provide the location of the JSON file as an argument.")
else:
    json_file_location = sys.argv[1]
    page_title = sys.argv[2] if len(sys.argv) >= 3 else "File Names and References"
    footer_file = sys.argv[3] if len(sys.argv) >= 4 else None
    generate_html(json_file_location, page_title, footer_file)
