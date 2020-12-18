import enum
import logging
import threading
import re
from contextlib import contextmanager
from threading import RLock
from typing import Dict, Optional, List, Callable, Union, Sequence, Mapping, ContextManager

import opentelemetry.sdk.metrics as metrics_sdk
import opentelemetry.sdk.trace as trace_sdk
import opentelemetry.trace as trace_api
from opentelemetry import context as context_api
from opentelemetry.trace import SpanKind as OTSpanKind, Status
from opentelemetry.trace.status import StatusCode

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
Attributes = Optional[Mapping[str, AttributeValue]]


class SpanListener:
    def enabled(self, span: 'Span') -> bool:
        return True

    def on_start(self, span: 'Span'):
        pass

    def on_end(self, span: 'Span'):
        pass


class SpanTracker(trace_sdk.SpanProcessor):

    def __init__(self):
        from telemetry import Metrics, Tracer

        self._tracer: Tracer = None
        self._metrics: Metrics = None
        self._span_processors = []
        self._active_spans = {}
        self._lock = threading.RLock()
        self._span_listeners = []
        super().__init__()

    def set_telemetry(self, telemetry):
        self._telemetry = telemetry

    def add_span_listener(self, listener: SpanListener):
        self._span_listeners.append(listener)

    def remove_span_listener(self, listener: SpanListener):
        self._span_listeners.remove(listener)

    @property
    def telemetry(self):
        if self._telemetry is None:
            raise Exception("Telemetry is not set!  You must initialize this instance with a call to set_telemetry!")
        return self._telemetry

    def get_span(self, span_id: int) -> trace_sdk.Span:
        return self._active_spans.get(span_id)

    def on_start(self, span: "trace_sdk.Span", parent_context: Optional[context_api.Context] = None) -> None:

        with self._lock:
            self._active_spans[span.get_span_context().span_id] = span

        wrapped_span = Span(span)

        # handles attribute propagation from outer spans to inner spans
        # TODO: opentelemetry has a propagation mechanism, could that be used instead?
        for s in self.telemetry.tracer.get_spans():
            if s.attributes:
                for key, value in s.attributes.items():
                    if key not in span.attributes:
                        wrapped_span.set_attribute(key, value)

        for name, value in self.telemetry.environment.attributes.items():
            wrapped_span.set_attribute(name, value)

        for name, value in self.telemetry.environment.tags.items():
            wrapped_span.set_tag(name, value)

        super().on_start(span, parent_context)

        for span_listener in self._span_listeners:
            span_listener.on_start(wrapped_span)

    def on_end(self, span: "trace_sdk.Span") -> None:
        if span.status.is_unset:
            if span.end_time is None:
                raise Exception("End time not set on span!")
            span.status = Status(status_code=StatusCode.OK)

        wrapped_span = Span(span)
        for span_listener in self._span_listeners:
            span_listener.on_end(wrapped_span)

        super().on_end(span)

        elapsed_ms = int((span.end_time - span.start_time) / 1000000)
        category = span.instrumentation_info.name.replace('opentelemetry.instrumentation.', '')
        metric = self._telemetry.metrics._get_metric(category, f"{span.name}.duration", int, metrics_sdk.ValueRecorder, unit="ms")

        tags = wrapped_span.tags

        metric.record(elapsed_ms, labels=tags)

        with self._lock:
            if span.get_span_context().span_id not in self._active_spans:
                logging.warning(f"Existing span could not be cleaned up: {span.context.span_id}")

            self._active_spans.pop(span.get_span_context().span_id)


class SynchronousSpanTracker(SpanTracker, trace_sdk.SynchronousMultiSpanProcessor):
    pass


class ConcurrentSpanTracker(SpanTracker, trace_sdk.ConcurrentMultiSpanProcessor):
    pass


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
    def to_ot_span_kind(cls, span_kind: 'SpanKind') -> OTSpanKind:
        return OTSpanKind[span_kind.name]


