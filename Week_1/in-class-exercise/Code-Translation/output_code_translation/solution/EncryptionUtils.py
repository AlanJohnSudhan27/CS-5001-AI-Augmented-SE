import string

class EncryptionUtils:
    def __init__(self, key):
        self.key = key

    def caesar_cipher(self, plaintext, shift):
        ciphertext = []
        for ch in plaintext:
            if ch.isalpha():
                ascii_offset = 65 if ch.isupper() else 97
                shifted_char = chr((ch.lower() - 'a' + shift) % 26 + ascii_offset)
                ciphertext.append(shifted_char)
            else:
                ciphertext.append(ch)
        return ''.join(ciphertext)

    def vigenere_cipher(self, plain_text):
        encrypted_text = []
        key_index = 0
        for ch in plain_text:
            if ch.isalpha():
                shift = self.key[key_index % len(self.key)].lower() - 'a'
                encrypted_char = chr((ch.lower() - 'a' + shift) % 26 + ord('a'))
                encrypted_text.append(encrypted_char.upper() if ch.isupper() else encrypted_char)
                key_index += 1
            else:
                encrypted_text.append(ch)
        return ''.join(encrypted_text)

    def rail_fence_cipher(self, plain_text, rails):
        if rails <= 0:
            raise ValueError("Rails must be greater than zero.")
        fence = [[] for _ in range(rails)]
        direction = -1
        row = 0

        for ch in plain_text:
            if row == 0 or row == rails - 1:
                direction = -direction

            fence[row].append(ch)
            row += direction

        encrypted_text = []
        for i in range(rails):
            encrypted_text.extend(fence[i])

        return ''.join(encrypted_text)
