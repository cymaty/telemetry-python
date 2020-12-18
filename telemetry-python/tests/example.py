import logging
import time

from telemetry import TelemetryMixin, trace


@trace
def global_method():
    logging.info('global_method log')
    time.sleep(0.1)  # artificial delay so that we can assert a non-zero elapsed time


class ExampleClass(TelemetryMixin):
    def method1(self):
        self.telemetry.counter('method1_counter')
        with self.telemetry.span('method1', attributes={'key1': 'value1'}, tags={'tag1': 'value1'}) as span:
            self.telemetry.counter('method1_counter_inside_span', 1)
            logging.info('method1 log')
            time.sleep(0.1)  # artificial delay so that we can assert a non-zero elapsed time
            self.method2()

    def method2(self):
        self.telemetry.counter('method2_counter', 1)
        with self.telemetry.span('method2', attributes={'key2': 'value2'}, tags={'tag2': 'value2'}) as span:
            self.telemetry.counter('method2_counter_inside_span', 1)
            time.sleep(0.1)  # artificial delay so that we can assert a non-zero elapsed time
            logging.info('method2 log')

    def error(self):
        self.telemetry.counter('error_counter', 1)
        with self.telemetry.span('error') as span:
            time.sleep(0.1)  # artificial delay so that we can assert a non-zero elapsed time
            logging.info('error log')
            raise Exception("Intentional")
