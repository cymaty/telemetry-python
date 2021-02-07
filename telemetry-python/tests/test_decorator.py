import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import pytest

from telemetry import TelemetryMixin, trace, extract_args, Keys
from telemetry.testing import TelemetryFixture
from tests.example import global_method


@dataclass
class ComplexValue:
    name: str
    age: Optional[int] = field(default=None)


class DecoratorExample(TelemetryMixin):
    @trace
    def method_trace_default(self, arg1: str, arg2: int = 10):
        self.telemetry.counter('counter3', 1)
        time.sleep(0.1)  # artificial delay so that we can assert a non-zero elapsed time
        logging.info(f'method_trace_default log')

    @trace(category='custom_category',
           labels={'label1': 't1'},
           attributes={'attribute1': 'a1'},
           label_extractor=extract_args("arg1"),
           attribute_extractor=extract_args("arg2"))
    def method_trace_custom(self, arg1: str, arg2: int = 10, arg3: Optional[ComplexValue] = None):
        self.telemetry.counter('counter3', 1)
        time.sleep(0.1)  # artificial delay so that we can assert a non-zero elapsed time
        logging.info(f'method_trace_custom log')

    @trace(category='custom_category',
           labels={'label1': 't1'},
           attributes={'attribute1': 'a1'},
           label_extractor=extract_args("arg4"),  # arg4 is not a valid argument
           attribute_extractor=extract_args("arg2"))
    def method_invalid_argument_label(self, arg1: str, arg2: int = 10):
        logging.info(f'method_invalid_argument_label log')

    @trace(label_extractor=extract_args("arg1"))  # arg1 is a complex type, ComplexValue)
    def method_invalid_complex_argument_label(self, arg1: ComplexValue):
        logging.info(f'method_invalid_complex_argument_label log')

    @trace(label_extractor=lambda d, fn: {'name': d['arg1']['name']} if 'arg1' in d else {})
    def method_complex_argument_label(self, arg1: ComplexValue):
        logging.info(f'method_complex_argument_label log')

    # @trace(labels={'label1': 't1'}, attributes={'attribute1': 'a1'})
    # def method_outer(self, arg1: str, arg2: int = 10):
    #     logging.info(f'method_outer log')
    #     self.method_inner(f"{arg1}_inner", arg2*2)
    # 
    # @trace.labels(labels={'label_inner': 'label_inner'}, extractor=extract_args("arg1"))
    # @trace.attributes(extractor=extract_args("arg2"))
    # def method_inner(self, arg1: str, arg2: int = 10):
    #     logging.info(f'method_inner log')


