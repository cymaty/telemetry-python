import enum
import logging
import re
from contextlib import contextmanager
from threading import RLock
from typing import Dict, Optional, Union, Sequence, Mapping, ContextManager

import opentelemetry.sdk.trace as trace_sdk
import opentelemetry.trace as trace_api
from opentelemetry.trace import SpanKind as OTSpanKind

from telemetry.api import Attribute, _REGISTRY, Attributes, Label

AttributeValue = Union[
    str,
    bool,
    int,
    float,
    Sequence[Union[None, str]],
    Sequence[Union[None, bool]],
    Sequence[Union[None, int]],
    Sequence[Union[None, float]],
]

class SpanContext:
    def __init__(self, trace_id: str, span_id: str, trace_state: Dict[str, str]):
        self.trace_id = trace_id
        self.span_id = span_id
        self.trace_state = trace_state

class SpanStatus(enum.Enum):
    OK = 0
    UNSET = 1
    ERROR = 2

class SpanKind(enum.Enum):
    """Specifies additional details on how this span relates to its parent span.

    Note that this enumeration is experimental and likely to change. See
    https://github.com/open-telemetry/opentelemetry-specification/pull/226.
    """

    #: Default value. Indicates that the span is used internally in the
    # application.
    INTERNAL = 0

    #: Indicates that the span describes an operation that handles a remote
    # request.
    SERVER = 1

    #: Indicates that the span describes a request to some remote service.
    CLIENT = 2

    #: Indicates that the span describes a producer sending a message to a
    #: broker. Unlike client and server, there is usually no direct critical
    #: path latency relationship between producer and consumer spans.
    PRODUCER = 3

    #: Indicates that the span describes a consumer receiving a message from a
    #: broker. Unlike client and server, there is usually no direct critical
    #: path latency relationship between producer and consumer spans.
    CONSUMER = 4

    @classmethod
    def to_otel_span_kind(cls, span_kind: 'SpanKind') -> OTSpanKind:
        return OTSpanKind[span_kind.name]


class Span:
    _ATTRIBUTE_NAME_PATTERN = re.compile('_*[a-zA-Z0-9_.\\-]+')

    # used to track valid attribute keys so that we can skip validation after it's first seen
    _attribute_key_cache = set()

    def __init__(self, span: trace_sdk.Span):
        assert isinstance(span, trace_sdk._Span), f'unexpected Span type: {type(span)}'
        self._span = span

    @property
    def context(self) -> SpanContext:
        return SpanContext(
            str(self._span.context.trace_id),
            str(self._span.context.span_id),
            self._span.context.trace_state
        )

    @property
    def status(self) -> SpanStatus:
        if self._span.status.is_unset:
            return SpanStatus.UNSET
        elif self._span.status.is_ok:
            return SpanStatus.OK
        else:
            return SpanStatus.ERROR
            
    @property
    def name(self) -> str:
        return self._span.name

    @property
    def category(self) -> str:
        return self._span.attributes.get(Attributes.TRACE_CATEGORY.name, self._span.instrumentation_info.name.replace('opentelemetry.instrumentation.', ''))

    @property
    def qname(self) -> str:
        """
        Returns the qualified name of the span {category}.{name}
        :return: qualified name
        """
        return f"{self.category}.{self.name}"

    def set(self, attribute_or_label: Attribute, value: AttributeValue):
        """
        Set's an Attribute or Label value
        :param attribute_or_label: instance of Attribute (or Label) to set
        :param value: Attribute or Label value
        :return: None
        """
        if attribute_or_label is None:
            raise Exception(f"Attribute or Label cannot be None!")

        if not isinstance(attribute_or_label, Attribute):
            raise Exception(f"Expected Attribute or Label, but got a {attribute_or_label.__class__.__name__} ({attribute_or_label}) instead")

        if attribute_or_label.is_label:
            self.set_label(attribute_or_label.name, str(value))
        else:
            self.set_attribute(attribute_or_label.name, value)

    def set_attribute(self, name: str, value: AttributeValue) -> 'Span':
        # to boost performance, we track valid attribute names in this cache (shared across all instances).
        # The first time an attribute key is seen, we'll validate it and then add it to the cache so that we can skip
        # validation the next time we encounter it.
        if not isinstance(name, str):
            raise Exception("Attribute name must be a string!")

        if name not in self._attribute_key_cache:
            if not isinstance(name, str):
                logging.warning(f"attribute/label name must be a string! (name={name})")
            elif not self._ATTRIBUTE_NAME_PATTERN.fullmatch(name):
                logging.warning(f"attribute/label name must match the pattern: {self._ATTRIBUTE_NAME_PATTERN.pattern} (name={name})")
            else:
                if len(self._attribute_key_cache) > 1000:
                    logging.warning("Over 1000 attribute names have been cached. This should be investigated and the"
                                    "size warning should be increased if this is a valid use-case!")
                self._attribute_key_cache.add(name)

        if value is not None:
            self._span.set_attribute(name, value)
            
        return self

    def set_label(self, name: str, value: str) -> 'Span':
        if not isinstance(name, str):
            raise Exception("label name must be a string!")

        if not isinstance(value, str):
            logging.warning(f"label value for must be a string! (name={name}, value={value})")
        else:
            self.set_attribute(name, value)
            # mark this attribute as a label
            label_keys = set(self._span.attributes.get(Attributes._LABEL_KEYS.name, ()))
            label_keys.add(name)
            self._span.set_attribute(Attributes._LABEL_KEYS.name, list(label_keys))

        return self

    def add_event(self, name: str, attributes: Mapping[str, AttributeValue]) -> 'Span':
        self._span.add_event(name, attributes)
        return self

    def end(self):
        self._span.end()

    @property
    def attributes(self) -> Mapping[str, AttributeValue]:
        """
        Return all (public) attributes
        """
        return {k: v for k, v in self._span.attributes.items() if not k.startswith('_')}

    @property
    def labels(self) -> Dict[str, str]:
        label_keys = set(self._span.attributes.get(Attributes._LABEL_KEYS.name, list()))
        return {key: value for key, value in self.attributes.items() if key in label_keys or _REGISTRY.is_label(key)}

    def events(self):
        return self._span.events


