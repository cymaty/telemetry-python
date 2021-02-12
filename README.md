# Telemetry API

## Environment Variables

TODO

## Usage

Via Module Import:
```python
from telemetry import telemetry, Attributes

class UserManager:
    def fetch_user(self, user_id: str):
        with telemetry.span("UserManager", "fetch_user", attributes={Attributes.USER_ID, user_id}) as span:
            # ... fetch and return user ...
```

Via `TelemetryMixin` class:

The `TelemetryMixin` class can be mixed into any class to expose a `telemetry` variable on the class.
All of the standard telemetry methods are available on this member, EXCEPT that the methods don't accept a `category` argument-- instead the category will be automatically populated with the class's fully-qualified name.   
```python
from telemetry import Attributes, TelemetryMixin

class UserManager(TelemetryMixin):
    def fetch_user(self, user_id: str):
        # note how the "category" argument is not specified-- it will be auto set to the fully-qualified class name 
        self.telemetry.span("fetch_user", attributes={Attributes.USER_ID, user_id})
            # ... fetch and return user ...
```

## Attributes and Labels

Attributes and labels are used the same way, but they have different applications as far as how they are attached to traces, metrics and logging.
* **Attribute**'s should be used to represent values with [high-cardinality](https://en.wikipedia.org/wiki/Cardinality_(SQL_statements)) 
* **Labels**'s should be used to represent values with [low-cardinality](https://en.wikipedia.org/wiki/Cardinality_(SQL_statements))

| Type      | Cardinality |
|-----------|-------------|
| Attribute | High        |
| Label     | Low         |


There are currently three telemetry data "types": **Traces**, **Metrics** and **Logs**.  When span's are created and wrap code, the traces/metrics/logs within that span will inherit the span's attributes and labels.
Here is a summary of whether attributes and/or labels will be attached to the corresponding telemetry type:
 
| System  | Labels?   | Attributes? | Notes |
|---------|-----------|-------------|-------|
| Metrics | YES       | NO          | Due to the high-cardinality nature of attributes, they are not included for metrics because each value combination would create a new time-series in the metrics database (eg: Prometheus) |
| Traces  | YES       | YES (except trace metrics)  | Each trace exported to an external trace viewer like Jaeger will include both, but the trace metrics that track the trace count and timing will NOT include attributes |
| Logs    | YES       | YES         | Logs will include all labels and attributes when JSON logging is used |

### Attribute and Label Inheritance

When defining `Attribute`'s and `Label`'s, there is a `propagate` flag that dictates whether that attribute/label will be automatically pass down to any child spans from a parent span.

This is useful when you want to be able to track a higher "context" in which that trace/metric/log was generated.
For example, for the standard tag `GRPC_METHOD`, the `propagate` flag is set to `True`, which means that any telemetry data that is generated within the execution of that GRPC call will have the GRPC method that is currently executing attached to all telemetry data generated within that call.

TODO: recommendations and/or rule of thumb for enabling propagation?
  
## JSON Logging

Setting the environment variable `JSON_LOGGING=1` environment variable will install a Python `logging` handler that will emit logs as JSON records and attach current attributes and labels to the log message under the `attributes` key. 
## Tracing

#### Usage

```python

```

## Metrics

#### Exporting Metrics


