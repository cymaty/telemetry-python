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
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleExportSpanProcessor, SpanExporter

from telemetry.api.metrics import Metrics, Observer
from telemetry.api.trace import Tracer, SpanKind, Span, SynchronousSpanTracker, SpanListener, Attributes, AttributeValue


def _repo_url():
    """
    When an unexpected bug occurs, we use this repo url in our log messages to instruct where to open a ticket
    """
    return 'https://github.com/alchemy-way/telemetry-python'


class Telemetry(abc.ABC):
    _instance: 'Telemetry' = None

    def __init__(self, span_tracker=None):
        from telemetry.api.otel.meter_provider import ManagedMeterProvider
        from telemetry.api.helpers.environment import Environment

        if span_tracker is None:
            span_tracker = SynchronousSpanTracker()

        self.span_tracker = span_tracker
        self.tracer_provider = TracerProvider(active_span_processor=self.span_tracker)
        self.tracer = Tracer(self.tracer_provider)
        self.meter_provider = ManagedMeterProvider(stateful=False)
        self.metrics = Metrics(self, self.meter_provider)
        self.span_tracker.set_telemetry(self)
        self.environment = Environment()

    def register(self):
        trace_api._TRACER_PROVIDER = None
        metrics_api._METER_PROVIDER = None
        trace_api.set_tracer_provider(self.tracer_provider)
        metrics_api.set_meter_provider(self.meter_provider)

    def initialize(self):
        from telemetry.api.helpers.environment import Environment

        logging.info("Initializing telemetry")

        self.environment = Environment()

        metric_exporters = (os.environ.get('METRICS_EXPORTERS') or '').lower()
        if 'prometheus' in metric_exporters:
            try:
                from telemetry.api.exporter.prometheus import PrometheusMetricsExporter
                self.add_metrics_exporter(PrometheusMetricsExporter())
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

    def add_span_listener(self, span_listener: SpanListener, *instrumentors: str):
        from telemetry.api.listeners.span import InstrumentorSpanListener
        if len(instrumentors) > 0:
            self.span_tracker.add_span_listener(InstrumentorSpanListener(span_listener, *instrumentors))
        else:
            self.span_tracker.add_span_listener(span_listener)

    def add_span_exporter(self, span_exporter: SpanExporter):
        logging.info(f"Added trace exporter: {span_exporter}")
        self.span_tracker.add_span_processor(SimpleExportSpanProcessor(span_exporter))

    def span(self, category: str, name: str,
             attributes: Optional[Attributes] = None,
             tags: Optional[Dict[str, str]] = None,
             kind: SpanKind = SpanKind.INTERNAL) -> Span:
        return self.tracer.span(category, name, attributes=attributes, tags=tags, kind=kind)

    def active_spans(self) -> typing.List[Span]:
        return self.tracer.get_spans()

    @property
    def current_span(self) -> Optional[Span]:
        return self.tracer.current_span

    def counter(self, category: str, name: str, value: typing.Union[int, float] = 1, tags: Dict[str, str] = {},
                unit: str = "1",
                description: Optional[str] = None):
        self.metrics.counter(category, name, value=value, tags=tags, unit=unit, description=description)

    def up_down_counter(self, category: str, name: str, value: typing.Union[int, float] = 1, tags: Dict[str, str] = {},
                unit: str = "1",
                description: Optional[str] = None):
        self.metrics.up_down_counter(category, name, value=value, tags=tags, unit=unit, description=description)

    def record_value(self, category: str, name: str, value: typing.Union[int, float] = 1, tags: Dict[str, str] = {},
                     unit: str = "1",
                     description: Optional[str] = None):
        self.metrics.record_value(category, name, value=value, tags=tags, unit=unit, description=description)

    def gauge(self, category: str, name: str, callback: typing.Callable[[Observer], None],
              unit: str = "1",
              description: Optional[str] = None) -> None:
        self.metrics.gauge(category, name, callback, unit, description)


class TelemetryApi:

    def __init__(self, category: str):
        self.category = category

    def span(self, name: str, attributes: Optional[Attributes] = None, tags: Optional[Dict[str, str]] = None,
             kind: SpanKind = SpanKind.INTERNAL) -> typing.ContextManager[Span]:
        from telemetry import tracer
        
        @contextmanager
        def wrapper():
            with tracer.span(self.category, name, attributes=attributes, tags=tags, kind=kind) as span:
                yield span

        return wrapper()

    def counter(self, name: str, value: int = 1, tags: Dict[str, str] = {}, unit: str = "1", description: Optional[str] = None):
        from telemetry import metrics
        metrics.counter(self.category, name, value=value, tags=tags, unit=unit, description=description)

    def up_down_counter(self, name: str, value: int = 1, tags: Dict[str, str] = {}, unit: str = "1",
                description: Optional[str] = None):
        from telemetry import metrics
        metrics.up_down_counter(self.category, name, value=value, tags=tags, unit=unit, description=description)

    def record_value(self, name: str, value: int = 1, tags: Dict[str, str] = {}, unit: str = "1", description: Optional[str] = None):
        from telemetry import metrics
        metrics.record_value(self.category, name, value=value, tags=tags, unit=unit, description=description)

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


