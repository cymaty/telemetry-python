# Copyright The OpenTelemetry Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
This library allows export of metrics data to `Prometheus <https://prometheus.io/>`_.

Usage
-----

The **OpenTelemetry Prometheus Exporter** allows export of `OpenTelemetry`_ metrics to `Prometheus`_.


.. _Prometheus: https://prometheus.io/
.. _OpenTelemetry: https://github.com/open-telemetry/opentelemetry-python/

.. code:: python

    from opentelemetry import metrics
    from opentelemetry.exporter.prometheus import PrometheusMetricsExporter
    from opentelemetry.sdk.metrics import Counter, Meter
    from prometheus_client import start_http_server

    # Start Prometheus client
    start_http_server(port=8000, addr="localhost")

    # Meter is responsible for creating and recording metrics
    metrics.set_meter_provider(MeterProvider())
    meter = metrics.get_meter(__name__)
    # exporter to export metrics to Prometheus
    prefix = "MyAppPrefix"
    exporter = PrometheusMetricsExporter(prefix)
    # Starts the collect/export pipeline for metrics
    metrics.get_meter_provider().start_pipeline(meter, exporter, 5)

    counter = meter.create_counter(
        "requests",
        "number of requests",
        "requests",
        int,
        ("environment",),
    )

    # Labels are used to identify key-values that are associated with a specific
    # metric that you want to record. These are useful for pre-aggregation and can
    # be used to store custom dimensions pertaining to a metric
    labels = {"environment": "staging"}

    counter.add(25, labels)
    input("Press any key to exit...")

API
---
"""

import collections
import logging
import re
import os
from typing import Iterable, Optional, Sequence, Union

from opentelemetry.sdk.util.instrumentation import InstrumentationInfo
from prometheus_client.core import (
    REGISTRY,
    CounterMetricFamily,
    SummaryMetricFamily,
    UnknownMetricFamily,
)

from opentelemetry.metrics import Counter, ValueRecorder
from opentelemetry.sdk.metrics.export import (
    ExportRecord,
    MetricsExporter,
    MetricsExportResult,
)
from opentelemetry.sdk.metrics.export.aggregate import MinMaxSumCountAggregator

logger = logging.getLogger(__name__)


class PrometheusMetricsExporter(MetricsExporter):
    """Prometheus metric exporter for OpenTelemetry.

    Args:
        prefix: single-word application prefix relevant to the domain
            the metric belongs to.
    """

    def __init__(self, bind_address: str = os.environ.get('METRICS_PROMETHEUS_BIND_ADDRESS', '0.0.0.0:9102'),
                       prefix: str = os.environ.get('METRICS_PROMETHEUS_PREFIX', ''),
                       start_server: bool = True):

        from prometheus_client import start_http_server

        if ':' not in bind_address:
            bind_address = f"{bind_address}:9091"

        self.prefix = prefix
        self.bind_address = bind_address
        self.collectors = {}

        metrics_bind_address, metrics_port = bind_address.split(':')

        self._collector = CustomCollector(prefix)
        REGISTRY.register(self._collector)

        if start_server:
            start_http_server(port=int(metrics_port), addr=metrics_bind_address)

    def _get_collector(self, instrumentor: InstrumentationInfo) -> 'CustomCollector':
        col = self.collectors.get(instrumentor)
        if not col:
            logger.info(f"Registering collector for: {instrumentor}")
            col = CustomCollector(instrumentor, self.prefix)
            REGISTRY.register(col)
            self.collectors[instrumentor] = col

        return col

    def export(self, export_records: Sequence[ExportRecord]) -> MetricsExportResult:
        collector: Optional[CustomCollector] = None
        for rec in export_records:
            if collector is None or collector.instrumentation_info != rec.instrument.meter.instrumentation_info:
                logging.info(f"Fetching collector for {rec.instrument.meter.instrumentation_info}")
                collector = self._get_collector(rec.instrument.meter.instrumentation_info)
            collector.add_metrics_data(export_records)

        return MetricsExportResult.SUCCESS

    def shutdown(self) -> None:
        REGISTRY.unregister(self._collector)


class CustomCollector:
    """CustomCollector represents the Prometheus Collector object
    https://github.com/prometheus/client_python#custom-collectors
    """

    def __init__(self, instrumentor: InstrumentationInfo, prefix: str = ""):
        self.instrumentation_info = instrumentor
        self._prefix = prefix
        self._metrics_to_export = collections.deque()
        self._non_letters_nor_digits_re = re.compile(
            r"[^\w]", re.UNICODE | re.IGNORECASE
        )

    def add_metrics_data(self, export_records: Sequence[ExportRecord]) -> None:
        self._metrics_to_export.append(export_records)

    def collect(self):
        """Collect fetches the metrics from OpenTelemetry
        and delivers them as Prometheus Metrics.
        Collect is invoked every time a prometheus.Gatherer is run
        for example when the HTTP endpoint is invoked by Prometheus.
        """

        while self._metrics_to_export:
            for export_record in self._metrics_to_export.popleft():
                prometheus_metric = self._translate_to_prometheus(
                    export_record
                )
                if prometheus_metric is not None:
                    yield prometheus_metric

    def _translate_to_prometheus(self, export_record: ExportRecord):
        prometheus_metric = None
        label_values = []
        label_keys = []
        for label_tuple in export_record.labels:
            label_keys.append(self._sanitize(label_tuple[0]))
            label_values.append(label_tuple[1])

        metric_name = ""
        if self._prefix != "":
            metric_name = self._prefix + "_"
        metric_name += self._sanitize(export_record.instrument.name)

        description = getattr(export_record.instrument, "description", "")
        if isinstance(export_record.instrument, Counter):
            prometheus_metric = CounterMetricFamily(
                name=metric_name, documentation=description, labels=label_keys
            )
            prometheus_metric.add_metric(
                labels=label_values, value=export_record.aggregator.checkpoint
            )
        # TODO: Add support for histograms when supported in OT
        elif isinstance(export_record.instrument, ValueRecorder):
            value = export_record.aggregator.checkpoint
            if isinstance(export_record.aggregator, MinMaxSumCountAggregator):
                prometheus_metric = SummaryMetricFamily(
                    name=metric_name,
                    documentation=description,
                    labels=label_keys,
                )
                prometheus_metric.add_metric(
                    labels=label_values,
                    count_value=value.count,
                    sum_value=value.sum,
                )
            else:
                prometheus_metric = UnknownMetricFamily(
                    name=metric_name,
                    documentation=description,
                    labels=label_keys,
                )
                prometheus_metric.add_metric(labels=label_values, value=value)

        else:
            logger.warning(
                "Unsupported metric type. %s", type(export_record.instrument)
            )
        return prometheus_metric

    def _sanitize(self, key: str) -> str:
        """sanitize the given metric name or label according to Prometheus rule.
        Replace all characters other than [A-Za-z0-9_] with '_'.
        """
        return self._non_letters_nor_digits_re.sub("_", key)