class Span:
    _ATTRIBUTE_NAME_PATTERN = re.compile('_*[a-zA-Z0-9_.\\-]+')

    # used to track valid attribute keys so that we can skip validation after it's first seen
    _attribute_key_cache = set()

    def __init__(self, span: trace_sdk.Span):
        assert isinstance(span, trace_sdk._Span), f'unexpected Span type: {type(span)}'

        self._span = span

    @property
    def name(self) -> str:
        return self._span.name

    @property
    def qname(self) -> str:
        return f"{self.instrumentor}.{self.name}"

    @property
    def instrumentor(self) -> str:
        return self._span.instrumentation_info.name

    def set_attribute(self, name: str, value: AttributeValue) -> 'Span':
        # to boost performance, we track valid attribute names in this cache (shared across all instances).
        # The first time an attribute key is seen, we'll validate it and then add it to the cache so that we can skip
        # validation the next time we encounter it.
        if name not in self._attribute_key_cache:
            if not isinstance(name, str):
                logging.warning(f"attribute/tag name must be a string! (name={name})")
            elif not self._ATTRIBUTE_NAME_PATTERN.fullmatch(name):
                logging.warning(f"attribute/tag name must match the pattern: {self._ATTRIBUTE_NAME_PATTERN.pattern} (name={name})")
            else:
                if len(self._attribute_key_cache) > 1000:
                    logging.warning("Over 1000 attribute names have been cached. This should be investigated and the"
                                    "size warning should be increased if this is a valid use-case!")
                self._attribute_key_cache.add(name)

        if value is not None:
            self._span.set_attribute(name, value)
            
        return self

    def set_tag(self, name: str, value: str) -> 'Span':
        if not isinstance(value, str):
            logging.warning(f"Tag value for must be a string! (name={name}, value={value})")
        else:
            self.set_attribute(name, value)
            self.add_attribute_tags(name)
            
        return self

    def add_attribute_tags(self, *names: str):
        from telemetry.api import _TAG_ATTRIBUTES_KEY
        tag_attributes = list(self.attributes.get(_TAG_ATTRIBUTES_KEY, ()))

        for name in names:
            if name not in tag_attributes:
                tag_attributes.append(name)
        self.set_attribute(_TAG_ATTRIBUTES_KEY, tag_attributes)

    def add_event(self, name: str, attributes: Attributes) -> 'Span':
        self._span.add_event(name, attributes)
        return self

    def end(self):
        self._span.end()

    @property
    def attributes(self) -> Attributes:
        attributes = {}
        for key, value in (self._span.attributes or {}).items():
            attributes[key] = value

        if not self._span.status.is_unset:
            attributes['span.status'] = self._span.status.status_code.name
            attributes['span.description'] = self._span.status.description
            attributes['span.kind'] = self._span.kind.name

        return attributes

    @property
    def tags(self) -> Dict[str, str]:
        from telemetry.api import _TAG_ATTRIBUTES_KEY

        tags = {}
        attributes_as_tags = set(self.attributes.get(_TAG_ATTRIBUTES_KEY, ()))
        attributes_as_tags.add('span.status')

        for key in attributes_as_tags:
            if key in self.attributes:
                # tags values must be a string
                tags[key] = str(self.attributes[key])

        return tags

    def events(self):
        return self._span.events


class Tracer:
    def __init__(self, tracer_provider: trace_sdk.TracerProvider, name: str = "default"):
        if not isinstance(tracer_provider._active_span_processor, SpanTracker):
            raise Exception(f"Whoco telemetry requires that you use an instance of SynchronousSpanTracker or "
                            f"ConcurrentSpanTracker for the TracerProvider.active_span_processor, but instead we got "
                            f"an instance of '{tracer_provider._active_span_processor.__class__.__name__}'")

        self.name = name
        self._lock = RLock()
        self._tracer_provider = tracer_provider
        self._span_tracker: SpanTracker = tracer_provider._active_span_processor

    def set_attribute(self, name: str, value: AttributeValue) -> 'Tracer':
        if self.has_active_span():
            self.current_span.set_attribute(name, value)
        return self

    def set_tag(self, name: str, value: str) -> 'Tracer':
        if self.has_active_span():
            self.current_span.set_tag(name, value)
        return self

    def add_event(self, name: str, attributes: Attributes) -> 'Tracer':
        if self.has_active_span():
            self.current_span.add_event(name, attributes)
        return self

    def get_span(self, span_id: int) -> Optional[Span]:
        return Span(self._span_tracker.get_span(span_id))

    def get_spans(self) -> List[Span]:

        def walk_spans(current: Optional[Span], visit: Callable[[Span], None]):
            if not current:
                return
            visit(current)
            parent = current._span.parent
            if parent and parent.span_id != trace_api.INVALID_SPAN:
                parent = self._span_tracker.get_span(parent.span_id)
                if parent:
                    walk_spans(Span(parent), visit)

        spans = []

        walk_spans(self.current_span, lambda span: spans.append(span))

        return spans

    def has_active_span(self):
        return trace_api.get_current_span() != trace_api.INVALID_SPAN

    @property
    def attributes(self) -> Attributes:
        if not self.has_active_span():
            return {}
        return self.current_span.attributes or {}

    @property
    def tags(self) -> Dict[str, str]:
        output = {}
        if not self.has_active_span():
            return output

        return self.current_span.tags

    @property
    def current_span(self) -> Optional[Span]:
        if not self.has_active_span():
            return None

        return Span(trace_api.get_current_span())

    def span(self, category: str,
             name: str,
             attributes: Optional[Attributes] = None,
             tags: Optional[Dict[str, str]] = None,
             kind: SpanKind = SpanKind.INTERNAL) -> ContextManager[Span]:

        from opentelemetry import trace

        @contextmanager
        def wrapper():
            nonlocal name, attributes, kind, tags

            if attributes is None:
                attributes = {}


            tracer = trace.get_tracer(category, tracer_provider=self._tracer_provider)

            with tracer.start_as_current_span(name=name,
                                              attributes=attributes,
                                              kind=SpanKind.to_ot_span_kind(kind)) as span:
                wrapped_span = Span(span)
                if tags:
                    for name, value in tags.items():
                        wrapped_span.set_tag(name, value)
                yield wrapped_span

        return wrapper()
