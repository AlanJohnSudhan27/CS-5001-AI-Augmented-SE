class URLHandler:
    def __init__(self, url):
        self.url = url

    def get_scheme(self):
        scheme_end = self.url.find("://")
        if scheme_end != -1:
            return self.url[:scheme_end]
        return ""

    def get_host(self):
        scheme_end = self.url.find("://")
        if scheme_end != -1:
            url_without_scheme = self.url[scheme_end + 3:]
            host_end = url_without_scheme.find("/")
            if host_end != -1:
                return url_without_scheme[:host_end]
            return url_without_scheme
        return ""

    def get_path(self):
        scheme_end = self.url.find("://")
        if scheme_end != -1:
            url_without_scheme = self.url[scheme_end + 3:]
            host_end = url_without_scheme.find("/")
            if host_end != -1:
                return url_without_scheme[host_end:]
        return ""

    def get_query_params(self):
        params = {}
        query_start = self.url.find("?")
        fragment_start = self.url.find("#")
        if query_start != -1:
            query_string = self.url[query_start + 1:fragment_start] if fragment_start != -1 else self.url[query_start + 1:]
            if query_string:
                pos = 0
                while pos < len(query_string):
                    next_pos = query_string.find("&", pos)
                    if next_pos == -1:
                        next_pos = len(query_string)
                    token = query_string[pos:next_pos]
                    equal_pos = token.find("=")
                    if equal_pos != -1:
                        key = token[:equal_pos]
                        value = token[equal_pos + 1:]
                        params[key] = value
                    pos = next_pos + 1
        return params

    def get_fragment(self):
        fragment_start = self.url.find("#")
        if fragment_start != -1:
            return self.url[fragment_start + 1:]
        return ""
