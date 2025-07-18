#!/usr/bin/env python3
"""
Simple test server to debug the frontend without FastAPI dependencies
"""
import http.server
import socketserver
import os
from pathlib import Path

class TestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.path = '/static/index.html'
        elif self.path.startswith('/static/'):
            # Serve static files from the static directory
            self.path = self.path[7:]  # Remove '/static' prefix
        
        return super().do_GET()
    
    def do_POST(self):
        # For debugging POST requests
        print(f"POST request to {self.path}")
        print(f"Content-Type: {self.headers.get('Content-Type')}")
        print(f"Content-Length: {self.headers.get('Content-Length')}")
        
        # Simple response for testing
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"job_id": "test123", "status": "pending"}')

if __name__ == "__main__":
    PORT = 8000
    
    # Change to the project directory
    os.chdir('/Users/mitchellcurrie/Projects/image2plug')
    
    with socketserver.TCPServer(("", PORT), TestHandler) as httpd:
        print(f"Test server running at http://localhost:{PORT}")
        print("Press Ctrl+C to stop")
        httpd.serve_forever()