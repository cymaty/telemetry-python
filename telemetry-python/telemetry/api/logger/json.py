from datetime import datetime

from pythonjsonlogger import jsonlogger


class JsonLogFormatter(jsonlogger.JsonFormatter):
    copy_fields = ['filename', 'lineno', 'module', 'process', 'processName', 'threadName']

    def add_fields(self, log_record, record, message_dict):
        from telemetry import tracer

        super(JsonLogFormatter, self).add_fields(log_record, record, message_dict)
        log_record['@timestamp'] = datetime.now().isoformat()
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['attributes'] = tracer.attributes

        for name in self.copy_fields:
            if hasattr(record, name):
                value = getattr(record, name)
                if value is not None:
                    log_record[name] = str(value)
