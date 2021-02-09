from typing import Mapping, Optional, Callable

from opentelemetry.sdk.trace import Span

class AttributeRegistry:
    def __init__(self):
        self.attributes: Mapping[str, Attribute] = {}
        self.label_keys = set()

    def register(self, a: 'Attribute'):
        if a.name in self.attributes:
            raise Exception(f"Attribute/label '{a.name}' already registered!")
        self.attributes[a.name] = a
        if a.is_label:
            self.label_keys.add(a.name)

    def propagate(self, key: str) -> bool:
        a = self.attributes.get(key)
        if a:
            return a.propagate
        return False

    def is_label(self, key: str) -> bool:
        return key in self.label_keys

    def __getitem__(self, item):
        return self.attributes[item]

    def __iter__(self):
        return self.attributes.values()


_REGISTRY = AttributeRegistry()


class Attribute:
    def __init__(self, name: str, propagate: bool = True, is_label: bool = False, register: bool = True):
        self.name = name
        self.propagate = propagate
        self.is_label = is_label
        if register:
            _REGISTRY.register(self)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.name})"


class Label(Attribute):
    def __init__(self, name: str, propagate: bool = True, register: bool = True):
        super().__init__(name, propagate, True, register)


class Attributes:
    @staticmethod
    def registry() -> AttributeRegistry:
        return _REGISTRY

    @staticmethod
    def propagte(key: str) -> bool:
        if not key:
            return False
        return Attributes.registry().propagate(key)

    @staticmethod
    def is_label(key: str) -> bool:
        if not key:
            return False
        return Attributes.registry().is_label(key)

    _LABEL_KEYS = Attribute('_label_keys')

    ENV = Label('env')
    TRACE_ID = Attribute('trace.id')
    TRACE_SPAN_ID = Attribute('trace.span_id')
    TRACE_IS_REMOTE = Attribute('trace.is_remote')
    TRACE_NAME = Label('span')
    TRACE_CATEGORY = Label('category', False)
    TRACE_STATUS = Label('span_status', False)
    COMPONENT = Label('component', False)

    # Taken from the OpenTelemetry HTTP spec:
    # https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/trace/semantic_conventions/http.md
    HTTP_STATUS_CODE = Label('http.status_code', False)  # HTTP response status code.
    HTTP_METHOD = Label('http.method', False)  # HTTP request method.
    HTTP_ROUTE = Label('http.route', True)  # used when the route or url contains placeholders, eg:  /user/:user_id as they are suitable for labels
    HTTP_TARGET = Label('http.target', False)  # The full request target as passed in a HTTP request line or equivalent.
    HTTP_HOST = Label('http.host', False)  # The value of the HTTP host header. When the header is empty or not present, this attribute should be the same.
    HTTP_SCHEME = Label('http.scheme', False)  # The URI scheme identifying the used protocol.
    HTTP_FLAVOR = Label('http.flavor', False)  # HTTP protocol version number

    HTTP_URL = Attribute('http.url',
                         False)  # Full HTTP request URL in the form scheme://host[:port]/path?query[#fragment]. Usually the fragment is not transmitted over HTTP, but if it is known, it should be included nevertheless.
    HTTP_USER_AGENT = Attribute('http.user_agent', False)  # Value of the HTTP User-Agent header sent by the client.
    HTTP_REQUEST_CONTENT_LENGTH = Attribute('http.request_content_length',
                                            False)  # The size of the request payload body in bytes. This is the number of bytes transferred excluding headers and is often, but not always, present as the Content-Length header.

    GRPC_METHOD = Label('grpc.method', True)  # GRPC method name
    GRPC_PEER = Attribute('grpc.peer', True)  # GRPC peer (client/server host)
    GRPC_STATUS_CODE = Label('grpc.status_code', False)  # GRPC status code
    GRPC_STATUS_DETAILS = Attribute('grpc.status_details', False)  # GRPC status details


class Spans:
    SPAN_DURATION = 'trace.duration'


from telemetry.api.telemetry import Telemetry, TelemetryMixin
from telemetry.api.decorator import trace
