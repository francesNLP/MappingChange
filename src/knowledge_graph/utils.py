import pickle
import random
import string
import regex
def normalize_entity_name(entity_name):
    entity_name = regex.sub(r'[^\p{L}\s\-\'\,\.\’]', '', entity_name)
    entity_name = regex.sub(r'\n', '', entity_name)
    entity_name = string.capwords(entity_name)
    return entity_name

MAX_SIZE_NAMES = 10000000000
name_map = {}
def name_to_uri_name(name):
    """
    Convert a name to a format which will be shown in the uri of a resource. This format (uri name) is digits based,
    which means  a sequence of digits are used to represent the name in the uri. Same name should have the
    same uri name. We later use this ID to construct the URI for the entity. Special characters (such as Greek letters)
    might appear in the name, and uris with such characters are difficult to query, so we need digital ID over names.
    :param name: name of a resource
    :return: string as uri name (digits based).
    """
    if name in name_map:
        return name_map[name]

    name_id = random.randint(0, MAX_SIZE_NAMES)
    while str(name_id) in name_map.values():
        name_id = random.randint(0, MAX_SIZE_NAMES)
    name_map[name] = str(name_id)
    return str(name_id)


def save_name_map(filepath):
    """
    Save the name map into a pickle file, so it can be used to convert names to uri names, thus the form of uri
    can be consistent - same name should have the same uri name.
    :param filepath: where the file will be stored.
    :return:
    """
    with open(filepath, 'wb') as f:
        pickle.dump(name_map, f)


def load_name_map(filepath):
    """
    Load the name map from a pickle file, so it can be used to convert names to uri names, thus the form of uri
    can be consistent - same name should have the same uri name.
    :param filepath: where the file will be stored.
    :return:
    """
    try:
        with open(filepath, 'rb') as f:
            global name_map
            name_map = pickle.load(f)
    except FileNotFoundError:
        print("file not found")
        name_map = {}