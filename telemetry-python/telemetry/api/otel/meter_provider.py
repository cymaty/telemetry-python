from typing import Dict

from opentelemetry.metrics import Meter
from opentelemetry.sdk.metrics import MeterProvider, MetricsExporter
from opentelemetry.sdk.resources import Resource


class ManagedMeterProvider(MeterProvider):
    def __init__(self, stateful=True, resource: Resource = Resource.create({}), shutdown_on_exit: bool = True):
        super().__init__(stateful, resource, shutdown_on_exit)
        self._meters: Dict[str, Meter] = {}
        self._exporter_intervals = dict()

    def add_exporter(self, exporter: MetricsExporter, interval: int):
        if exporter not in self._exporters:
            self._exporter_intervals[exporter] = interval
            self._exporters.add(exporter)
            for key, meter in self._meters.items():
                self.start_pipeline(meter, exporter, interval)

    def get_meter(self, instrumenting_module_name: str, instrumenting_library_version: str = "") -> Meter:

        meter = self._meters.get(instrumenting_module_name)
        if meter is None:
            meter = super().get_meter(instrumenting_module_name, instrumenting_library_version)
            self._meters[instrumenting_module_name] = meter

            for exporter in self._exporters:
                interval = self._exporter_intervals[exporter]
                self.start_pipeline(meter, exporter, interval)

        return meter




