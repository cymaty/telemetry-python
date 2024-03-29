from telemetry.testing import TelemetryFixture


class TestMetrics:
    def test_counter(self, telemetry: TelemetryFixture):
        telemetry.counter("category1", "counter1", 1)
        telemetry.counter("category1", "counter2", 2)
        telemetry.counter("category1", "counter3", 2)
        telemetry.counter("category1", "counter3", 1)
        telemetry.counter("category1", "counter4", 1, labels={'label1': 'label1'})

        telemetry.collect()

        assert telemetry.get_counter('category1.counter1').value == 1
        assert telemetry.get_counter('category1.counter2').value == 2
        assert telemetry.get_counter('category1.counter3').value == 3
        assert telemetry.get_counter('category1.counter4', labels={'label1': 'label1'}).value == 1

    def test_up_down_counter(self, telemetry: TelemetryFixture):
        telemetry.up_down_counter("category1", "counter1", 5)
        telemetry.up_down_counter("category1", "counter1", -10)

        telemetry.collect()

        assert telemetry.get_up_down_counter('category1.counter1').value == -5

    def test_gauge(self, telemetry: TelemetryFixture):
        telemetry.gauge("category1", "gauge1", lambda observer: observer.observe(10, {'label1': 'label1'}))
        telemetry.gauge("category1", "gauge2", lambda observer: observer.observe(1.2, {'label1': 'label1'}))

        telemetry.collect()

        assert telemetry.get_gauge('category1.gauge1', {'label1': 'label1'}).count == 1
        assert telemetry.get_gauge('category1.gauge1', {'label1': 'label1'}).min == 10
        assert telemetry.get_gauge('category1.gauge1', {'label1': 'label1'}).max == 10
        assert telemetry.get_gauge('category1.gauge1', {'label1': 'label1'}).last == 10
        assert telemetry.get_gauge('category1.gauge1', {'label1': 'label1'}).sum == 10

        assert telemetry.get_gauge('category1.gauge2', {'label1': 'label1'}).count == 1
        assert telemetry.get_gauge('category1.gauge2', {'label1': 'label1'}).min == 1.2
        assert telemetry.get_gauge('category1.gauge2', {'label1': 'label1'}).max == 1.2
        assert telemetry.get_gauge('category1.gauge2', {'label1': 'label1'}).last == 1.2
        assert telemetry.get_gauge('category1.gauge2', {'label1': 'label1'}).sum == 1.2

    def test_value_recorder(self, telemetry: TelemetryFixture):
        telemetry.record_value("category1", "value1", 1)

        telemetry.record_value("category1", "value2", 1.0)
        telemetry.record_value("category1", "value2", 1.2)
        telemetry.record_value("category1", "value2", 1.4)

        telemetry.collect()

        assert telemetry.get_value_recorder('category1.value1').count == 1
        assert telemetry.get_value_recorder('category1.value1').sum == 1
        assert telemetry.get_value_recorder('category1.value1').min == 1
        assert telemetry.get_value_recorder('category1.value1').max == 1

        assert telemetry.get_value_recorder('category1.value2').count == 3
        assert telemetry.get_value_recorder('category1.value2').sum == 3.6
        assert telemetry.get_value_recorder('category1.value2').min == 1.0
        assert telemetry.get_value_recorder('category1.value2').max == 1.4


    def test_instrumentors(self, telemetry: TelemetryFixture):
        telemetry.record_value("category1", "value1", 1)
        with telemetry.span("span_category1", "span1") as span:
            pass

        telemetry.collect()

        assert len(telemetry.get_metrics()) == 2
        assert len(telemetry.get_metrics(instrumentor_filter=lambda name: name == "default")) == 2
