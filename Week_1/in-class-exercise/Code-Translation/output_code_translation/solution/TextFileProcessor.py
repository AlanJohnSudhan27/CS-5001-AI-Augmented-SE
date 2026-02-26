import json
import os

class TextFileProcessor:
    def __init__(self, filename):
        self.filename = filename

    def read_file_as_json(self):
        with open(self.filename, 'r') as file:
            return json.load(file)

    def read_file(self):
        with open(self.filename, 'r') as file:
            return file.read()

    def write_file(self, content):
        with open(self.filename, 'w') as file:
            file.write(content)

    def process_file(self):
        content = self.read_file()
        result = ''.join([c for c in content if c.isalpha()])
        self.write_file(result)
        return result
