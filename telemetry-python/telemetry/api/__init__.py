class Keys:
    class Label:
        ENV = 'env'
        TRACE_NAME = 'span'
        TRACE_CATEGORY = 'category'
        TRACE_STATUS = 'span_status'

        # anything in this list will be automatically promoted to a label regardless of whether set_attribute or set_label is used
        _FORCE_LABELS = (ENV, TRACE_NAME, TRACE_CATEGORY, TRACE_STATUS)

    class Attribute:
        _LABEL_KEYS = '_label_keys'
        TRACE_ID = 'trace_id'
        TRACE_SPAN_ID = 'span_id'
        TRACE_IS_REMOTE = 'trace_is_remote'

    class Trace:
        SPAN_DURATION = 'trace.duration'


_NO_PROPAGATE = (Keys.Label.TRACE_CATEGORY, Keys.Attribute.TRACE_ID, Keys.Attribute.TRACE_SPAN_ID)

from telemetry.api.telemetry import Telemetry, TelemetryMixin
from telemetry.api.decorator import trace
