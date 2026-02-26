class DecryptionUtils:
    def __init__(self, key):
        self.key_ = key

    def caesar_decipher(self, ciphertext, shift):
        shift = shift % 26
        plaintext = []
        for c in ciphertext:
            if c.isalpha():
                base = 'A' if c.isupper() else 'a'
                shifted_char = chr((ord(c) - ord(base) - shift + 26) % 26 + ord(base))
                plaintext.append(shifted_char)
            else:
                plaintext.append(c)
        return ''.join(plaintext)

    def vigenere_decipher(self, ciphertext):
        decrypted_text = []
        key_length = len(self.key_)
        key_index = 0

        for c in ciphertext:
            if c.isalpha():
                shift = ord(self.key_[key_index % key_length].lower()) - ord('a')
                base = 'a' if c.islower() else 'A'
                decrypted_char = chr((ord(c.lower()) - ord('a') - shift + 26) % 26 + ord('a'))
                decrypted_text.append(decrypted_char.upper() if c.isupper() else decrypted_char)
                key_index += 1
            else:
                decrypted_text.append(c)
        return ''.join(decrypted_text)

    def rail_fence_decipher(self, encrypted_text, rails):
        plain_text = []
        n = len(encrypted_text)
        if rails <= 1:
            return encrypted_text

        fence = [['\n' for _ in range(n)] for _ in range(rails)]

        direction = -1
        row = 0
        col = 0

        for _ in range(n):
            if row == 0 or row == rails - 1:
                direction = -direction
            fence[row][col] = '*'
            col += 1
            row += direction

        index = 0
        for r in range(rails):
            for c in range(n):
                if fence[r][c] == '*':
                    fence[r][c] = encrypted_text[index]
                    index += 1

        direction = -1
        row = 0
        col = 0

        for _ in range(n):
            if row == 0 or row == rails - 1:
                direction = -direction
            plain_text.append(fence[row][col])
            col += 1
            row += direction

        return ''.join(plain_text)
