import subprocess
from os.path import dirname, abspath
from lxml import etree

lib_path = dirname(abspath(__file__))


class StanzaMagic(object):
    """
    Simple Stanza Magic to minimize loading time.
    """
    _stanzas = {}

    @classmethod
    def get(cls, lang):
        if lang not in cls._stanzas:
            import stanza
            stanza.download(lang) # download language model
            cls._stanzas[lang] = stanza.Pipeline(lang)
        return cls._stanzas[lang]


def geo_tagging(text):
    nlp = StanzaMagic.get(lang='en')
    doc = nlp(text)
    tagged_tokens = []
    for ent in doc.ents:
        #print(ent.text, ent.type)
        if ent.type == "LOC" or ent.type == "GPE" or ent.type == "FAC":
            toponym = ent.text
            start_index = ent.start_char
            end_index = ent.end_char
            tagged_tokens.append({
                "start": start_index,
                "end": end_index,
                "name": toponym,
            })

    return tagged_tokens


def georesolve_cmd(in_xml, gazetteer, bounding_box):
    georesolve_xml = ''
    atempt = 0
    flag = 1
    if "'" in in_xml:
        in_xml = in_xml.replace("'", "\'\\\'\'")

    cmd = 'printf \'%s\' \'' + in_xml + '\' | ' + lib_path + '/georesolve/scripts/geoground -g ' + gazetteer + ' ' + bounding_box + ' -top'
    while (len(georesolve_xml) < 5) and (atempt < 1000) and (flag == 1):
        proc = subprocess.Popen(cmd.encode('utf-8'), shell=True,
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        if "Error" in str(stderr):
            flag = 0
            print("err: '{}'".format(stderr))
            georesolve_xml = ''
        else:
            if stdout == in_xml:
                georesolve_xml = ''
            else:
                georesolve_xml = stdout
        atempt += 1
    return georesolve_xml


def georesolved_xml_tojson(resolved_xml):
    geo_list = []
    if len(resolved_xml) > 5:
        root = etree.fromstring(resolved_xml)
        for child in root:
            toponymName = child.attrib["name"]
            toponymId = child.attrib["id"]
            startIndex = int(child.attrib["start"])
            endIndex = int(child.attrib["end"])
            latitude = ''
            longitude = ''
            pop = ''
            in_cc = ''
            type = ''
            gazref = ''
            if len(child) >= 1:
                top_child = child[0]
                if "lat" in top_child.attrib:
                    latitude = top_child.attrib["lat"]
                if "long" in top_child.attrib:
                    longitude = top_child.attrib["long"]
                if "pop" in top_child.attrib:
                    pop = top_child.attrib["pop"]
                if "in-cc" in top_child.attrib:
                    in_cc = top_child.attrib["in-cc"]
                if "type" in top_child.attrib:
                    type = top_child.attrib["type"]
                if 'gazref' in top_child.attrib:
                    gazref = top_child.attrib['gazref']
            geo_list.append({
                "name": toponymName,
                "id": toponymId,
                "latitude": latitude,
                "longitude": longitude,
                "gazetteer_ref": gazref,
                "population": pop,
                "in_country": in_cc,
                "feature_type": type,
                "start": startIndex,
                "end": endIndex
            })
    return geo_list