class Tracer:
    def __init__(self, tracer_provider: trace_sdk.TracerProvider, name: str = "default"):
        self.name = name
        self._lock = RLock()
        self._tracer_provider = tracer_provider

    def set(self, attribute_or_label: Attribute, value: AttributeValue) -> 'Tracer':
        if self.has_active_span():
            self.current_span.set(attribute_or_label, value)
        return self

    def set_attribute(self, name: str, value: AttributeValue) -> 'Tracer':
        if self.has_active_span():
            self.current_span.set_attribute(name, value)
        return self

    def set_label(self, name: str, value: str) -> 'Tracer':
        if self.has_active_span():
            self.current_span.set_label(name, value)
        return self

    def add_event(self, name: str, attributes: Mapping[str, AttributeValue]) -> 'Tracer':
        if self.has_active_span():
            self.current_span.add_event(name, attributes)
        return self

    def has_active_span(self):
        return trace_api.get_current_span() != trace_api.INVALID_SPAN

    @property
    def attributes(self) -> Mapping[str, AttributeValue]:
        if not self.has_active_span():
            return {}
        return self.current_span.attributes or {}

    @property
    def labels(self) -> Dict[str, str]:
        output = {}
        if not self.has_active_span():
            return output

        return self.current_span.labels

    @property
    def current_span(self) -> Optional[Span]:
        if not self.has_active_span():
            return None

        return Span(trace_api.get_current_span())

    def span(self, category: str,
             name: str,
             attributes: Optional[Mapping[Attribute, AttributeValue]] = None,
             kind: SpanKind = SpanKind.INTERNAL) -> ContextManager[Span]:

        from opentelemetry import trace

        @contextmanager
        def wrapper():
            nonlocal name, attributes, kind

            if not attributes:
                attributes = {}

            tracer = trace.get_tracer(category, tracer_provider=self._tracer_provider)

            try:
                attributes_copy = {}
                attributes_copy[Attributes.TRACE_CATEGORY.name] = category
                for key, value in attributes.items():
                    if isinstance(key, str):
                        attributes_copy[key] = value
                    else:
                        attributes_copy[key.name] = value

                with tracer.start_as_current_span(name=name, attributes=attributes_copy, kind=SpanKind.to_otel_span_kind(kind)) as span:
                    wrapped_span = Span(span)

                    # set passed attributes
                    for a, value in attributes.items():
                        wrapped_span.set(a, value)

                    yield wrapped_span

            finally:
                pass

        return wrapper()

    def shutdown(self):
        self._tracer_provider.shutdown()
