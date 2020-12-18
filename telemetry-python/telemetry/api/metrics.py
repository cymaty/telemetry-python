import logging
from typing import Optional, Dict, Type, TypeVar, Callable, Union

import opentelemetry.sdk.metrics as metrics_sdk
from opentelemetry.metrics import Metric, ValueT

from telemetry.api.otel.meter_provider import ManagedMeterProvider

T = TypeVar("T")


class Observer:
    def __init__(self, delegate: metrics_sdk.Observer):
        from telemetry.api.helpers.environment import Environment
        self._delegate = delegate
        self._environment = Environment()

    def observe(self, value: float, labels: Dict[str, str]):
        labels_copy = labels.copy()
        labels_copy.update(self._environment.tags)
        self._delegate.observe(float(value), labels_copy)


class Metrics:

    def __init__(self, telemetry, meter_provider: ManagedMeterProvider):
        from telemetry.api.helpers.environment import Environment
        from telemetry.api import Telemetry

        self._telemetry: Telemetry = telemetry
        self._metrics: Dict[str, Metric] = {}
        self._observers: Dict[str, Observer] = {}
        self._meter_provider: ManagedMeterProvider = meter_provider
        self._environment = Environment()

    def _metric_name(self, category: str, name: str):
        if category is None:
            from telemetry.api.telemetry import _repo_url
            logging.warning(f"Metric category is not set for metric '{name}'!  Please report this as a bug to {_repo_url}")
            return name

        return f"{category}.{name}"

    def _register_observer(self,
                           category: str,
                           name: str,
                           callback: Callable[[metrics_sdk.Observer], None],
                           value_type: Type[ValueT],
                           observer_type: Type[T],
                           unit: str = "1",
                           description: Optional[str] = None):

        meter = self._meter_provider.get_meter(category)
        fqn = f"{category}.{name}"

        if fqn in self._observers:
            return
        else:
            if observer_type == metrics_sdk.ValueObserver:
                observer = meter.register_valueobserver(callback, fqn, description, unit, value_type)
            elif observer_type == metrics_sdk.UpDownSumObserver:
                observer = meter.register_updownsumobserver(callback, fqn, description, unit, value_type)
            elif observer_type == metrics_sdk.SumObserver:
                observer = meter.register_sumobserver(callback, fqn, description, unit, value_type)
            else:
                raise Exception(f"Observer type not implemented: {observer_type}")

            self._observers[fqn] = observer

    def _get_metric(self, category: str, name: str, value_type: Type[ValueT], metric_type: Type[T], unit: str = "1",
                    description: Optional[str] = None) -> T:

        meter = self._meter_provider.get_meter(category)
        fqn = f"{category}.{name}"

        if fqn in self._metrics:
            return self._metrics[fqn]
        else:
            if metric_type == metrics_sdk.Counter:
                metric = meter.create_counter(fqn, description or '', unit=unit, value_type=value_type)
            elif metric_type == metrics_sdk.ValueRecorder:
                metric = meter.create_valuerecorder(fqn, description or '', unit=unit, value_type=value_type)
            elif metric_type == metrics_sdk.UpDownCounter:
                metric = meter.create_updowncounter(fqn, description or '', unit=unit, value_type=value_type)
            else:
                raise Exception(f"Unknown metric type: {metric_type}")

            self._metrics[fqn] = metric

            return metric

    def _merge_tags(self, tags: Dict[str, str]):
        all_tags = self._telemetry.tracer.tags.copy()
        all_tags.update(tags)
        all_tags.update(self._telemetry.environment.tags)
        return all_tags

    def add_exporter(self, exporter: metrics_sdk.MetricsExporter, interval: int):
        self._meter_provider.add_exporter(exporter, interval)

    def counter(self, category: str, name: str, value: Union[int, float] = 1, tags: Dict[str, str] = {},
                unit: str = "1",
                description: Optional[str] = None):
        self._get_metric(category, name, type(value), metrics_sdk.Counter, unit, description)\
            .add(value, self._merge_tags(tags))

    def up_down_counter(self, category: str, name: str, value: Union[int, float] = 1, tags: Dict[str, str] = {},
                unit: str = "1",
                description: Optional[str] = None):
        self._get_metric(category, name, type(value), metrics_sdk.UpDownCounter, unit, description) \
            .add(value, self._merge_tags(tags))


    def record_value(self, category: str, name: str, value: Union[int, float],
                     tags: Dict[str, str] = {},
                     unit: str = "1",
                     description: Optional[str] = None):
        self._get_metric(category, name, type(value), metrics_sdk.ValueRecorder, unit,description)\
            .record(value, self._merge_tags(tags))

    def gauge(self,
              category: str,
              name: str,
              callback: Callable[[Observer], None],
              unit: str = '1',
              description: Optional[str] = None):

        def observer_callback(o: metrics_sdk.Observer):
            callback(Observer(o))

        self._register_observer(category, name, observer_callback, float, metrics_sdk.ValueObserver, unit, description)
