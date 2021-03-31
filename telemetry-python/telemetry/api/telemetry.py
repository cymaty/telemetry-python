import abc
import logging
import os
import typing
from contextlib import contextmanager
from decimal import Decimal
from enum import Enum
from typing import Dict, Optional

from opentelemetry import metrics as metrics_api, trace as trace_api
from opentelemetry.sdk.metrics import MetricsExporter
from opentelemetry.sdk.trace import TracerProvider, SynchronousMultiSpanProcessor, SpanProcessor
from opentelemetry.sdk.trace.export import SimpleExportSpanProcessor, SpanExporter

from telemetry.api import Attribute, Label
from telemetry.api.listeners.span_metrics import SpanMetricsProcessor
from telemetry.api.metrics import Metrics, Observer
from telemetry.api.trace import Tracer, SpanKind, Span, AttributeValue


def _repo_url():
    """
    When an unexpected bug occurs, we use this repo url in our log messages to instruct where to open a ticket
    """
    return 'https://github.com/alchemy-way/telemetry-python'


class Telemetry(abc.ABC):
    _instance: 'Telemetry' = None

    def __init__(self, span_processor=None, stateful: bool = True):

        if span_processor is None:
            span_processor = SynchronousMultiSpanProcessor()
        self.span_processor = span_processor

        self.tracer_provider = TracerProvider(active_span_processor=span_processor)
        self.tracer = Tracer(self.tracer_provider)
        self.metrics = Metrics(self, stateful=stateful)
        self.span_processor.add_span_processor(SpanMetricsProcessor(self.metrics))

    def register(self):
        trace_api._TRACER_PROVIDER = None
        metrics_api._METER_PROVIDER = None
        trace_api.set_tracer_provider(self.tracer_provider)
        metrics_api.set_meter_provider(self.metrics.meter_provider)

    def initialize(self):
        from telemetry.api.helpers.environment import Environment

        # mainly needed for testing where after we mock the environment, we need to refresh this class
        Environment.initialize()

        logging.info(f"Initializing Telemetry API [exporters: ${os.environ.get('METRICS_EXPORTERS')}]")

        metric_exporters = (os.environ.get('METRICS_EXPORTERS') or '').lower()
        if 'prometheus' in metric_exporters:
            try:
                from telemetry.api.exporter.prometheus import PrometheusMetricsExporter
                self.add_metrics_exporter(PrometheusMetricsExporter(), int(os.environ.get('METRICS_INTERVAL', '10')))
            except Exception as ex:
                logging.warning("Prometheus exporter already running, will use existing server")

        if 'console' in metric_exporters:
            from telemetry.api.exporter.console import ConsoleSpanExporter
            self.add_span_exporter(ConsoleSpanExporter())

        self.register()

    def shutdown(self):
        self.tracer.shutdown()
        self.metrics.shutdown()

    def add_metrics_exporter(self, metrics_exporter: MetricsExporter,
                             interval: int = int(os.environ.get('METRICS_INTERVAL', '10'))):
        logging.info(f"Added metrics exporter: {metrics_exporter}")
        self.metrics.add_exporter(metrics_exporter, interval)

    def add_span_listener(self, span_listener: SpanProcessor, *instrumentors: str):
        from telemetry.api.listeners.span import InstrumentorSpanListener
        if len(instrumentors) > 0:
            self.span_processor.add_span_processor(InstrumentorSpanListener(span_listener, *instrumentors))
        else:
            self.span_processor.add_span_processor(span_listener)

    def add_span_exporter(self, span_exporter: SpanExporter):
        logging.info(f"Added trace exporter: {span_exporter}")
        self.span_processor.add_span_processor(SimpleExportSpanProcessor(span_exporter))

    def span(self, category: str, name: str,
             attributes: Optional[typing.Mapping[typing.Union[Attribute, str], AttributeValue]] = None,
             kind: SpanKind = SpanKind.INTERNAL) -> typing.ContextManager[Span]:
        return self.tracer.span(category, name, attributes=attributes, kind=kind)

    @property
    def current_span(self) -> Optional[Span]:
        return self.tracer.current_span

    def counter(self, category: str, name: str, value: typing.Union[int, float] = 1, labels: Dict[typing.Union[Label, str], str] = {},
                unit: str = "1",
                description: Optional[str] = None):
        self.metrics.counter(category, name, value=value, labels=labels, unit=unit, description=description)

    def up_down_counter(self, category: str, name: str, value: typing.Union[int, float] = 1, labels: Dict[typing.Union[Label, str], str] = {},
                        unit: str = "1",
                        description: Optional[str] = None):
        self.metrics.up_down_counter(category, name, value=value, labels=labels, unit=unit, description=description)

    def record_value(self, category: str, name: str, value: typing.Union[int, float] = 1, labels: Dict[typing.Union[Label, str], str] = {},
                     unit: str = "1",
                     description: Optional[str] = None):
        self.metrics.record_value(category, name, value=value, labels=labels, unit=unit, description=description)

    def gauge(self, category: str, name: str, callback: typing.Callable[[Observer], None],
              unit: str = "1",
              description: Optional[str] = None) -> None:
        self.metrics.gauge(category, name, callback, unit, description)


class TelemetryApi:

    def __init__(self, category: str):
        self.category = category

    def span(self, name: str, attributes: Optional[typing.Mapping[Attribute, AttributeValue]] = None,
             kind: SpanKind = SpanKind.INTERNAL) -> typing.ContextManager[Span]:
        from telemetry import tracer

        @contextmanager
        def wrapper():
            with tracer.span(self.category, name, attributes=attributes, kind=kind) as span:
                yield span

        return wrapper()

    def counter(self, name: str, value: int = 1, labels: Dict[typing.Union[Label, str], str] = {}, unit: str = "1", description: Optional[str] = None):
        from telemetry import metrics
        metrics.counter(self.category, name, value=value, labels=labels, unit=unit, description=description)

    def up_down_counter(self, name: str, value: int = 1, labels: Dict[typing.Union[Label, str], str] = {}, unit: str = "1",
                        description: Optional[str] = None):
        from telemetry import metrics
        metrics.up_down_counter(self.category, name, value=value, labels=labels, unit=unit, description=description)

    def record_value(self, name: str, value: int = 1, labels: Dict[typing.Union[Label, str], str] = {}, unit: str = "1", description: Optional[str] = None):
        from telemetry import metrics
        metrics.record_value(self.category, name, value=value, labels=labels, unit=unit, description=description)

    def gauge(self, name: str, callback: typing.Callable[[Observer], None], unit: str = "1", description: Optional[str] = None):
        from telemetry import metrics
        metrics.gauge(self.category, name, callback, unit=unit, description=description)


class TelemetryMixin(object):
    telemetry_category: Optional[str] = None

    def __init_subclass__(cls, **kwargs):
        if cls.telemetry_category is None:
            cls.telemetry_category = f"{cls.__module__}.{cls.__name__}"

    @property
    def telemetry(self) -> TelemetryApi:
        return TelemetryApi(self.telemetry_category)
