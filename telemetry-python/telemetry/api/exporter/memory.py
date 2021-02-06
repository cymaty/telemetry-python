import threading

import telemetry

import typing
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace import Span


class InMemorySpanExporter(SpanExporter):
    """Implementation of :class:`.SpanExporter` that stores spans in memory.

    This class can be used for testing purposes. It stores the exported spans
    in a list in memory that can be retrieved using the
    :func:`.get_finished_spans` method.
    """

    def __init__(self):
        self._finished_spans = []
        self._stopped = False
        self._lock = threading.Lock()

    def clear(self):
        """Clear list of collected spans."""
        with self._lock:
            self._finished_spans.clear()

    def get_finished_spans(self) -> typing.List[telemetry.Span]:
        """Get list of collected spans."""
        with self._lock:
            return list(map(lambda s: telemetry.Span(s), self._finished_spans))

    def export(self, spans: typing.Sequence[Span]) -> SpanExportResult:
        """Stores a list of spans in memory."""
        if self._stopped:
            return SpanExportResult.FAILURE
        with self._lock:
            self._finished_spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self):
        """Shut downs the exporter.

        Calls to export after the exporter has been shut down will fail.
        """
        self._stopped = True
