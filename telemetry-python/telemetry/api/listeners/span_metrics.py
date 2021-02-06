from typing import Optional

import opentelemetry.trace as trace_api
from opentelemetry import context as context_api
from opentelemetry.sdk.metrics import ValueRecorder, Counter
from opentelemetry.sdk.trace import Span, SpanProcessor
from opentelemetry.trace.status import StatusCode

import telemetry
from telemetry.api.helpers.environment import Environment


class SpanMetricsProcessor(SpanProcessor):

    def __init__(self, metrics):
        self.metrics = metrics

    def on_start(self, span: "Span", parent_context: Optional[context_api.Context] = None) -> None:
        """
        Span listener that will:

        1. copy attributes from parent span to
        :param span:
        :param parent_context:
        :return:
        """
        current_span = trace_api.get_current_span(context_api.get_current())

        wrapped_span = telemetry.Span(span)

        if current_span and not isinstance(current_span, trace_api.DefaultSpan):
            # copy parent span's attributes into this span
            for key, value in current_span.attributes.items():
                span.set_attribute(key, value)

        # set/overwrite any span-specific attributes/labels
        wrapped_span.set_attribute('trace.id', str(span.context.trace_id))
        wrapped_span.set_attribute('trace.span_id', str(span.context.span_id))
        wrapped_span.set_attribute('trace.is_remote', span.context.is_remote)
        wrapped_span.set_label('trace.category', wrapped_span.category)
        wrapped_span.set_label(telemetry.Keys.Label.TRACE_NAME, wrapped_span.qname)

        for key, value in Environment.attributes.items():
            wrapped_span.set_attribute(key, value)

        for key, value in Environment.labels.items():
            wrapped_span.set_label(key, value)

        super().on_start(span, parent_context)

    def on_end(self, span: "Span") -> None:
        from telemetry import Keys

        elapsed_ms = int((span.end_time - span.start_time) / 1000000)

        metric = self.metrics._get_metric("trace", f"duration", int, ValueRecorder, unit="ms")
        wrapped_span = telemetry.Span(span)

        labels = wrapped_span.labels

        status = "OK"
        if not span.status.is_ok:
            status = "ERROR"

        labels[Keys.Label.TRACE_STATUS] = status

        metric.record(elapsed_ms, labels=labels)

        if span.status.status_code == StatusCode.ERROR:
            error_counter = self.metrics._get_metric("trace", f"errors", int, Counter)
            error_counter.add(1, labels=labels)

    def shutdown(self) -> None:
        super().shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return super().force_flush(timeout_millis)

