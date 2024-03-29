import logging

from telemetry import Attributes
from telemetry.api.helpers.environment import Environment
from telemetry.testing import TelemetryFixture
from tests.attributes import TestAttributes


class TestEnvironment:

    def test_environment_attributes(self, monkeypatch, telemetry: TelemetryFixture):
        monkeypatch.setenv('METRICS_LABEL_label1', 'label1_value')
        monkeypatch.setenv('METRICS_LABEL_label2', 'label2_value')
        monkeypatch.setenv('METRICS_ATTRIBUTE_ATTRIB1', 'attrib1_value')
        monkeypatch.setenv('METRICS_ATTRIBUTE_ATTRIB2', 'attrib2_value')

        # need to initialize again after environment is updated
        telemetry.initialize()

        with telemetry.span("category1", 'span1') as span:
            logging.info("In span")

        telemetry.collect()

        assert len(telemetry.get_finished_spans(name_filter=lambda name: name == 'category1.span1',
                                                attribute_filter=lambda a: a.get('attrib1') == 'attrib1_value' and
                                                                           a.get('attrib2') == 'attrib2_value')) == 1

        assert telemetry.get_value_recorder('trace.duration', labels={Attributes.TRACE_CATEGORY.name: 'category1',
                                                                      Attributes.TRACE_NAME.name: 'category1.span1',
                                                                      Attributes.TRACE_STATUS.name: 'OK', 'label1': 'label1_value',
                                                                      'label2': 'label2_value'}).count == 1

    def test_environment_attributes_override(self, monkeypatch, telemetry: TelemetryFixture):
        monkeypatch.setenv('METRICS_LABEL_label1', 'label1_value')
        monkeypatch.setenv('METRICS_LABEL_label2', 'label2_value')
        monkeypatch.setenv('METRICS_ATTRIBUTE_ATTRIB1', 'attrib1_value')
        monkeypatch.setenv('METRICS_ATTRIBUTE_ATTRIB2', 'attrib2_value')

        # need to initialize again after environment is updated
        telemetry.initialize()

        # environment labels should win over any locally-specified labels to preserve ops behavior
        with telemetry.span("category1",
                            'span1',
                            attributes={TestAttributes.ATTRIB1: 'attrib1_override', TestAttributes.LABEL1: 'label1_value'}) as span:
            pass

        telemetry.collect()

        spans = telemetry.get_finished_spans()
        assert len(telemetry.get_finished_spans(name_filter=lambda name: name == 'category1.span1',
                                                attribute_filter=lambda a: a.get('attrib1') == 'attrib1_override')) == 1

        assert telemetry.get_value_recorder('trace.duration',
                                            labels={Attributes.TRACE_CATEGORY.name: 'category1',
                                                    Attributes.TRACE_NAME.name: 'category1.span1',
                                                    Attributes.TRACE_STATUS.name: 'OK',
                                                    TestAttributes.LABEL1.name: 'label1_value',
                                                    TestAttributes.LABEL2.name: 'label2_value'}).count == 1

        Environment._clear()

    def test_labelger_empty(self, monkeypatch, telemetry: TelemetryFixture):
        # need to initialize again after environment is updated
        telemetry.initialize()

        with telemetry.span("category1", 'span1') as span:
            pass

        telemetry.collect()

        assert telemetry.get_value_recorder('trace.duration', labels={Attributes.TRACE_CATEGORY.name: 'category1',
                                                                      Attributes.TRACE_NAME.name: 'category1.span1',
                                                                      Attributes.TRACE_STATUS.name: 'OK'}).count == 1

        Environment._clear()

    def test_metrics_labelged_without_span(self, monkeypatch, telemetry: TelemetryFixture):
        monkeypatch.setenv('METRICS_LABEL_label1', 'label1_value')
        monkeypatch.setenv('METRICS_LABEL_label2', 'label2_value')
        monkeypatch.setenv('METRICS_ATTRIBUTE_ATTRIB1', 'attrib1_value')
        monkeypatch.setenv('METRICS_ATTRIBUTE_ATTRIB2', 'attrib2_value')

        # test that we include the environment labelger by default
        telemetry.initialize()

        # environment labels should win over any locally-specified labels to preserve ops behavior
        telemetry.counter('category1', 'counter1', 1, labels={'label1': 'label1_override'})
        telemetry.collect()

        assert telemetry.get_counter('category1.counter1', labels={'label1': 'label1_value',
                                                                   'label2': 'label2_value'}).value == 1

        Environment._clear()
