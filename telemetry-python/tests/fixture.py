from dataclasses import field, dataclass
from logging import LogRecord
from typing import Callable, Iterator, Dict, Optional, List, Type, Union

import pytest
from _pytest.logging import LogCaptureFixture
from opentelemetry.sdk.metrics import PushController, Counter, ValueRecorder, ValueObserver
from opentelemetry.sdk.metrics.export import ExportRecord
from opentelemetry.sdk.metrics.export.in_memory_metrics_exporter import InMemoryMetricsExporter
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.util.types import Attributes

from telemetry import Telemetry, SynchronousSpanTracker, Span
from telemetry.api.logger.json import JsonLogFormatter


@dataclass
class CounterInfo:
    name: str
    value: Union[int, float]
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class ValueRecorderInfo:
    name: str
    min: Union[int, float]
    max: Union[int, float]
    sum: Union[int, float]
    count: int
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class GaugeInfo:
    name: str
    min: Union[int, float]
    max: Union[int, float]
    sum: Union[int, float]
    last: Union[int, float]
    count: int
    tags: Dict[str, str] = field(default_factory=dict)

class TelemetryFixture(Telemetry):
    def __init__(self):
        span_tracker = SynchronousSpanTracker()
        super().__init__(span_tracker=span_tracker)
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

    def _get_tags(self, metric: ExportRecord):
        return dict(filter(lambda tag: not tag[0].startswith('_'), metric.labels))

    def _find_metric(self,
                     metric_type: Type,
                     name: str,
                     tags: Optional[Dict[str, str]] = None) -> Optional[ExportRecord]:

        tags = tags or {}

        def fail_no_match(msg: str, candidates: Optional[List[ExportRecord]] = None):
            if candidates is None:
                candidates = self.metrics_exporter.get_exported_metrics()
            msg = f"{msg}\n\nMetric:\n\t{name} {tags}\n\nRecorded {metric_type.__name__} metric(s):\n"
            if len(candidates) > 0:
                for m in candidates:
                    msg = f"{msg}\t{m.instrument.name} {self._get_tags(m)}\n"
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
                if self._get_tags(m) == tags:
                    return m  # exact match, return immediately

        pytest.fail(fail_no_match(f"No matching {metric_type.__name__} metric found!", candidates))

    def collect(self):
        self.collected = True
        for controller in self.meter_provider._controllers:
            if isinstance(controller, PushController):
                controller.tick()

    def get_metrics(self,
                    type_filter: Callable[[Type], bool] = lambda v: True,
                    name_filter: Callable[[str], bool] = lambda v: True,
                    tag_filter: Callable[[Dict[str, str]], bool] = lambda v: True) -> List[Union[CounterInfo, ValueRecorderInfo]]:
        metrics = []
        for metric in self.metrics_exporter.get_exported_metrics():
            m: ExportRecord = metric
            if not type_filter(type(m.instrument)) or not name_filter(m.instrument.name) or not tag_filter(self._get_tags(m)):
                continue

            if type(m.instrument) == Counter:
                metrics.append(CounterInfo(m.instrument.name, m.aggregator.checkpoint, self._get_tags(m)))
            elif type(m.instrument) == ValueRecorder:
                metrics.append(ValueRecorderInfo(m.instrument.name,
                                                 m.aggregator.checkpoint.min,
                                                 m.aggregator.checkpoint.max,
                                                 m.aggregator.checkpoint.sum,
                                                 m.aggregator.checkpoint.count,
                                                 self._get_tags(m)))
            else:
                # TODO: other metric types?
                pass

        return metrics

    def get_counters(self, name_filter: Callable[[str], bool] = lambda v: True,
                           tag_filter: Callable[[Dict[str, str]], bool] = lambda v: True) -> List[CounterInfo]:
        return self.get_metrics(type_filter=lambda t: t == Counter, name_filter=name_filter, tag_filter=tag_filter)

    def get_finished_spans(self, name_filter: Callable[[str], bool] = lambda v: True,
                                 attribute_filter: Callable[[Attributes], bool] = lambda v: True,
                                 tag_filter: Callable[[Dict[str, str]], bool] = lambda v: True) -> List[Span]:
        spans = []

        for span in self.span_exporter.get_finished_spans():
            wrapped_span = Span(span)
            if not name_filter(f"{wrapped_span.qname}") or not attribute_filter(wrapped_span.attributes) or not tag_filter(wrapped_span.tags):
                continue
            spans.append(wrapped_span)

        return spans

    def get_value_recorders(self, name_filter: Callable[[str], bool] = lambda v: True,
                                  tag_filter: Callable[[Dict[str, str]], bool] = lambda v: True) -> List[ValueRecorderInfo]:
        return self.get_metrics(type_filter=lambda t: t == ValueRecorder, name_filter=name_filter, tag_filter=tag_filter)

    def get_counter(self, name: str, tags: Optional[Dict[str, str]] = None) -> Optional[CounterInfo]:
        m = self._find_metric(Counter, name, tags)
        if m:
            return CounterInfo(m.instrument.name, m.aggregator.checkpoint, self._get_tags(m))
        else:
            return None

    def get_value_recorder(self, name: str, tags: Optional[Dict[str, str]] = None) -> Optional[ValueRecorderInfo]:
        m = self._find_metric(ValueRecorder, name, tags)
        if m:
            return ValueRecorderInfo(m.instrument.name,
                                     m.aggregator.checkpoint.min,
                                     m.aggregator.checkpoint.max,
                                     m.aggregator.checkpoint.sum,
                                     m.aggregator.checkpoint.count,
                                     self._get_tags(m))
        else:
            return None

    def get_gauge(self, name: str, tags: Optional[Dict[str, str]] = None) -> Optional[GaugeInfo]:
        m = self._find_metric(ValueObserver, name, tags)
        if m:
            return GaugeInfo(f"{m.instrument.name}.{name}",
                             m.aggregator.checkpoint.min,
                             m.aggregator.checkpoint.max,
                             m.aggregator.checkpoint.sum,
                             m.aggregator.checkpoint.last,
                             m.aggregator.checkpoint.count,
                             self._get_tags(m))
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
