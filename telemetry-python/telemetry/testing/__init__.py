from dataclasses import field, dataclass
from logging import LogRecord
from typing import Callable, Iterator, Dict, Optional, List, Type, Union

import pytest
from _pytest.logging import LogCaptureFixture
from opentelemetry.sdk.metrics import PushController, Counter, ValueRecorder, ValueObserver, UpDownCounter
from opentelemetry.sdk.metrics.export import ExportRecord
from opentelemetry.sdk.metrics.export.in_memory_metrics_exporter import InMemoryMetricsExporter

from telemetry import Telemetry, Span
from telemetry.api.exporter.memory import InMemorySpanExporter
from telemetry.api.logger.json import JsonLogFormatter
from telemetry.api.trace import Attributes


@dataclass
class CounterInfo:
    name: str
    value: Union[int, float]
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class ValueRecorderInfo:
    name: str
    min: Union[int, float]
    max: Union[int, float]
    sum: Union[int, float]
    count: int
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class GaugeInfo:
    name: str
    min: Union[int, float]
    max: Union[int, float]
    sum: Union[int, float]
    last: Union[int, float]
    count: int
    labels: Dict[str, str] = field(default_factory=dict)



class TelemetryFixture(Telemetry):
    def __init__(self, stateful: bool = False):
        super().__init__(span_processor=None, stateful=stateful)
        self.span_exporter = InMemorySpanExporter()
        self.metrics_exporter = InMemoryMetricsExporter()
        self.add_span_exporter(span_exporter=self.span_exporter)
        self.add_metrics_exporter(metrics_exporter=self.metrics_exporter, interval=10000)
        self.collected = False
        self.caplog = JsonLogCaptureFormatter()

    def enable_log_record_capture(self, caplog: LogCaptureFixture):
        """
        This is exposed to be called from a test to install the json log format on the 'caplog' fixture.  If there's
        a way to do this automatically, then we could get rid of this, but all attempts to do this as part of fixture
        initialization, etc didn't work because the fixture is replaced for each phase of the test run (setup, run test)
        """
        caplog.handler.setFormatter(self.caplog)

    def _get_labels(self, metric: ExportRecord):
        return dict(filter(lambda label: not label[0].startswith('_'), metric.labels))

    def _find_metric(self,
                     metric_type: Type,
                     name: str,
                     labels: Optional[Dict[str, str]] = None) -> Optional[ExportRecord]:

        labels = labels or {}

        def fail_no_match(msg: str, candidates: Optional[List[ExportRecord]] = None):
            if candidates is None:
                candidates = self.metrics_exporter.get_exported_metrics()
            msg = f"{msg}\n\nMetric:\n\t{name} {labels}\n\nRecorded {metric_type.__name__} metric(s):\n"
            if len(candidates) > 0:
                for m in candidates:
                    msg = f"{msg}\t{m.instrument.name} {self._get_labels(m)}\n"
            else:
                msg = f"{msg}\t(none)"
            return msg

        if not self.collected:
            self.collect()

        candidates = []

        for metric in self.metrics_exporter.get_exported_metrics():
            m: ExportRecord = metric
            if type(m.instrument) != metric_type:
                continue

            candidates.append(m)

            if m.instrument.name == name:
                if self._get_labels(m) == labels:
                    return m  # exact match, return immediately

        pytest.fail(fail_no_match(f"No matching {metric_type.__name__} metric found!", candidates))

    def collect(self):
        self.collected = True
        for controller in self.metrics.meter_provider._controllers:
            if isinstance(controller, PushController):
                controller.tick()

    def get_metrics(self,
                    type_filter: Callable[[Type], bool] = lambda v: True,
                    name_filter: Callable[[str], bool] = lambda v: True,
                    label_filter: Callable[[Dict[str, str]], bool] = lambda v: True,
                    instrumentor_filter: Callable[[str], bool] = lambda v: True) -> List[
        Union[CounterInfo, ValueRecorderInfo]]:
        metrics = []
        for metric in self.metrics_exporter.get_exported_metrics():
            m: ExportRecord = metric
            if not type_filter(type(m.instrument)) or not name_filter(m.instrument.name) or \
                    not label_filter(self._get_labels(m)) or not instrumentor_filter(m.instrument.meter.instrumentation_info.name):
                continue

            if type(m.instrument) == Counter:
                metrics.append(CounterInfo(m.instrument.name, m.aggregator.checkpoint, self._get_labels(m)))
            elif type(m.instrument) == ValueRecorder:
                metrics.append(ValueRecorderInfo(m.instrument.name,
                                                 m.aggregator.checkpoint.min,
                                                 m.aggregator.checkpoint.max,
                                                 m.aggregator.checkpoint.sum,
                                                 m.aggregator.checkpoint.count,
                                                 self._get_labels(m)))
            else:
                # TODO: other metric types?
                pass

        return metrics

    def get_counters(self, name_filter: Callable[[str], bool] = lambda v: True,
                     label_filter: Callable[[Dict[str, str]], bool] = lambda v: True) -> List[CounterInfo]:
        return self.get_metrics(type_filter=lambda t: t == Counter, name_filter=name_filter, label_filter=label_filter)

    def get_finished_spans(self, name_filter: Callable[[str], bool] = lambda v: True,
                           attribute_filter: Callable[[Attributes], bool] = lambda v: True,
                           label_filter: Callable[[Dict[str, str]], bool] = lambda v: True) -> List[Span]:
        spans = []

        for span in self.span_exporter.get_finished_spans():
            if not name_filter(f"{span.qname}") or not attribute_filter(
                    span.attributes) or not label_filter(span.labels):
                continue
            spans.append(span)

        return spans

    def get_value_recorders(self, name_filter: Callable[[str], bool] = lambda v: True,
                            label_filter: Callable[[Dict[str, str]], bool] = lambda v: True) -> List[ValueRecorderInfo]:
        return self.get_metrics(type_filter=lambda t: t == ValueRecorder, name_filter=name_filter,
                                label_filter=label_filter)

    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[CounterInfo]:
        m = self._find_metric(Counter, name, labels)
        if m:
            return CounterInfo(m.instrument.name, m.aggregator.checkpoint, self._get_labels(m))
        else:
            return None

    def get_up_down_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[CounterInfo]:
        m = self._find_metric(UpDownCounter, name, labels)
        if m:
            return CounterInfo(m.instrument.name, m.aggregator.checkpoint, self._get_labels(m))
        else:
            return None

    def get_value_recorder(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[ValueRecorderInfo]:
        m = self._find_metric(ValueRecorder, name, labels)
        if m:
            return ValueRecorderInfo(m.instrument.name,
                                     m.aggregator.checkpoint.min,
                                     m.aggregator.checkpoint.max,
                                     m.aggregator.checkpoint.sum,
                                     m.aggregator.checkpoint.count,
                                     self._get_labels(m))
        else:
            return None

    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[GaugeInfo]:
        m = self._find_metric(ValueObserver, name, labels)
        if m:
            return GaugeInfo(f"{m.instrument.name}.{name}",
                             m.aggregator.checkpoint.min,
                             m.aggregator.checkpoint.max,
                             m.aggregator.checkpoint.sum,
                             m.aggregator.checkpoint.last,
                             m.aggregator.checkpoint.count,
                             self._get_labels(m))
        else:
            return None


class JsonLogCaptureFormatter(JsonLogFormatter):

    def __init__(self):
        super(JsonLogCaptureFormatter, self).__init__()
        self.records = []

    def add_fields(self, log_record, record, message_dict):
        super(JsonLogCaptureFormatter, self).add_fields(log_record, record, message_dict)
        self.records.append(log_record)

    def find_records(self, f: Callable[[LogRecord], bool]) -> Iterator[LogRecord]:
        return filter(f, self.records)

    def get_record(self, f: Callable[[LogRecord], bool]) -> LogRecord:
        matching = list(filter(f, self.records))
        if len(matching) == 0:
            pytest.fail("Matching log record not found!")
        if len(matching) != 1:
            pytest.fail(f"Expected a single log record match but got {len(matching)} instead")

        return matching[0]

    def assert_log_exists(self, f: Callable[[LogRecord], bool]):
        matching = list(filter(f, self.records))
        if len(matching) == 0:
            pytest.fail("Matching log record not found!")
        if len(matching) != 1:
            pytest.fail(f"Expected a single log record match but got {len(matching)} instead")

    def assert_log_contains(self, text: str, level: Optional[str] = None):
        for record in self.records:
            if text in record['message']:
                if level and level.upper() != record['level']:
                    pytest.fail(f"Assertion failed! Expected log message containing '{text}' to be level '{level}' "
                                f"but instead got '{record.levelname}'")
                return

        pytest.fail(f"Assertion failed! Could not find expected text in logs: {text}")
