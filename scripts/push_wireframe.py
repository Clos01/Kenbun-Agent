#!/usr/bin/env python3
import sys
import json
import urllib.request
import urllib.error

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 push_wireframe.py <path_to_wireframe_json>")
        sys.exit(1)

    file_path = sys.argv[1]
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        sys.exit(1)

    url = "http://100.92.127.1:3000/api/wireframe"
    
    # Ensure it looks like Excalidraw schema
    if "type" not in data or data["type"] != "excalidraw":
        print("Warning: JSON does not appear to be a valid Excalidraw scene (missing type='excalidraw').")
        
    req = urllib.request.Request(url, method="POST")
    req.add_header('Content-Type', 'application/json')
    
    try:
        response = urllib.request.urlopen(req, data=json.dumps(data).encode('utf-8'))
        if response.status == 200:
            print(f"Successfully pushed wireframe from {file_path} to {url}")
        else:
            print(f"Failed to push wireframe. HTTP Status: {response.status}")
            print(response.read().decode('utf-8'))
    except urllib.error.URLError as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
