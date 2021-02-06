from typing import Optional

from opentelemetry.context import Context
from opentelemetry.sdk.trace import SpanProcessor, Span
from opentelemetry import context as context_api

from telemetry import Keys


class InstrumentorSpanListener(SpanProcessor):
    """
    A span listener that is only enabled for specific instrumentors
    """
    def __init__(self, delegate: SpanProcessor, *instrumentors: str):
        self.instrumentors = instrumentors
        self.delegate = delegate

    def enabled(self, span: Span) -> bool:
        return span.instrumentation_info.name.replace('opentelemetry.instrumentation.', '') in self.instrumentors

    def on_start(self, span: Span, parent_context: Optional[context_api.Context] = None):
        self.delegate.on_start(span)

    def on_end(self, span: Span):
        self.delegate.on_end(span)


class LabelAttributes(SpanProcessor):
    """
    Will mark specified span attributes as labels
    """
    def __init__(self, *attributes: str):
        self.attributes = attributes

    def on_start(self, span: "trace_sdk.Span", parent_context: Optional[context_api.Context] = None) -> None:
        label_keys = set(span.attributes.get(Keys.Attribute._LABEL_KEYS, ()))
        label_keys.update(self.attributes)
        span.set_attribute(Keys.Attribute._LABEL_KEYS, list(label_keys))



