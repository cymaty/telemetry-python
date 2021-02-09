from typing import Optional

import responses
from opentelemetry import context as context_api
from opentelemetry.instrumentation.requests import RequestsInstrumentor

from telemetry import Span, Attributes, Attribute
from telemetry.testing import TelemetryFixture
from tests.attributes import TestAttributes
from tests.example import ExampleClass


class TestTracer:

    def test_span_inheritance(self, telemetry: TelemetryFixture):
        with telemetry.span('test', 'span1', attributes={TestAttributes.ATTRIB1: 'attrib1', TestAttributes.LABEL1: 'label1'}) as span1:
            telemetry.counter('test', 'counter1')

            with telemetry.span('test', 'span2', attributes={TestAttributes.ATTRIB2: 'attrib2', TestAttributes.LABEL2: 'label2'}) as span2:
                telemetry.counter('test', 'counter2')

                with telemetry.span('test', 'span3') as span3:
                    span3.set_label('label3', 'label3')
                    span3.set_attribute('attrib3', 'attrib3')

                    telemetry.counter('test', 'counter3', labels={'counter_label': 'counter_label'})

                    assert span3.attributes == {'attrib1': 'attrib1',
                                                'attrib2': 'attrib2',
                                                'attrib3': 'attrib3',
                                                'label1': 'label1',
                                                'label2': 'label2',
                                                'label3': 'label3',
                                                Attributes.TRACE_ID.name: str(span3.context.trace_id),
                                                Attributes.TRACE_SPAN_ID.name: str(span3.context.span_id),
                                                Attributes.TRACE_IS_REMOTE.name: False,
                                                Attributes.TRACE_CATEGORY.name: 'test',
                                                Attributes.TRACE_NAME.name: 'test.span3'
                                                }

                    assert span3.labels == {Attributes.TRACE_CATEGORY.name: 'test',
                                            Attributes.TRACE_NAME.name: 'test.span3',
                                            'label1': 'label1',
                                            'label2': 'label2',
                                            'label3': 'label3'}

                    assert telemetry.current_span.qname == 'test.span3'
                    assert span3.qname == 'test.span3'

        telemetry.collect()

        assert telemetry.get_counter('test.counter1', labels={'label1': 'label1',
                                                              Attributes.TRACE_CATEGORY.name: 'test',
                                                              Attributes.TRACE_NAME.name: 'test.span1'}).value == 1
        assert telemetry.get_counter('test.counter2', labels={'label1': 'label1',
                                                              'label2': 'label2',
                                                              Attributes.TRACE_CATEGORY.name: 'test',
                                                              Attributes.TRACE_NAME.name: 'test.span2'}).value == 1
        assert telemetry.get_counter('test.counter3', labels={'label1': 'label1',
                                                              'label2': 'label2',
                                                              'label3': 'label3',
                                                              'counter_label': 'counter_label',
                                                              Attributes.TRACE_CATEGORY.name: 'test',
                                                              Attributes.TRACE_NAME.name: 'test.span3'}).value == 1
        assert len(telemetry.get_finished_spans()) == 3

    def test_mixin(self, telemetry: TelemetryFixture, caplog):
        example = ExampleClass()
        example.method1()
        example.method2()
        try:
            example.error()  # raises exception
        except:
            pass

        telemetry.collect()

        assert example.telemetry_category == 'tests.example.ExampleClass'

        # method1 (direct)
        assert telemetry.get_counter('tests.example.ExampleClass.method1_counter').value == 1

        # method1 (direct, inside span)
        assert telemetry.get_counter('tests.example.ExampleClass.method1_counter_inside_span', labels={'label1': 'value1',
                                                                                                       Attributes.TRACE_CATEGORY.name: 'tests.example.ExampleClass',
                                                                                                       Attributes.TRACE_NAME.name: 'tests.example.ExampleClass.method1'}).value == 1

        # method2 (direct)
        assert telemetry.get_counter('tests.example.ExampleClass.method2_counter').value == 1

        # method2 (direct, inside span)
        assert telemetry.get_counter('tests.example.ExampleClass.method2_counter_inside_span',
                                     labels={'label2': 'value2',
                                             Attributes.TRACE_CATEGORY.name: 'tests.example.ExampleClass',
                                             Attributes.TRACE_NAME.name: 'tests.example.ExampleClass.method2'}).value == 1  # method2 (inside span)

        # method2 (indirect)
        assert telemetry.get_counter('tests.example.ExampleClass.method2_counter', labels={'label1': 'value1',
                                                                                           Attributes.TRACE_CATEGORY.name: 'tests.example.ExampleClass',
                                                                                           Attributes.TRACE_NAME.name: 'tests.example.ExampleClass.method1'}).value == 1

        # method2 (indirect, inside span)
        assert telemetry.get_counter('tests.example.ExampleClass.method2_counter_inside_span',
                                     labels={'label1': 'value1', 'label2': 'value2',
                                             Attributes.TRACE_CATEGORY.name: 'tests.example.ExampleClass',
                                             Attributes.TRACE_NAME.name: 'tests.example.ExampleClass.method2'}).value == 1

        assert len(telemetry.get_counters()) == 8

        # method1 (direct)
        assert telemetry.get_value_recorder('trace.duration',
                                            labels={'label1': 'value1',
                                                    Attributes.TRACE_STATUS.name: 'OK',
                                                    Attributes.TRACE_CATEGORY.name: 'tests.example.ExampleClass',
                                                    Attributes.TRACE_NAME.name: 'tests.example.ExampleClass.method1'}).count == 1

        assert telemetry.get_value_recorder('trace.duration',
                                            labels={'label1': 'value1',
                                                    Attributes.TRACE_STATUS.name: 'OK',
                                                    Attributes.TRACE_CATEGORY.name: 'tests.example.ExampleClass',
                                                    Attributes.TRACE_NAME.name: 'tests.example.ExampleClass.method1'}).sum >= 100
        assert telemetry.get_value_recorder('trace.duration',
                                            labels={'label1': 'value1',
                                                    Attributes.TRACE_STATUS.name: 'OK',
                                                    Attributes.TRACE_CATEGORY.name: 'tests.example.ExampleClass',
                                                    Attributes.TRACE_NAME.name: 'tests.example.ExampleClass.method1'}).min >= 100
        assert telemetry.get_value_recorder('trace.duration',
                                            labels={'label1': 'value1',
                                                    Attributes.TRACE_STATUS.name: 'OK',
                                                    Attributes.TRACE_CATEGORY.name: 'tests.example.ExampleClass',
                                                    Attributes.TRACE_NAME.name: 'tests.example.ExampleClass.method1'}).max >= 100

        # method2 (direct)
        assert telemetry.get_value_recorder('trace.duration',
                                            labels={'label2': 'value2',
                                                    Attributes.TRACE_STATUS.name: 'OK',
                                                    Attributes.TRACE_CATEGORY.name: 'tests.example.ExampleClass',
                                                    Attributes.TRACE_NAME.name: 'tests.example.ExampleClass.method2'}).count == 1
        assert telemetry.get_value_recorder('trace.duration',
                                            labels={'label2': 'value2',
                                                    Attributes.TRACE_STATUS.name: 'OK',
                                                    Attributes.TRACE_CATEGORY.name: 'tests.example.ExampleClass',
                                                    Attributes.TRACE_NAME.name: 'tests.example.ExampleClass.method2'}).sum >= 100
        assert telemetry.get_value_recorder('trace.duration',
                                            labels={'label2': 'value2',
                                                    Attributes.TRACE_STATUS.name: 'OK',
                                                    Attributes.TRACE_CATEGORY.name: 'tests.example.ExampleClass',
                                                    Attributes.TRACE_NAME.name: 'tests.example.ExampleClass.method2'}).min >= 100
        assert telemetry.get_value_recorder('trace.duration',
                                            labels={'label2': 'value2',
                                                    Attributes.TRACE_STATUS.name: 'OK',
                                                    Attributes.TRACE_CATEGORY.name: 'tests.example.ExampleClass',
                                                    Attributes.TRACE_NAME.name: 'tests.example.ExampleClass.method2'}).max >= 100

        # method2 (indirect)
        assert telemetry.get_value_recorder('trace.duration',
                                            labels={'label1': 'value1',
                                                    'label2': 'value2',
                                                    Attributes.TRACE_STATUS.name: 'OK',
                                                    Attributes.TRACE_CATEGORY.name: 'tests.example.ExampleClass',
                                                    Attributes.TRACE_NAME.name: 'tests.example.ExampleClass.method2'}).count == 1

        # error (direct)
        assert telemetry.get_value_recorder('trace.duration',
                                            labels={Attributes.TRACE_STATUS.name: 'ERROR',
                                                    Attributes.TRACE_CATEGORY.name: 'tests.example.ExampleClass',
                                                    Attributes.TRACE_NAME.name: 'tests.example.ExampleClass.error'}).count == 1

        assert telemetry.get_counter('trace.errors', labels={Attributes.TRACE_STATUS.name: 'ERROR',
                                                             Attributes.TRACE_CATEGORY.name: 'tests.example.ExampleClass',
                                                             Attributes.TRACE_NAME.name: 'tests.example.ExampleClass.error'}).value == 1

        assert len(telemetry.get_value_recorders()) == 4

    def test_json_log_format(self, telemetry: TelemetryFixture, caplog):
        telemetry.enable_log_record_capture(caplog)

        example = ExampleClass()
        example.method1()

        telemetry.collect()
        method1_span = telemetry.get_finished_spans(name_filter=lambda name: name == 'tests.example.ExampleClass.method1')[0]
        method2_span = telemetry.get_finished_spans(name_filter=lambda name: name == 'tests.example.ExampleClass.method2')[0]

        log_record = telemetry.caplog.get_record(lambda l: l['message'] == 'method1 log')
        assert log_record['attributes'] == {TestAttributes.ATTRIB1.name: 'value1',
                                            TestAttributes.LABEL1.name: 'value1',
                                            Attributes.TRACE_ID.name: method1_span.context.trace_id,
                                            Attributes.TRACE_SPAN_ID.name: method1_span.context.span_id,
                                            Attributes.TRACE_IS_REMOTE.name: False,
                                            Attributes.TRACE_CATEGORY.name: 'tests.example.ExampleClass',
                                            Attributes.TRACE_NAME.name: 'tests.example.ExampleClass.method1'}

        log_record = telemetry.caplog.get_record(lambda l: l['message'] == 'method2 log')
        assert log_record['attributes'] == {TestAttributes.ATTRIB1.name: 'value1',
                                            TestAttributes.ATTRIB2.name: 'value2',
                                            Attributes.TRACE_ID.name: method2_span.context.trace_id,
                                            Attributes.TRACE_SPAN_ID.name: method2_span.context.span_id,
                                            Attributes.TRACE_IS_REMOTE.name: False,
                                            Attributes.TRACE_CATEGORY.name: 'tests.example.ExampleClass',
                                            Attributes.TRACE_NAME.name: 'tests.example.ExampleClass.method2',
                                            'label1': 'value1',
                                            'label2': 'value2'}

        telemetry.collect()

        assert example.telemetry_category == 'tests.example.ExampleClass'
        assert telemetry.get_value_recorder(name='trace.duration',
                                            labels={Attributes.TRACE_STATUS.name: 'OK', 'label1': 'value1',
                                                    Attributes.TRACE_CATEGORY.name: 'tests.example.ExampleClass',
                                                    Attributes.TRACE_NAME.name: 'tests.example.ExampleClass.method1'}).count == 1

        assert telemetry.get_value_recorder(name='trace.duration',
                                            labels={Attributes.TRACE_STATUS.name: 'OK', 'label1': 'value1', 'label2': 'value2',
                                                    Attributes.TRACE_CATEGORY.name: 'tests.example.ExampleClass',
                                                    Attributes.TRACE_NAME.name: 'tests.example.ExampleClass.method2'}).count == 1
        assert len(telemetry.get_value_recorders()) == 2

    def test_span_events(self, telemetry: TelemetryFixture):
        with telemetry.span('test', 'span1', attributes={TestAttributes.LABEL1: 'span1_value1'}) as span1:
            span1.set_attribute('label2', 'span1_value2')

            with telemetry.span('test', 'span2', attributes={TestAttributes.LABEL2: 'span2_value2'}) as span2:
                span2.add_event('TestEvent1', {'string_field': 'string_value', 'int_field': 10})
                with telemetry.span('test', 'span3', attributes={TestAttributes.LABEL3: 'span3_value3'}) as span3:
                    span3.add_event('TestEvent2', {'string_field': 'string_value', 'int_field': 20})

                    assert len(span3.events()) == 1
                    assert len(span2.events()) == 1

    @responses.activate
    def test_third_party_instrumentor(self, telemetry: TelemetryFixture):
        import requests
        from telemetry.api.listeners.span import LabelAttributes, InstrumentorSpanListener

        RequestsInstrumentor().instrument()

        telemetry.initialize()
        telemetry.add_span_listener(InstrumentorSpanListener(
            LabelAttributes('component', 'http.status_code', 'http.method'), 'requests'))

        responses.add_passthru('http://localhost:1234/does_not_exist')

        with telemetry.span('test_category', 'span1', attributes={TestAttributes.LABEL1: 'l1'}) as span:
            try:
                with requests.get('http://localhost:1234/does_not_exist') as response:
                    pass
            except:
                pass

        telemetry.collect()

        assert telemetry.get_value_recorder(name='trace.duration',
                                            labels={'component': 'http',
                                                    'http.method': 'GET',
                                                    TestAttributes.LABEL1.name: 'l1',
                                                    Attributes.TRACE_CATEGORY.name: 'requests',
                                                    Attributes.TRACE_NAME.name: 'requests.HTTP GET',
                                                    Attributes.TRACE_STATUS.name: 'ERROR'}).count == 1

    def test_span_listener(self, telemetry: TelemetryFixture):
        from opentelemetry.sdk.trace import SpanProcessor
        class Customlabelger(SpanProcessor):
            def on_start(self, span: "Span", parent_context: Optional[context_api.Context] = None) -> None:
                wrapped = Span(span)
                wrapped.set_attribute('hostname', 'localhost')
                wrapped.set_label('env', 'test')

        telemetry.add_span_listener(Customlabelger())

        with telemetry.span("category1", "span1") as span:
            assert span.labels['env'] == 'test'

        telemetry.collect()

        assert telemetry.get_value_recorder(name='trace.duration',
                                            labels={'env': 'test',
                                                    Attributes.TRACE_CATEGORY.name: 'category1',
                                                    Attributes.TRACE_NAME.name: 'category1.span1',
                                                    Attributes.TRACE_STATUS.name: 'OK'}).count == 1

    def test_invalid_attributes(self, telemetry: TelemetryFixture, caplog):
        telemetry.enable_log_record_capture(caplog)

        invalid_names = [
            '',
            'invalid ',
            '(invalid )',
        ]

        with telemetry.span('test', 'span1') as span:
            for name in invalid_names:
                span.set_attribute(name, "value")
                telemetry.caplog \
                    .assert_log_contains(f"attribute/label name must match the pattern: _*[a-zA-Z0-9_.\\-]+ (name={name})", 'WARNING')

    def test_invalid_labels(self, telemetry: TelemetryFixture, caplog):
        telemetry.enable_log_record_capture(caplog)

        invalid_names = [
            '',
            'invalid ',
            '(invalid )',
        ]

        with telemetry.span('test', 'span1') as span:
            for name in invalid_names:
                span.set_label(name, "value")
                telemetry.caplog.assert_log_contains(
                    f"attribute/label name must match the pattern: _*[a-zA-Z0-9_.\-]+ (name={name})", 'WARNING')

            span.set_label("foo", 1)
            telemetry.caplog.assert_log_contains(
                f"label value for must be a string! (name=foo, value=1)", 'WARNING')

            span.set_label("foo", 1.0)
            telemetry.caplog.assert_log_contains(
                f"label value for must be a string! (name=foo, value=1.0)", 'WARNING')

            span.set_label("foo", True)
            telemetry.caplog.assert_log_contains(
                f"label value for must be a string! (name=foo, value=True)", 'WARNING')
