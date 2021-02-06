import logging
from typing import Optional, Dict, Type, TypeVar, Callable, Union

import opentelemetry.sdk.metrics as metrics_sdk
from opentelemetry.metrics import Metric, ValueT

from telemetry.api.exporter.environment import EnvironmentMetricsDecorator
from telemetry.api.otel.meter_provider import ManagedMeterProvider

T = TypeVar("T")


class Observer:
    def __init__(self, delegate: metrics_sdk.Observer):
        self._delegate = delegate

    def observe(self, value: float, labels: Dict[str, str]):
        self._delegate.observe(float(value), labels)


class Metrics:

    def __init__(self, telemetry, name: str = "default", stateful: bool = True):
        from telemetry.api import Telemetry

        self.meter_provider = ManagedMeterProvider(stateful=stateful)
        self._telemetry: Telemetry = telemetry
        self._metrics: Dict[str, Metric] = {}
        self._observers: Dict[str, Observer] = {}
        self._meter = self.meter_provider.get_meter(name)
        self.name = name

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

        fqn = f"{category}.{name}"

        if fqn in self._observers:
            return
        else:
            if observer_type == metrics_sdk.ValueObserver:
                observer = self._meter.register_valueobserver(callback, fqn, description, unit, value_type)
            elif observer_type == metrics_sdk.UpDownSumObserver:
                observer = self._meter.register_updownsumobserver(callback, fqn, description, unit, value_type)
            elif observer_type == metrics_sdk.SumObserver:
                observer = self._meter.register_sumobserver(callback, fqn, description, unit, value_type)
            else:
                raise Exception(f"Observer type not implemented: {observer_type}")

            self._observers[fqn] = observer

    def _get_metric(self, category: str, name: str, value_type: Type[ValueT], metric_type: Type[T], unit: str = "1",
                    description: Optional[str] = None) -> T:

        fqn = f"{category}.{name}"

        if fqn in self._metrics:
            return self._metrics[fqn]
        else:
            if metric_type == metrics_sdk.Counter:
                metric = self._meter.create_counter(fqn, description or '', unit=unit, value_type=value_type)
            elif metric_type == metrics_sdk.ValueRecorder:
                metric = self._meter.create_valuerecorder(fqn, description or '', unit=unit, value_type=value_type)
            elif metric_type == metrics_sdk.UpDownCounter:
                metric = self._meter.create_updowncounter(fqn, description or '', unit=unit, value_type=value_type)
            else:
                raise Exception(f"Unknown metric type: {metric_type}")

            self._metrics[fqn] = metric

            return metric

    def _merge_labels(self, labels: Dict[str, str]):
        all_labels = self._telemetry.tracer.labels.copy()
        all_labels.update(labels)
        return all_labels

    def add_exporter(self, exporter: metrics_sdk.MetricsExporter, interval: int):
        wrapped = EnvironmentMetricsDecorator(exporter)
        self.meter_provider.add_exporter(wrapped, interval)

    def counter(self, category: str, name: str, value: Union[int, float] = 1, labels: Dict[str, str] = {},
                unit: str = "1",
                description: Optional[str] = None):
        self._get_metric(category, name, type(value), metrics_sdk.Counter, unit, description)\
            .add(value, self._merge_labels(labels))

    def up_down_counter(self, category: str, name: str, value: Union[int, float] = 1, labels: Dict[str, str] = {},
                unit: str = "1",
                description: Optional[str] = None):
        self._get_metric(category, name, type(value), metrics_sdk.UpDownCounter, unit, description) \
            .add(value, self._merge_labels(labels))


    def record_value(self, category: str, name: str, value: Union[int, float],
                     labels: Dict[str, str] = {},
                     unit: str = "1",
                     description: Optional[str] = None):
        self._get_metric(category, name, type(value), metrics_sdk.ValueRecorder, unit,description)\
            .record(value, self._merge_labels(labels))

    def gauge(self,
              category: str,
              name: str,
              callback: Callable[[Observer], None],
              unit: str = '1',
              description: Optional[str] = None):

        def observer_callback(o: metrics_sdk.Observer):
            callback(Observer(o))

        self._register_observer(category, name, observer_callback, float, metrics_sdk.ValueObserver, unit, description)

    def shutdown(self):
        self.meter_provider.shutdown()
