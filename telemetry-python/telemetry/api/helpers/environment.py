import os


class Environment:
    tag_prefix = "METRICS_TAG_"
    attrib_prefix = "METRICS_ATTRIBUTE_"

    def __init__(self):
        def parse(prefix):
            out = {}
            for key, value in os.environ.items():
                if key.startswith(prefix):
                    out[key[len(prefix):].lower()] = value
            return out

        self.tags = parse(self.tag_prefix)
        self.attributes = parse(self.attrib_prefix)
