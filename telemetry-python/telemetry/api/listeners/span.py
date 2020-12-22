from telemetry import Span
from telemetry.api.trace import SpanListener


class InstrumentorSpanListener(SpanListener):
    """
    A span listener that is only enabled for specific instrumentors
    """
    def __init__(self, delegate: SpanListener, *instrumentors: str):
        self.instrumentors = instrumentors
        self.delegate = delegate

    def enabled(self, span: Span) -> bool:
        for instrumentor in self.instrumentors:
            if span.instrumentor in [f"opentelemetry.instrumentation.{instrumentor}", span.instrumentor == instrumentor]:
                return True
            
        return False

    def on_start(self, span: Span):
        self.delegate.on_start(span)

    def on_end(self, span: Span):
        self.delegate.on_end(span)


class AttributeTagMarker(SpanListener):
    def __init__(self, *attributes: str):
        self.attributes = attributes

    def on_start(self, span: Span):
        span._add_attribute_tags(*self.attributes)
