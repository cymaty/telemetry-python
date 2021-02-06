class Keys:
    class Label:
        ENV = 'env'
        TRACE_NAME = 'trace.name'
        TRACE_CATEGORY = 'trace.category'
        TRACE_STATUS = 'trace.status'

        # anything in this list will be automatically promoted to a label regardless of whether set_attribute or set_label is used
        _FORCE_LABELS = (ENV, TRACE_NAME, TRACE_CATEGORY, TRACE_STATUS)

    class Attribute:
        _LABEL_KEYS = '_label_keys'
        TRACE_ID = 'trace.id'
        TRACE_SPAN_ID = 'trace.span_id'

    class Trace:
        SPAN_DURATION = 'trace.duration'


from telemetry.api.telemetry import Telemetry, TelemetryMixin
from telemetry.api.decorator import trace
