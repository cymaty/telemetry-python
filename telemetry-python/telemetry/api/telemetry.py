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
        """
        NOTE: Applications should instead call `initialize()`, which will call this method on the application's behalf.

        Registers this Telemetry instance as the default, global instance.
        If an existing instance was registered, it will be replaced.
        :return: None
        """
        trace_api._TRACER_PROVIDER = None
        metrics_api._METER_PROVIDER = None
        trace_api.set_tracer_provider(self.tracer_provider)
        metrics_api.set_meter_provider(self.metrics.meter_provider)

    def initialize(self):
        """
        Initializes this Telemetry instance and registers it as the new global instance.

        The initialization process includes:
        - Configure default attributes/tags from environment variables.  See py:class:: telemetry.api.helpers.environment.Environment
        - Configure metrics/trace exporters from the `METRICS_EXPORTERS` environment variable.
          - prometheus: exports metrics for scraping by Prometheus by starting an HTTP server on port 9102 (default)
          - console: logs metrics to console
        - Registers this instance as the global telemetry instance
        :return: None
        """
        from telemetry.api.helpers.environment import Environment

        logging.info(f"Initializing Telemetry API [exporters: ${os.environ.get('METRICS_EXPORTERS')}]")

        # mainly needed for testing where after we mock the environment, we need to refresh this class
        Environment.initialize()

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
        """
        Shut down this telemetry instance
        :return: None
        """
        self.tracer.shutdown()
        self.metrics.shutdown()

    def add_metrics_exporter(self, metrics_exporter: MetricsExporter,
                             interval: int = int(os.environ.get('METRICS_INTERVAL', '10'))):
        """
        Adds a metrics exporter
        :param metrics_exporter: the exporter instance
        :param interval: interval that metrics should be aggregated into.
        :return: None
        """
        logging.info(f"Added metrics exporter: {metrics_exporter}")
        self.metrics.add_exporter(metrics_exporter, interval)

    def add_span_processor(self, span_processor: SpanProcessor, *instrumentors: str):
        """
        Adds a span processor that will be called for each span's start/end.

        :param span_processor: the span processor
        :param instrumentors: one or more instrumentors to limit the processor to.  If not specified, will be called for all instrumentors.
        :return: None
        """
        from telemetry.api.listeners.span import InstrumentorSpanListener
        if len(instrumentors) > 0:
            self.span_processor.add_span_processor(InstrumentorSpanListener(span_processor, *instrumentors))
        else:
            self.span_processor.add_span_processor(span_processor)

    def add_span_exporter(self, span_exporter: SpanExporter):
        """
        Adds a span exporter that will be called to export completed spans.
        :param span_exporter: the span exporter
        :return: None
        """
        logging.info(f"Added trace exporter: {span_exporter}")
        self.span_processor.add_span_processor(SimpleExportSpanProcessor(span_exporter))

    def span(self, category: str, name: str,
             attributes: Optional[typing.Mapping[typing.Union[Attribute, str], AttributeValue]] = None,
             kind: SpanKind = SpanKind.INTERNAL) -> typing.ContextManager[Span]:
        """
        Creates a new span.  Typically used as a context manager like this:
        ```
        with span(...) as span:
            # do something
        ```

        Span data can be exported in two forms:
            - metrics (eg: call count and sum of duration of all calls)
            - traces

        :param category: the category to associate with the span
        :param name: the short name of the span (we be appended to the category when exporting the full span name)
        :param attributes: a dict of attribute/label instances to their values.
        :param kind: the span kind (eg: CLIENT, SERVER, etc).  Defaults to INTERNAL
        :return: the new `Span` instance (wrapped in a `ContextManager`)
        """
        return self.tracer.span(category, name, attributes=attributes, kind=kind)

    @property
    def current_span(self) -> Optional[Span]:
        """
        Returns the current span (if one is active)
        :return: current Span or None
        """
        return self.tracer.current_span

    def counter(self, category: str, name: str, value: typing.Union[int, float] = 1, labels: Dict[typing.Union[Label, str], str] = {},
                unit: str = "1",
                description: Optional[str] = None):
        """
        Increments a counter value

        :param category: the metric's category
        :param name: the metric's short name within the category
        :param value: the value to add to the counter
        :param labels: labels to attach to this counter value
        :param unit: units to associate with this counter
        :param description: human-readable description for this metric
        :return: None
        """
        self.metrics.counter(category, name, value=value, labels=labels, unit=unit, description=description)

    def up_down_counter(self, category: str, name: str, value: typing.Union[int, float] = 1, labels: Dict[typing.Union[Label, str], str] = {},
                        unit: str = "1",
                        description: Optional[str] = None):
        """
        Increments/decrements a counter value

        :param category: the metric's category
        :param name: the metric's short name within the category
        :param value: value to add to the counter.  May be negative.
        :param labels: labels to attach to this counter value
        :param unit: units to associate with this counter
        :param description: human-readable description for this metric
        :return: None
        """
        self.metrics.up_down_counter(category, name, value=value, labels=labels, unit=unit, description=description)

    def record_value(self, category: str, name: str, value: typing.Union[int, float] = 1, labels: Dict[typing.Union[Label, str], str] = {},
                     unit: str = "1",
                     description: Optional[str] = None):
        """
        Records a numeric value.  When exported, two metrics will be written:
        - <metric fqdn>_count: how many values were recorded in the metric interval
        - <metric fqdn>_sum: the sum of all the values recorded in the metric interval

        :param category: the metric's category
        :param name: the metric's short name within the category
        :param value: the value to record.
        :param labels: labels to attach to this counter value
        :param unit: units to associate with this counter
        :param description: human-readable description for this metric
        :return: None
        """
        self.metrics.record_value(category, name, value=value, labels=labels, unit=unit, description=description)

    def gauge(self, category: str, name: str, callback: typing.Callable[[Observer], None],
              unit: str = "1",
              description: Optional[str] = None) -> None:
        """
        Calls the given callback for to allow recording the current value of something for each metric collection interval.

        Example:

        ```
        telemetry.gauge("category1", "gauge1", lambda observer: observer.observe(get_some_value(), labels: {...}))
        ```

        :param category: the metric's category
        :param name: the metric's short name within the category
        :param callback: the value to record.
        :param unit: units to associate with this counter
        :param description: human-readable description for this metric
        :return: None
        """
        self.metrics.gauge(category, name, callback, unit, description)


