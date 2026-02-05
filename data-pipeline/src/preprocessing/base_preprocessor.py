import re
import unicodedata
from dataclasses import dataclass


@dataclass
class TextStatistics:
    word_count: int
    char_count: int
    sentence_count: int
    avg_word_length: float


class BasePreprocessor:
    
    URL_PATTERN = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    EMAIL_PATTERN = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
    WHITESPACE_PATTERN = re.compile(r'[ \t]+')
    NEWLINE_PATTERN = re.compile(r'\n{3,}')
    
    QUOTE_MAP = {
        '"': '"',
        '"': '"',
        ''': "'",
        ''': "'",
        '«': '"',
        '»': '"',
    }
    
    def normalize_unicode(self, text: str) -> str:
        return unicodedata.normalize('NFC', text)
    
    def replace_urls(self, text: str) -> str:
        return self.URL_PATTERN.sub('<URL>', text)
    
    def replace_emails(self, text: str) -> str:
        return self.EMAIL_PATTERN.sub('<EMAIL>', text)
    
    def standardize_quotes(self, text: str) -> str:
        for fancy, standard in self.QUOTE_MAP.items():
            text = text.replace(fancy, standard)
        return text
    
    def standardize_whitespace(self, text: str) -> str:
        text = self.WHITESPACE_PATTERN.sub(' ', text)
        text = self.NEWLINE_PATTERN.sub('\n\n', text)
        return text.strip()
    
    def compute_statistics(self, text: str) -> TextStatistics:
        words = text.split()
        word_count = len(words)
        char_count = len(text)
        
        sentences = re.split(r'[.!?]+', text)
        sentence_count = len([s for s in sentences if s.strip()])
        
        total_word_chars = sum(len(w) for w in words)
        avg_word_length = total_word_chars / word_count if word_count > 0 else 0.0
        
        return TextStatistics(
            word_count=word_count,
            char_count=char_count,
            sentence_count=sentence_count,
            avg_word_length=round(avg_word_length, 2)
        )
    
    def process(self, text: str) -> str:
        if not text or not isinstance(text, str):
            return ""
        
        text = self.normalize_unicode(text)
        text = self.replace_urls(text)
        text = self.replace_emails(text)
        text = self.standardize_quotes(text)
        text = self.standardize_whitespace(text)
        
        return text
