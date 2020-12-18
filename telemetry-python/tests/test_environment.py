from telemetry.testing import TelemetryFixture


class TestEnvironment:

    def test_tagger(self, monkeypatch, telemetry: TelemetryFixture):
        monkeypatch.setenv('METRICS_TAG_TAG1', 'tag1_value')
        monkeypatch.setenv('METRICS_TAG_TAG2', 'tag2_value')
        monkeypatch.setenv('METRICS_ATTRIBUTE_ATTRIB1', 'attrib1_value')
        monkeypatch.setenv('METRICS_ATTRIBUTE_ATTRIB2', 'attrib2_value')

        # need to initialize again after environment is updated
        telemetry.initialize()

        with telemetry.span("category1", 'span1') as span:
            pass

        telemetry.collect()

        assert len(telemetry.get_finished_spans(name_filter=lambda name: name == 'category1.span1',
                                                attribute_filter=lambda a: a.get('attrib1') == 'attrib1_value' and
                                                                           a.get('attrib2') == 'attrib2_value')) == 1

        assert telemetry.get_value_recorder('category1.span1.duration', tags={'span.status': 'OK', 'tag1': 'tag1_value',
                                                                     'tag2': 'tag2_value'}).count == 1

    def test_tagger_no_override(self, monkeypatch, telemetry: TelemetryFixture):
        monkeypatch.setenv('METRICS_TAG_TAG1', 'tag1_value')
        monkeypatch.setenv('METRICS_TAG_TAG2', 'tag2_value')
        monkeypatch.setenv('METRICS_ATTRIBUTE_ATTRIB1', 'attrib1_value')
        monkeypatch.setenv('METRICS_ATTRIBUTE_ATTRIB2', 'attrib2_value')

        # need to initialize again after environment is updated
        telemetry.initialize()

        # environment tags should win over any locally-specified tags to preserve ops behavior
        with telemetry.span("category1",
                            'span1',
                            attributes={'attrib2': 'attrib2_override'},
                            tags={'tag2': 'tag2_override'}) as span:
            pass

        telemetry.collect()

        assert len(telemetry.get_finished_spans(name_filter=lambda name: name == 'category1.span1',
                                                attribute_filter=lambda a: a.get('attrib1') == 'attrib1_value' and
                                                                           a.get('attrib2') == 'attrib2_value')) == 1

        assert telemetry.get_value_recorder('category1.span1.duration',
                                            tags={'span.status': 'OK', 'tag1': 'tag1_value',
                                                  'tag2': 'tag2_override'}).count == 1

    def test_tagger_empty(self, monkeypatch, telemetry: TelemetryFixture):
        # need to initialize again after environment is updated
        telemetry.initialize()

        with telemetry.span("category1", 'span1') as span:
            pass

        telemetry.collect()

        assert telemetry.get_value_recorder('category1.span1.duration', tags={'span.status': 'OK'}).count == 1


    def test_metrics_tagged_without_span(self, monkeypatch, telemetry: TelemetryFixture):
        monkeypatch.setenv('METRICS_TAG_TAG1', 'tag1_value')
        monkeypatch.setenv('METRICS_TAG_TAG2', 'tag2_value')
        monkeypatch.setenv('METRICS_ATTRIBUTE_ATTRIB1', 'attrib1_value')
        monkeypatch.setenv('METRICS_ATTRIBUTE_ATTRIB2', 'attrib2_value')

        # test that we include the environment tagger by default
        telemetry.initialize()

        # environment tags should win over any locally-specified tags to preserve ops behavior
        telemetry.counter('category1', 'counter1', 1, tags={'tag1': 'tag1_override'})
        telemetry.collect()

        assert telemetry.get_counter('category1.counter1', tags={'tag1': 'tag1_value',
                                                                 'tag2': 'tag2_value'}).value == 1