class TestDecorator:

    def test_decorator_global_method(self, telemetry: TelemetryFixture, caplog):
        telemetry.enable_log_record_capture(caplog)

        global_method()

        telemetry.collect()

        assert telemetry.get_value_recorder('trace.duration', labels={Keys.Label.TRACE_CATEGORY: 'tests.example',
                                                                      Keys.Label.TRACE_NAME: 'tests.example.global_method',
                                                                      Keys.Label.TRACE_STATUS: 'OK'}).count == 1

        log_record = telemetry.caplog.get_record(lambda l: l['message'] == 'global_method log')
        assert log_record['attributes']['trace_id']

    def test_decorator_default(self, telemetry: TelemetryFixture):
        example = DecoratorExample()
        example.method_trace_default(arg1='arg1_value')

        telemetry.collect()

        assert example.telemetry_category == 'tests.test_decorator.DecoratorExample'
        assert telemetry.get_value_recorder('trace.duration', labels={
            Keys.Label.TRACE_CATEGORY: 'tests.test_decorator.DecoratorExample',
            Keys.Label.TRACE_NAME: 'tests.test_decorator.DecoratorExample.method_trace_default',
            Keys.Label.TRACE_STATUS: 'OK'}).count == 1

    def test_decorator_custom(self, telemetry: TelemetryFixture):
        example = DecoratorExample()
        example.method_trace_custom(arg1='arg1_value')

        telemetry.collect()

        assert example.telemetry_category == 'tests.test_decorator.DecoratorExample'
        assert telemetry.get_value_recorder(name='trace.duration',
                                            labels={'arg1': 'arg1_value',
                                                    'label1': 't1',
                                                    Keys.Label.TRACE_CATEGORY: 'custom_category',
                                                    Keys.Label.TRACE_NAME: 'custom_category.method_trace_custom',
                                                    Keys.Label.TRACE_STATUS: 'OK'}).count == 1

    def test_decorator_argument_labelging(self, telemetry: TelemetryFixture, caplog):
        telemetry.enable_log_record_capture(caplog)

        example = DecoratorExample()
        example.method_trace_custom('foo')
        example.method_trace_custom('foo', 20)

        telemetry.collect()

        assert telemetry.get_value_recorder(name='trace.duration',
                                            labels={'arg1': 'foo', Keys.Label.TRACE_CATEGORY: 'custom_category',
                                                    Keys.Label.TRACE_NAME: 'custom_category.method_trace_custom',
                                                    Keys.Label.TRACE_STATUS: 'OK', 'label1': 't1'}).count == 2

        rec = telemetry.caplog.get_record(
            lambda rec: rec['message'] == 'method_trace_custom log' and rec['attributes']['arg2'] == 10)

        assert rec['attributes']['label1'] == 't1'
        assert rec['attributes']['arg1'] == 'foo'
        assert rec['attributes']['arg2'] == 10

        rec = telemetry.caplog.get_record(lambda rec: rec['message'] == 'method_trace_custom log' and
                                                      rec['attributes']['arg2'] == 20)

        assert rec['attributes']['label1'] == 't1'
        assert rec['attributes']['arg1'] == 'foo'
        assert rec['attributes']['arg2'] == 20

    def test_decorator_argument_labelging_none(self, telemetry: TelemetryFixture, caplog):
        telemetry.enable_log_record_capture(caplog)

        example = DecoratorExample()
        example.method_trace_custom(arg1='foo', arg2=None)

        telemetry.collect()

        assert telemetry.get_value_recorder(name='trace.duration',
                                            labels={'arg1': 'foo', 'label1': 't1', Keys.Label.TRACE_STATUS: 'OK',
                                                    Keys.Label.TRACE_CATEGORY: 'custom_category',
                                                    Keys.Label.TRACE_NAME: 'custom_category.method_trace_custom'}).count == 1

        rec = telemetry.caplog.get_record(lambda rec: rec['message'] == 'method_trace_custom log')

        assert rec['attributes']['label1'] == 't1'
        assert rec['attributes']['attribute1'] == 'a1'
        assert rec['attributes']['arg1'] == 'foo'

    def test_decorator_complex_argument_label(self, telemetry: TelemetryFixture):
        example = DecoratorExample()
        example.method_complex_argument_label(arg1=ComplexValue('foo', 10))

        telemetry.collect()

        assert telemetry.get_value_recorder(name='trace.duration',
                                            labels={Keys.Label.TRACE_STATUS: 'OK',
                                                    Keys.Label.TRACE_CATEGORY: 'tests.test_decorator.DecoratorExample',
                                                    Keys.Label.TRACE_NAME: 'tests.test_decorator.DecoratorExample.method_complex_argument_label'}).count == 1

    def test_decorator_invalid_argument_label(self, telemetry: TelemetryFixture, caplog):
        telemetry.enable_log_record_capture(caplog)

        example = DecoratorExample()
        example.method_invalid_argument_label(arg1='arg1_value')

        telemetry.collect()

        telemetry.caplog.assert_log_contains(
            "@trace decorator refers to an argument, arg4, that was not found in the signature for DecoratorExample.method_invalid_argument_label",
            'WARNING')

    def test_decorator_ignore_complex_argument_label(self, telemetry: TelemetryFixture, caplog):
        telemetry.enable_log_record_capture(caplog)

        example = DecoratorExample()
        example.method_complex_argument_label(arg1=ComplexValue('foo', 10))

        telemetry.collect()

        assert telemetry.get_value_recorder(name='trace.duration',
                                            labels={Keys.Label.TRACE_STATUS: 'OK',
                                                    Keys.Label.TRACE_CATEGORY: 'tests.test_decorator.DecoratorExample',
                                                    Keys.Label.TRACE_NAME: 'tests.test_decorator.DecoratorExample.method_complex_argument_label'}).count == 1

    def test_decorator_local_def(self, telemetry: TelemetryFixture):
        @trace(label_extractor=extract_args("arg"))
        def foo(arg: str):
            time.sleep(.1)
            return "value"

        foo('arg1')

        telemetry.collect()

        assert telemetry.get_value_recorder('trace.duration', labels={
            Keys.Label.TRACE_CATEGORY: 'tests.test_decorator',
            Keys.Label.TRACE_NAME: 'tests.test_decorator.foo',
            Keys.Label.TRACE_STATUS: 'OK',
            'arg': 'arg1'}).count == 1

    def test_decorator_throws_exception_on_invalid_usage(self, telemetry: TelemetryFixture):
        """
        Exception should be raised in this case since the "foo" will not be passed as a decorator value but used as the
        wrapping function instead
        """
        with pytest.raises(Exception):
            @trace("foo")
            def foo(arg: str):
                pass

    # def test_decorator_inner(self, telemetry: TelemetryFixture, caplog):
    #     telemetry.enable_log_record_capture(caplog)
    #
    #     example = DecoratorExample()
    #     example.method_outer("foo", 20)
    #
    #     telemetry.collect()
    #
    #     assert telemetry.get_value_recorder(name='trace.duration',
    #                                         labels={'label1': 't1',
    #                                               'label_inner': 'label_inner',
    #                                               'arg1': 'foo_inner',
    #                                               Keys.Label.TRACE_STATUS: 'OK',
    #                                               Keys.Label.TRACE_CATEGORY: 'tests.test_decorator.DecoratorExample',
    #                                               Keys.Label.TRACE_NAME: 'tests.test_decorator.DecoratorExample.method_outer'}).count == 1
    #
    #
    #     rec = telemetry.caplog.get_record(lambda rec: rec['message'] == 'method_outer log')
    #     assert rec['attributes']['label1'] == 't1'
    #
    #     rec = telemetry.caplog.get_record(lambda rec: rec['message'] == 'method_inner log')
    #     assert rec['attributes']['label1'] == 't1'