class timed:
    argument_types = (str, int, float, bool, Decimal, Enum)
    none_value = None

    def __init__(self,
                 *args,
                 category: Optional[str] = None,
                 tags: Optional[Dict[str, str]] = None,
                 attributes: Optional[Attributes] = None,
                 argument_tags: Optional[typing.Set[str]] = None,
                 argument_attributes: Optional[typing.Set[str]] = None):

        if len(args) == 1:
            self.function = args[0]
        else:
            self.function = None

        self.signature = None
        self.category = category
        self.tags = tags
        self.attributes = attributes
        self.argument_tags = argument_tags
        self.argument_attributes = argument_attributes

    def __set_name__(self, owner, name):
        self.owner = owner
    
    def __get__(self, instance, owner):
        self.instance = instance
        self.owner = owner
        from functools import partial
        return partial(self.__call__, instance)

    def get_category(self, fn):
        import inspect
        if hasattr(self, 'category') and self.category:
            return self.category
        elif hasattr(self, 'instance') and self.instance:
            if hasattr(self.owner, 'telemetry_category'):
                return getattr(self.owner, 'telemetry_category')
            else:
                return self.instance.__class__.__name__
        elif hasattr(self, 'owner') and self.owner:
            if hasattr(self.owner, 'telemetry_category'):
                return getattr(self.owner, 'telemetry_category')
            else:
                return self.owner.__name__
        else:
            return inspect.getmodule(fn).__name__

    def get_arg_values(self, args, kwargs, fn):
        import inspect

        # initialize with explicitly-passed kwargs
        arg_values = kwargs.copy()

        # resolve the function signature (if not yet resolved)
        if self.signature is None:
            self.signature = inspect.signature(fn)

        def set_arg_value(name: str, value: any):
            # if None value, then set to predefined value of 'none_value'
            if value is None or value is inspect.Parameter.empty:
                arg_values[name] = self.none_value
                return

            # check that this argument is in our allowed list of types
            if type(value) not in self.argument_types:
                raise ValueError(f"Cannot set attribute/tag for argument '{name}' because it's type '{type(value)}' "
                                 f"is not in the allowed list of types.  If you think this type should be allowed, "
                                 f"then please file a bug request at {_repo_url()}")

            # if value is an enum, then extract the name
            if isinstance(value, Enum):
                value = value.name

            arg_values[name] = value

        for i, (name, param) in enumerate(self.signature.parameters.items()):
            if name == 'self' or name in arg_values:
                continue

            # we have positional argument 
            if i < len(args):
                set_arg_value(name, args[i])
            else:
                if param.default:
                    set_arg_value(name, param.default)

        return arg_values

    def wrapped_name(self, fn):
        import inspect

        name = fn.__name__
        if self.owner is not None:
            name = f"{self.owner.__name__}.{name}"
        elif self.instance is not None:
            name = f"{self.instance.__class__.__name__}.{name}"
        else:
            module = inspect.getmodule(fn)
            name = f"{module.__name__}.{name}"
        return name

    def decorate(self, fn):
        from telemetry import telemetry

        def wrapper(*call_args, **call_kwargs):
            with telemetry.tracer.span(self.category or self.get_category(self.function or fn), fn.__name__) as span:
                if self.tags:
                    for k, v in self.tags.items():
                        span.set_tag(k, v)
                if self.attributes:
                    for k, v in self.attributes.items():
                        span.set_attribute(k, v)

                # optimization that checks whether we should extract argument
                if self.argument_attributes or self.argument_tags:
                    # extract argument values
                    arg_values = self.get_arg_values(call_args, call_kwargs, fn)
                    if self.argument_tags:
                        for name in self.argument_tags:
                            if name not in arg_values:
                                logging.warning(
                                    f"@timed call refers to an argument, {name}, that was not found in the signature"
                                    f" for {fn.__name__}! This tag will not be added")
                            else:
                                span.set_tag(name, arg_values[name])

                    if self.argument_attributes:
                        for name in self.argument_attributes:
                            if name not in arg_values:
                                logging.warning(f"@timed call refers to an argument attribute was not found in the "
                                                f"signature for {fn.__name__}! This attribute will not be "
                                                f"added")
                            else:
                                span.set_attribute(name, arg_values[name])

                return fn(*call_args, **call_kwargs)

        return wrapper


    def __call__(self, *args, **kwargs):
        if len(args) == 1 and isinstance(args[0], typing.Callable):
            return self.decorate(args[0])
        else:
            return self.decorate(self.function)(*args, **kwargs)
