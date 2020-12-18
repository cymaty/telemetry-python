import pytest
import responses
from opentelemetry.instrumentation.requests import RequestsInstrumentor

from telemetry import Span
from telemetry.testing import TelemetryFixture
from tests.example import ExampleClass


class TestTracer:

    def test_span_inheritance(self, telemetry: TelemetryFixture):
        with telemetry.span('test', 'span1', attributes={'attrib1': 'attrib1'}, tags={'tag1': 'tag1'}) as span1:
            telemetry.counter('test', 'counter1')

            with telemetry.span('test', 'span2', attributes={'attrib2': 'attrib2'}, tags={'tag2': 'tag2'}) as span2:
                telemetry.counter('test', 'counter2')

                with telemetry.span('test', 'span3') as span3:
                    span3.set_tag('tag3', 'tag3')
                    span3.set_attribute('attrib3', 'attrib3')

                    telemetry.counter('test', 'counter3', tags={'counter_tag': 'counter_tag'})

                    assert span3.attributes == {'_tag_keys': ('tag1', 'tag2', 'tag3'),
                                                'attrib1': 'attrib1',
                                                'attrib2': 'attrib2',
                                                'attrib3': 'attrib3',
                                                'tag1': 'tag1',
                                                'tag2': 'tag2',
                                                'tag3': 'tag3'}

                    assert span3.tags == {'tag1': 'tag1',
                                          'tag2': 'tag2',
                                          'tag3': 'tag3'}

                    assert telemetry.current_span.qname == 'test.span3'
                    assert span3.qname == 'test.span3'
                    assert len(telemetry.active_spans()) == 3
                    assert list(map(lambda s: s.name, telemetry.active_spans())) == ['span3', 'span2', 'span1']

        telemetry.collect()

        assert telemetry.get_counter('test.counter1', tags={'tag1': 'tag1'}).value == 1
        assert telemetry.get_counter('test.counter2', tags={'tag1': 'tag1', 'tag2': 'tag2'}).value == 1
        assert telemetry.get_counter('test.counter3', tags={'tag1': 'tag1',
                                                            'tag2': 'tag2',
                                                            'tag3': 'tag3',
                                                            'counter_tag': 'counter_tag'}).value == 1
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
        assert telemetry.get_counter('tests.example.ExampleClass.method1_counter_inside_span', tags={'tag1': 'value1'}).value == 1

        # method2 (direct)
        assert telemetry.get_counter('tests.example.ExampleClass.method2_counter').value == 1

        # method2 (direct, inside span)
        assert telemetry.get_counter('tests.example.ExampleClass.method2_counter_inside_span',
                                     tags={'tag2': 'value2'}).value == 1  # method2 (inside span)

        # method2 (indirect)
        assert telemetry.get_counter('tests.example.ExampleClass.method2_counter', tags={'tag1': 'value1'}).value == 1

        # method2 (indirect, inside span)
        assert telemetry.get_counter('tests.example.ExampleClass.method2_counter_inside_span',
                                     tags={'tag1': 'value1', 'tag2': 'value2'}).value == 1

        assert len(telemetry.get_counters()) == 7

        # method1 (direct)
        assert telemetry.get_value_recorder('tests.example.ExampleClass.method1',
                                            tags={'span.status': 'OK', 'tag1': 'value1'}).count == 1
        assert telemetry.get_value_recorder('tests.example.ExampleClass.method1',
                                            tags={'span.status': 'OK', 'tag1': 'value1'}).sum >= 100
        assert telemetry.get_value_recorder('tests.example.ExampleClass.method1',
                                            tags={'span.status': 'OK', 'tag1': 'value1'}).min >= 100
        assert telemetry.get_value_recorder('tests.example.ExampleClass.method1',
                                            tags={'span.status': 'OK', 'tag1': 'value1'}).max >= 100

        # method2 (direct)
        assert telemetry.get_value_recorder('tests.example.ExampleClass.method2',
                                            tags={'span.status': 'OK', 'tag2': 'value2'}).count == 1
        assert telemetry.get_value_recorder('tests.example.ExampleClass.method2',
                                            tags={'span.status': 'OK', 'tag2': 'value2'}).sum >= 100
        assert telemetry.get_value_recorder('tests.example.ExampleClass.method2',
                                            tags={'span.status': 'OK', 'tag2': 'value2'}).min >= 100
        assert telemetry.get_value_recorder('tests.example.ExampleClass.method2',
                                            tags={'span.status': 'OK', 'tag2': 'value2'}).max >= 100
        # assert telemetry.get_counter('ExampleClass.method2.errors', tags={'tag1': 'value1'}).value == 0

        # method2 (indirect)
        assert telemetry.get_value_recorder('tests.example.ExampleClass.method2',
                                            tags={'span.status': 'OK', 'tag1': 'value1', 'tag2': 'value2'}).count == 1

        # error (direct)
        assert telemetry.get_value_recorder('tests.example.ExampleClass.error',
                                            tags={'span.status': 'ERROR'}).count == 1

        assert len(telemetry.get_value_recorders()) == 4

    def test_json_log_format(self, telemetry: TelemetryFixture, caplog):
        telemetry.enable_log_record_capture(caplog)

        example = ExampleClass()
        example.method1()

        log_record = telemetry.caplog.get_record(lambda l: l['message'] == 'method1 log')
        assert log_record['attributes'] == {'_tag_keys': ('tag1',),
                                            'key1': 'value1',
                                            'tag1': 'value1'}

        log_record = telemetry.caplog.get_record(lambda l: l['message'] == 'method2 log')
        assert log_record['attributes'] == {'_tag_keys': ('tag1', 'tag2'),
                                            'key1': 'value1',
                                            'key2': 'value2',
                                            'tag1': 'value1',
                                            'tag2': 'value2'}

        telemetry.collect()

        assert example.telemetry_category == 'tests.example.ExampleClass'
        assert telemetry.get_value_recorder(name='tests.example.ExampleClass.method1',
                                            tags={'span.status': 'OK', 'tag1': 'value1'}).count == 1

        assert telemetry.get_value_recorder(name='tests.example.ExampleClass.method2',
                                            tags={'span.status': 'OK', 'tag1': 'value1', 'tag2': 'value2'}).count == 1
        assert len(telemetry.get_value_recorders()) == 2

    def test_span_events(self, telemetry: TelemetryFixture):
        with telemetry.span('test', 'span1', attributes={'tag1': 'span1_value1'}) as span1:
            span1.set_attribute('tag2', 'span1_value2')

            with telemetry.span('test', 'span2', attributes={'tag2': 'span2_value2'}) as span2:
                span2.add_event('TestEvent1', {'string_field': 'string_value', 'int_field': 10})
                with telemetry.span('test', 'span3', attributes={'tag3': 'span3_value3'}) as span3:
                    span3.add_event('TestEvent2', {'string_field': 'string_value', 'int_field': 20})

                    assert len(span3.events()) == 1
                    assert len(span2.events()) == 1

    @responses.activate
    def test_third_party_instrumentor(self, telemetry: TelemetryFixture):
        import requests
        from telemetry.api.listeners.span import AttributeTagMarker, InstrumentorSpanListener

        RequestsInstrumentor().instrument()

        telemetry.add_span_listener(InstrumentorSpanListener(
            AttributeTagMarker('component', 'http.status_code', 'http.method'), 'requests'))

        responses.add_passthru('http://localhost:1234/does_not_exist')

        try:
            with requests.get('http://localhost:1234/does_not_exist') as response:
                pass
        except:
            pass

        telemetry.collect()

        assert telemetry.get_value_recorder(name='requests.HTTP GET',
                                            tags={'span.status': 'ERROR',
                                                  'component': 'http',
                                                  'http.method': 'GET'}).count == 1

    def test_span_listener(self, telemetry: TelemetryFixture):
        from telemetry.api import SpanListener

        class CustomTagger(SpanListener):
            def on_start(self, span: 'Span'):
                span.set_attribute('hostname', 'localhost')
                span.set_tag('env', 'test')

        telemetry.add_span_listener(CustomTagger())

        with telemetry.span("category1", "span1") as span:
            assert span.tags['env'] == 'test'

        telemetry.collect()

        assert telemetry.get_value_recorder(name='category1.span1',
                                            tags={'env': 'test',
                                                  'span.status': 'OK'}).count == 1

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
                telemetry.caplog\
                    .assert_log_contains(f"attribute/tag name must match the pattern: _*[a-zA-Z0-9_.\\-]+ (name={name})", 'WARNING')


    def test_invalid_tags(self, telemetry: TelemetryFixture, caplog):
        telemetry.enable_log_record_capture(caplog)

        invalid_names = [
            '',
            'invalid ',
            '(invalid )',
        ]

        with telemetry.span('test', 'span1') as span:
            for name in invalid_names:
                span.set_tag(name, "value")
                telemetry.caplog.assert_log_contains(
                    f"attribute/tag name must match the pattern: _*[a-zA-Z0-9_.\-]+ (name={name})", 'WARNING')

            span.set_tag("foo", 1)
            telemetry.caplog.assert_log_contains(
                f"Tag value for must be a string! (name=foo, value=1)", 'WARNING')
            
            span.set_tag("foo", 1.0)
            telemetry.caplog.assert_log_contains(
                f"Tag value for must be a string! (name=foo, value=1.0)", 'WARNING')

            span.set_tag("foo", True)
            telemetry.caplog.assert_log_contains(
                f"Tag value for must be a string! (name=foo, value=True)", 'WARNING')