class TelemetryApi:

    def __init__(self, category: str):
        self.category = category

    def span(self, name: str, attributes: Optional[typing.Mapping[Attribute, AttributeValue]] = None,
             kind: SpanKind = SpanKind.INTERNAL) -> typing.ContextManager[Span]:
        """
        Creates a new span.  Typically used as a context manager like this:
        ```
        with span(...) as span:
            # do something
        ```

        Span data can be exported in two forms:
            - metrics (eg: call count and sum of duration of all calls)
            - traces

        :param name: the short name of the span (we be appended to the category when exporting the full span name)
        :param attributes: a dict of attribute/label instances to their values.
        :param kind: the span kind (eg: CLIENT, SERVER, etc).  Defaults to INTERNAL
        :return:
        """

        from telemetry import tracer

        @contextmanager
        def wrapper():
            with tracer.span(self.category, name, attributes=attributes, kind=kind) as span:
                yield span

        return wrapper()

    def counter(self, name: str, value: int = 1, labels: Dict[typing.Union[Label, str], str] = {}, unit: str = "1", description: Optional[str] = None):
        """
        Increments a counter value

        :param name: the metric's short name within the category
        :param value: the value to add to the counter
        :param labels: labels to attach to this counter value
        :param unit: units to associate with this counter
        :param description: human-readable description for this metric
        :return: None
        """
        from telemetry import metrics
        metrics.counter(self.category, name, value=value, labels=labels, unit=unit, description=description)

    def up_down_counter(self, name: str, value: int = 1, labels: Dict[typing.Union[Label, str], str] = {}, unit: str = "1",
                        description: Optional[str] = None):
        """
        Increments/decrements a counter value

        :param name: the metric's short name within the category
        :param value: value to add to the counter.  May be negative.
        :param labels: labels to attach to this counter value
        :param unit: units to associate with this counter
        :param description: human-readable description for this metric
        :return: None
        """
        from telemetry import metrics
        metrics.up_down_counter(self.category, name, value=value, labels=labels, unit=unit, description=description)

    def record_value(self, name: str, value: int = 1, labels: Dict[typing.Union[Label, str], str] = {}, unit: str = "1", description: Optional[str] = None):
        """
        Records a numeric value.  When exported, two metrics will be written:
        - <metric fqdn>_count: how many values were recorded in the metric interval
        - <metric fqdn>_sum: the sum of all the values recorded in the metric interval

        :param name: the metric's short name within the category
        :param value: the value to record.
        :param labels: labels to attach to this counter value
        :param unit: units to associate with this counter
        :param description: human-readable description for this metric
        :return: None
        """
        from telemetry import metrics
        metrics.record_value(self.category, name, value=value, labels=labels, unit=unit, description=description)

    def gauge(self, name: str, callback: typing.Callable[[Observer], None], unit: str = "1", description: Optional[str] = None):
        """
        Calls the given callback for to allow recording the current value of something for each metric collection interval.

        Example:

        ```
        telemetry.gauge("category1", "gauge1", lambda observer: observer.observe(get_some_value(), labels: {...}))
        ```

        :param name: the metric's short name within the category
        :param callback: the value to record.
        :param unit: units to associate with this counter
        :param description: human-readable description for this metric
        :return: None
        """
        from telemetry import metrics
        metrics.gauge(self.category, name, callback, unit=unit, description=description)


class TelemetryMixin(object):
    """
    Can be mixed-in to an existing class to provide access to telemetry methods with a shared category value.

    Telemetry methods are accessed through the `self.telemetry` field.

    The telemetry category will default to the fully-qualified class name, but it can also be overridden by setting the
    `telemetry_category` class field to a custom category value.
    """
    telemetry_category: Optional[str] = None

    def __init_subclass__(cls, **kwargs):
        if cls.telemetry_category is None:
            cls.telemetry_category = f"{cls.__module__}.{cls.__name__}"

    @property
    def telemetry(self) -> TelemetryApi:
        return TelemetryApi(self.telemetry_category)
