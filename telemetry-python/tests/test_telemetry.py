import logging
import time

from opentelemetry.instrumentation.requests import RequestsInstrumentor

import responses
from telemetry import TelemetryMixin, trace
from telemetry.testing import TelemetryFixture


@trace
def global_method():
    logging.info('global_method log')
    time.sleep(0.1)  # artificial delay so that we can assert a non-zero elapsed time


class TestTelemetry:
    class ExampleClass(TelemetryMixin):
        def method1(self):
            self.telemetry.counter('counter1')
            with self.telemetry.span('method1', attributes={'key1': 'value1'}, tags={'tag1': 'value1'}) as span:
                self.telemetry.counter('counter1_inside_span', 1)
                logging.info('method1 log')
                time.sleep(0.1)  # artificial delay so that we can assert a non-zero elapsed time
                self.method2()

        def method2(self):
            self.telemetry.counter('counter2', 1)
            with self.telemetry.span('method2', attributes={'key2': 'value2'}, tags={'tag2': 'value2'}) as span:
                self.telemetry.counter('counter2_inside_span', 1)
                time.sleep(0.1)  # artificial delay so that we can assert a non-zero elapsed time
                logging.info('method2 log')

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
        example = TestTelemetry.ExampleClass()
        example.method1()
        example.method2()

        telemetry.collect()

        assert example.telemetry_category == 'ExampleClass'

        # method1 (direct)
        assert telemetry.get_counter('ExampleClass.counter1').value == 1

        # method1 (direct, inside span)
        assert telemetry.get_counter('ExampleClass.counter1_inside_span', tags={'tag1': 'value1'}).value == 1

        # method2 (direct)
        assert telemetry.get_counter('ExampleClass.counter2').value == 1

        # method2 (direct, inside span)
        assert telemetry.get_counter('ExampleClass.counter2_inside_span',
                                     tags={'tag2': 'value2'}).value == 1  # method2 (inside span)

        # method2 (indirect)
        assert telemetry.get_counter('ExampleClass.counter2', tags={'tag1': 'value1'}).value == 1

        # method2 (indirect, inside span)
        assert telemetry.get_counter('ExampleClass.counter2_inside_span',
                                     tags={'tag1': 'value1', 'tag2': 'value2'}).value == 1

        assert len(telemetry.get_counters()) == 6

        # method1 (direct)
        assert telemetry.get_value_recorder('ExampleClass.method1', tags={'span.status': 'OK', 'tag1': 'value1'}).count == 1
        assert telemetry.get_value_recorder('ExampleClass.method1', tags={'span.status': 'OK', 'tag1': 'value1'}).sum >= 100
        assert telemetry.get_value_recorder('ExampleClass.method1', tags={'span.status': 'OK', 'tag1': 'value1'}).min >= 100
        assert telemetry.get_value_recorder('ExampleClass.method1', tags={'span.status': 'OK', 'tag1': 'value1'}).max >= 100
        #assert telemetry.get_counter('ExampleClass.method1.errors', tags={'tag1': 'value1'}).value == 0

        # method2 (direct)
        assert telemetry.get_value_recorder('ExampleClass.method2', tags={'span.status': 'OK', 'tag2': 'value2'}).count == 1
        assert telemetry.get_value_recorder('ExampleClass.method2', tags={'span.status': 'OK', 'tag2': 'value2'}).sum >= 100
        assert telemetry.get_value_recorder('ExampleClass.method2', tags={'span.status': 'OK', 'tag2': 'value2'}).min >= 100
        assert telemetry.get_value_recorder('ExampleClass.method2', tags={'span.status': 'OK', 'tag2': 'value2'}).max >= 100
        #assert telemetry.get_counter('ExampleClass.method2.errors', tags={'tag1': 'value1'}).value == 0
        
        # method2 (indirect)
        assert telemetry.get_value_recorder('ExampleClass.method2',
                                            tags={'span.status': 'OK', 'tag1': 'value1', 'tag2': 'value2'}).count == 1
        # assert telemetry.get_counter('ExampleClass.method2',
        #                                     tags={'tag1': 'value1', 'tag2': 'value2'}).value == 0

        assert len(telemetry.get_value_recorders()) == 3

    def test_json_log_format(self, telemetry: TelemetryFixture, caplog):
        telemetry.enable_log_record_capture(caplog)

        example = TestTelemetry.ExampleClass()
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

        assert example.telemetry_category == 'ExampleClass'
        assert telemetry.get_value_recorder(name='ExampleClass.method1',
                                            tags={'span.status': 'OK', 'tag1': 'value1'}).count == 1

        assert telemetry.get_value_recorder(name='ExampleClass.method2',
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


class TestMetrics:
    def test_counter(self, telemetry: TelemetryFixture):
        telemetry.counter("category1", "counter1", 1)
        telemetry.counter("category1", "counter2", 2)
        telemetry.counter("category1", "counter3", 2)
        telemetry.counter("category1", "counter3", 1)
        telemetry.counter("category1", "counter4", 1, tags={'tag1': 'tag1'})

        telemetry.collect()

        assert telemetry.get_counter('category1.counter1').value == 1
        assert telemetry.get_counter('category1.counter2').value == 2
        assert telemetry.get_counter('category1.counter3').value == 3
        assert telemetry.get_counter('category1.counter4', tags={'tag1': 'tag1'}).value == 1

    def test_gauge(self, telemetry: TelemetryFixture):
        telemetry.gauge("category1", "gauge1", lambda observer: observer.observe(10, {'tag1': 'tag1'}))
        telemetry.gauge("category1", "gauge2", lambda observer: observer.observe(1.2, {'tag1': 'tag1'}))

        telemetry.collect()

        assert telemetry.get_gauge('category1.gauge1', {'tag1': 'tag1'}).count == 1
        assert telemetry.get_gauge('category1.gauge1', {'tag1': 'tag1'}).min == 10
        assert telemetry.get_gauge('category1.gauge1', {'tag1': 'tag1'}).max == 10
        assert telemetry.get_gauge('category1.gauge1', {'tag1': 'tag1'}).last == 10
        assert telemetry.get_gauge('category1.gauge1', {'tag1': 'tag1'}).sum == 10

        assert telemetry.get_gauge('category1.gauge2', {'tag1': 'tag1'}).count == 1
        assert telemetry.get_gauge('category1.gauge2', {'tag1': 'tag1'}).min == 1.2
        assert telemetry.get_gauge('category1.gauge2', {'tag1': 'tag1'}).max == 1.2
        assert telemetry.get_gauge('category1.gauge2', {'tag1': 'tag1'}).last == 1.2
        assert telemetry.get_gauge('category1.gauge2', {'tag1': 'tag1'}).sum == 1.2

    def test_value_recorder(self, telemetry: TelemetryFixture):
        telemetry.record("category1", "value1", 1)

        telemetry.record("category1", "value2", 1.0)
        telemetry.record("category1", "value2", 1.2)
        telemetry.record("category1", "value2", 1.4)

        telemetry.collect()

        assert telemetry.get_value_recorder('category1.value1').count == 1
        assert telemetry.get_value_recorder('category1.value1').sum == 1
        assert telemetry.get_value_recorder('category1.value1').min == 1
        assert telemetry.get_value_recorder('category1.value1').max == 1

        assert telemetry.get_value_recorder('category1.value2').count == 3
        assert telemetry.get_value_recorder('category1.value2').sum == 3.6
        assert telemetry.get_value_recorder('category1.value2').min == 1.0
        assert telemetry.get_value_recorder('category1.value2').max == 1.4


class TestDecorator:
    class ExampleClass(TelemetryMixin):

        @trace
        def method_trace_default(self, arg1: str, arg2: int = 10):
            self.telemetry.counter('counter3', 1)
            time.sleep(0.1)  # artificial delay so that we can assert a non-zero elapsed time
            logging.info(f'method_trace_default log')

        @trace(category='custom_category',
               tags={'tag1': 't1'},
               attributes={'attribute1': 'a1'},
               argument_tags={'arg1'},
               argument_attributes={'arg2'})
        def method_trace_custom(self, arg1: str, arg2: int = 10):
            self.telemetry.counter('counter3', 1)
            time.sleep(0.1)  # artificial delay so that we can assert a non-zero elapsed time
            logging.info(f'method_trace_custom log')

        @trace(category='custom_category',
               tags={'tag1': 't1'},
               attributes={'attribute1': 'a1'},
               argument_tags={'arg4'},  # arg4 is not a valid argument
               argument_attributes={'arg2'})
        def method_invalid_argument_tag(self, arg1: str, arg2: int = 10):
            logging.info(f'method3_invalid_argument_tag log')

    def test_decorator_global_method(self, telemetry: TelemetryFixture, caplog):
        telemetry.enable_log_record_capture(caplog)

        global_method()

        telemetry.collect()

        assert telemetry.get_value_recorder('tests.test_telemetry.global_method', tags={'span.status': 'OK'}).count == 1

        telemetry.caplog.assert_log_exists(lambda l: l['message'] == 'global_method log')

    def test_decorator_default(self, telemetry: TelemetryFixture):
        example = TestDecorator.ExampleClass()
        example.method_trace_default(arg1='arg1_value')

        telemetry.collect()

        assert example.telemetry_category == 'ExampleClass'
        assert telemetry.get_value_recorder('ExampleClass.method_trace_default', tags={'span.status': 'OK'}).count == 1

    def test_decorator_custom(self, telemetry: TelemetryFixture):
        example = TestDecorator.ExampleClass()
        example.method_trace_custom(arg1='arg1_value')

        telemetry.collect()

        assert example.telemetry_category == 'ExampleClass'
        assert telemetry.get_value_recorder(name='custom_category.method_trace_custom',
                                            tags={'arg1': 'arg1_value', 'tag1': 't1', 'span.status': 'OK'}).count == 1

    def test_decorator_argument_tagging(self, telemetry: TelemetryFixture):
        example = TestDecorator.ExampleClass()
        example.method_trace_custom('foo')

        telemetry.collect()

        assert telemetry.get_value_recorder(name='custom_category.method_trace_custom',
                                            tags={'arg1': 'foo', 'tag1': 't1', 'span.status': 'OK'}).count == 1

    def test_decorator_invalid_argument_tag(self, telemetry: TelemetryFixture, caplog):
        telemetry.enable_log_record_capture(caplog)

        example = TestDecorator.ExampleClass()
        example.method_invalid_argument_tag(arg1='arg1_value')

        telemetry.collect()

        telemetry.caplog.assert_log_contains("@timed call refers to an argument, arg4, that was not found", 'WARNING')
