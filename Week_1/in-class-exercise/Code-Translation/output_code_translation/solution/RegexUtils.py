import re

class RegexUtils:
    def match(self, pattern, text):
        return bool(re.search(pattern, text))

    def findall(self, pattern, text):
        return re.findall(pattern, text)

    def split(self, pattern, text):
        result = re.split(pattern, text)
        if not text:
            return result
        if result and result[0] != text:
            result.append("")
        return result

    def sub(self, pattern, replacement, text):
        return re.sub(pattern, replacement, text)

    def generate_email_pattern(self):
        return r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"

    def generate_phone_number_pattern(self):
        return r"\b\d{3}-\d{3}-\d{4}\b"

    def generate_split_sentences_pattern(self):
        return r"[.!?][\s]{1,2}(?=[A-Z])"

    def split_sentences(self, text):
        pattern = self.generate_split_sentences_pattern()
        sentences = self.split(pattern, text)
        if sentences and not sentences[0]:
            sentences.pop(0)
        if sentences and not sentences[-1]:
            sentences.pop()
        return sentences

    def validate_phone_number(self, phone_number):
        pattern = self.generate_phone_number_pattern()
        return self.match(pattern, phone_number)

    def extract_email(self, text):
        pattern = self.generate_email_pattern()
        return self.findall(pattern, text)
