import string
import regex


def normalize_name(name):
    name = regex.sub(r'[^\p{L}\s\-\'\,\.\’]', '', name)
    name = regex.sub(r'\n', '', name)
    name = string.capwords(name)
    return name