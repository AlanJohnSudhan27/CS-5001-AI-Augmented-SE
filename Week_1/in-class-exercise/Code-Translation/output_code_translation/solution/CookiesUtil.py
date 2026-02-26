import json
import os

class CookiesUtil:
    def __init__(self, cookiesFile):
        self.cookies_file = cookiesFile
        self.cookies = {}

    def get_cookies(self, response):
        if "cookies" in response:
            self.cookies = response["cookies"]
        self._save_cookies()

    def load_cookies(self):
        cookiesData = {}
        if os.path.exists(self.cookies_file):
            try:
                with open(self.cookies_file, 'r') as file:
                    cookiesData = json.load(file)
            except Exception as e:
                print(f"Error reading JSON file: {e}")
        return cookiesData

    def _save_cookies(self):
        cookiesJson = self.cookies
        try:
            with open(self.cookies_file, 'w') as file:
                json.dump(cookiesJson, file, indent=4)
            return True
        except Exception as e:
            print(f"Error writing JSON file: {e}")
            return False

    def set_cookies(self, request):
        oss = []
        for key, value in self.cookies.items():
            if oss:
                oss.append("; ")
            oss.append(f"{key}={value}")
        request["cookies"] = "".join(oss)
