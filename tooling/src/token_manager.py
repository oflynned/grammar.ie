import re

class TokenManager:
    def __init__(self):
        self.tokens = {}
        self.counter = 0

    def tokenise(self, text):
        """
        Finds all <ga>...</ga> content, stores it, and replaces it with __IRISH_N__.
        """
        def replace_match(match):
            original_text = match.group(1) # The text inside the tag
            token_id = f"__IRISH_{self.counter}__"
            self.tokens[token_id] = original_text
            self.counter += 1
            return token_id

        # Regex to find <ga>content</ga>
        # We replace the WHOLE tag with just the token
        return re.sub(r'<ga>(.*?)</ga>', replace_match, text, flags=re.DOTALL)

    def restore(self, text):
        """
        Finds __IRISH_N__ tokens and swaps them back to the final Astro syntax.
        """
        for token_id, original_text in self.tokens.items():
            text = text.replace(token_id, original_text)
        return text