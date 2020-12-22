import os


class Environment:
    tag_prefix = "METRICS_TAG_"
    attrib_prefix = "METRICS_ATTRIBUTE_"
    tag_variables = {
        'METRICS_APP_NAME': 'app.name',
        'METRICS_APP_VERSION': 'app.version',
    }

    def __init__(self):
        def parse(prefix):
            out = {}
            for key, value in os.environ.items():
                if key in self.tag_variables:
                    out[self.tag_variables[key]] = value
                elif key.startswith(prefix):
                    out[key[len(prefix):].lower()] = value
            return out

        self.tags = parse(self.tag_prefix)
        self.attributes = parse(self.attrib_prefix)
