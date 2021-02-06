import os


class Environment:
    label_prefix = "METRICS_label_"
    attrib_prefix = "METRICS_ATTRIBUTE_"
    label_variables = {
        'METRICS_APP_NAME': 'app.name',
        'METRICS_APP_VERSION': 'app.version',
    }

    labels = {}
    attributes = {}

    @classmethod
    def initialize(cls):
        def parse(prefix):
            out = {}
            for key, value in os.environ.items():
                if key in cls.label_variables:
                    out[cls.label_variables[key]] = value
                elif key.startswith(prefix):
                    out[key[len(prefix):].lower()] = value
            return out

        cls.labels = parse(cls.label_prefix)
        cls.attributes = parse(cls.attrib_prefix)

    @classmethod
    def _clear(cls):
        """
        Should only be called from tests!
        """
        cls.labels = {}
        cls.attributes = {}
