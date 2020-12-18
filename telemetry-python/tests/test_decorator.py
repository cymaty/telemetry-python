import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from telemetry import TelemetryMixin, trace, extract_args
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
           tags={'tag1': 't1'},
           attributes={'attribute1': 'a1'},
           tag_extractor=extract_args("arg1"),
           attribute_extractor=extract_args("arg2"))
    def method_trace_custom(self, arg1: str, arg2: int = 10, arg3: Optional[ComplexValue] = None):
        self.telemetry.counter('counter3', 1)
        time.sleep(0.1)  # artificial delay so that we can assert a non-zero elapsed time
        logging.info(f'method_trace_custom log')

    @trace(category='custom_category',
           tags={'tag1': 't1'},
           attributes={'attribute1': 'a1'},
           tag_extractor=extract_args("arg4"),  # arg4 is not a valid argument
           attribute_extractor=extract_args("arg2"))
    def method_invalid_argument_tag(self, arg1: str, arg2: int = 10):
        logging.info(f'method_invalid_argument_tag log')


    @trace(tag_extractor=extract_args("arg1"))  # arg1 is a complex type, ComplexValue)
    def method_invalid_complex_argument_tag(self, arg1: ComplexValue):
        logging.info(f'method_invalid_complex_argument_tag log')

    @trace(tag_extractor=lambda d, fn: {'name': d['arg1']['name']} if 'arg1' in d else {})
    def method_complex_argument_tag(self, arg1: ComplexValue):
        logging.info(f'method_complex_argument_tag log')


class TestDecorator:

    def test_decorator_global_method(self, telemetry: TelemetryFixture, caplog):
        telemetry.enable_log_record_capture(caplog)

        global_method()

        telemetry.collect()

        assert telemetry.get_value_recorder('tests.example.global_method', tags={'span.status': 'OK'}).count == 1

        telemetry.caplog.assert_log_exists(lambda l: l['message'] == 'global_method log')

    def test_decorator_default(self, telemetry: TelemetryFixture):
        example = DecoratorExample()
        example.method_trace_default(arg1='arg1_value')

        telemetry.collect()

        assert example.telemetry_category == 'tests.test_decorator.DecoratorExample'
        assert telemetry.get_value_recorder('tests.test_decorator.DecoratorExample.method_trace_default', tags={'span.status': 'OK'}).count == 1

    def test_decorator_custom(self, telemetry: TelemetryFixture):
        example = DecoratorExample()
        example.method_trace_custom(arg1='arg1_value')

        telemetry.collect()

        assert example.telemetry_category == 'tests.test_decorator.DecoratorExample'
        assert telemetry.get_value_recorder(name='custom_category.method_trace_custom',
                                            tags={'arg1': 'arg1_value', 'tag1': 't1', 'span.status': 'OK'}).count == 1

    def test_decorator_argument_tagging(self, telemetry: TelemetryFixture):
        example = DecoratorExample()
        example.method_trace_custom('foo')

        telemetry.collect()

        assert telemetry.get_value_recorder(name='custom_category.method_trace_custom',
                                            tags={'arg1': 'foo', 'tag1': 't1', 'span.status': 'OK'}).count == 1

    def test_decorator_complex_argument_tag(self, telemetry: TelemetryFixture):
        example = DecoratorExample()
        example.method_complex_argument_tag(arg1=ComplexValue('foo', 10))

        telemetry.collect()

        assert telemetry.get_value_recorder(name='tests.test_decorator.DecoratorExample.method_complex_argument_tag',
                                            tags={'span.status': 'OK'}).count == 1


    def test_decorator_invalid_argument_tag(self, telemetry: TelemetryFixture, caplog):
        telemetry.enable_log_record_capture(caplog)

        example = DecoratorExample()
        example.method_invalid_argument_tag(arg1='arg1_value')

        telemetry.collect()

        telemetry.caplog.assert_log_contains("@trace decorator refers to an argument, arg4, that was not found in the signature for DecoratorExample.method_invalid_argument_tag", 'WARNING')

    def test_decorator_ignore_complex_argument_tag(self, telemetry: TelemetryFixture, caplog):
        telemetry.enable_log_record_capture(caplog)

        example = DecoratorExample()
        example.method_complex_argument_tag(arg1=ComplexValue('foo', 10))

        telemetry.collect()

        assert telemetry.get_value_recorder(name='tests.test_decorator.DecoratorExample.method_complex_argument_tag',
                                            tags={'span.status': 'OK'}).count == 1
