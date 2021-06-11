# Telemetry API

Supports exposing application metrics and tracing data.

## Usage

The Telemetry API can be accessed in different ways. 

### Via Global Module

**NOTE: With this usage, metric methods have a `category` argument to "scope" the metric under.**

```python
from telemetry import telemetry, Attributes

class UserManager:
    def fetch_user(self, user_id: str):
        with telemetry.span("UserManager", "fetch_user", attributes={Attributes.USER_ID, user_id}) as span:
            # ... fetch and return user ...
```

### Via `TelemetryMixin` class:

The `TelemetryMixin` class can be mixed into any class to expose a `telemetry` variable on the class.
All of the standard telemetry methods are available on this member, EXCEPT that the methods don't accept a `category` argument-- instead the category will be automatically populated with the class's fully-qualified name.

**NOTE: With this usage, metric methods do NOT have a `category` argument, it is inferred from the class name (or value of `telemetry_category` if overriden).**


```python
from telemetry import Attributes, TelemetryMixin

class UserManager(TelemetryMixin):
    def fetch_user(self, user_id: str):
        # note how the "category" argument is not specified-- it will be auto set to the fully-qualified class name 
        self.telemetry.span("fetch_user", attributes={Attributes.USER_ID, user_id})
            # ... fetch and return user ...
```

## Telemetry Methods

**NOTE: for methods below that have a `category` argument, the same method when using the `TelemetryMixin` class will NOT have a `category` argument.**

### Span

Creates a new span.  Typically used as a context manager like this:
```
with span(...) as span:
    # do something
```

Span data can be exported in two forms:
    - metrics (eg: call count and sum of duration of all calls) 
    - traces
    
The current span (if one is active), can be accessed by calling `current_span()`


```
def span(self, category: str, name: str,
         attributes: Optional[typing.Mapping[typing.Union[Attribute, str], AttributeValue]] = None,
         kind: SpanKind = SpanKind.INTERNAL) -> typing.ContextManager[Span]

:param category: the category to associate with the span
:param name: the short name of the span (we be appended to the category when exporting the full span name)
:param attributes: a dict of attribute/label instances to their values.
:param kind: the span kind (eg: CLIENT, SERVER, etc).  Defaults to INTERNAL 
:return: new span instance (wrapped in a ContextManager)
         
```

##### Working with Spans

Span instances have methods that can be called after creation to attach metadata to the span:

| Method | Description | Returns |
|--------|-------------|---------|
| `context()` | Returns the span's contextual information (eg: parent span id, etc) | `SpanContext` |
| `status()` | Returns the span's status | `SpanStatus` |
| `name()` | Returns the span's short name | `str` |
| `qname()` | Returns the span's qualified name (`{category}.{name}`) | `str` |
| `category()` | Returns the span's category | `str` |
| `set(attribute_or_label: Attribute, value: AttributeValue)` | Sets a pre-defined attribute or label value for this span | `None` |
| `set_attribute(name: str, value: AttributeValue)` | Sets an arbitrary attribute for this span | `None` |
| `set_label(name: str, value: str)` | Sets an arbitrary label fir this span | `None` |
| `add_event(name: str, attributes: Mapping[str, AttributeValue])` | Sets an arbitrary label for this span | `None` |
| `end()` | Ends the span to record the end time and status for this span | `None` |
| `attributes()` | Returns attributes/labels set for this span | `Mapping[str, AttributeValue]` |
| `labels()` | Returns only the labels set for this span | `Dict[str, str]` |
| `events()` | Returns events added to this span | `List` |


### Counter

Increments a counter value
 

```
def counter(self, category: str, name: str, value: typing.Union[int, float] = 1, labels: Dict[typing.Union[Label, str], str] = {},
            unit: str = "1",
            description: Optional[str] = None)
            
:param category: the metric's category
:param name: the metric's short name within the category
:param value: the value to add to the counter
:param labels: labels to attach to this counter value
:param unit: units to associate with this counter
:param description: human-readable description for this metric
:return: None            
```


### Up-Down Counter

Increments/decrements a counter value

```
def up_down_counter(self, category: str, name: str, value: typing.Union[int, float] = 1, labels: Dict[typing.Union[Label, str], str] = {},
                    unit: str = "1",
                    description: Optional[str] = None)

:param category: the metric's category
:param name: the metric's short name within the category
:param value: value to add to the counter.  May be negative.
:param labels: labels to attach to this counter value
:param unit: units to associate with this counter
:param description: human-readable description for this metric
:return: None
```


### Record Value

Records a numeric value.  When exported, two metrics will be written:        
- `<metric fqdn>_count`: how many values were recorded in the metric interval
- `<metric fqdn>_sum`: the sum of all the values recorded in the metric interval

```
def record_value(self, category: str, name: str, value: typing.Union[int, float] = 1, labels: Dict[typing.Union[Label, str], str] = {},
                 unit: str = "1",
                 description: Optional[str] = None)
                 
:param category: the metric's category
:param name: the metric's short name within the category
:param value: the value to record.
:param labels: labels to attach to this counter value
:param unit: units to associate with this counter
:param description: human-readable description for this metric
:return: None
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

### Standard Attributes/Labels

The `telemetry.api.Attributes` class is used to define attributes/labels that are not application specific.

### Application-Specific Attributes/Labels

A class should be defined in the application codebase (typically `<application top-level package>.telemetry.Attributes`) that should extend `telemetry.Attributes` so that it inherits the pre-defined attributes/labels defined in the Telemetry API project by default.

### Propagation

When defining `Attribute`'s and `Label`'s, there is a `propagate` flag that dictates whether that attribute/label will be automatically passed down to any child spans from a parent span. If `propagate` is `False`, then only
spans that explicitly set that attribute/label will have it set. 

This is useful when you want to be able to track a parent "context" in which all child traces/metrics/logs were generated.

For example, for the standard label `GRPC_METHOD`, the `propagate` flag is set to `True`, which means that any telemetry data that is generated within the execution of that specific GRPC method call will automatically have that label set.

TODO: recommendations and/or rule of thumb for enabling propagation?
  
## JSON Logging

To enable telemetry-aware JSON logging, call `initialize_json_logger()`.

- Typically, applications should check if the environment variable `LOG_FORMAT=json`, and if so, should call this method during application startup.
- The log message format is Logstash compatible.
- Any attributes/labels that are set on the current span when the log message emitted will be added to the `attributes` key of the message.


## Exporting Metrics

To enable exporting of metrics, you should set the `METRICS_EXPORTERS` environment variable to a comma-delimited set of exporters to enable.  See below for a list of exporters that are available.

### Exporters

| Key     | Description   | Configuration |
|---------|---------------|---------------|
| `prometheus` | Starts an HTTP server to expose a metrics dump page (by default: `http://localhost:9102`) | `METRICS_PROMETHEUS_BIND_ADDRESS` - sets the `hostname:port` to start the HTTP server on. Defaults to `localhost:9102`. `METRICS_PROMETHEUS_PREFIX` - prefix to add to all metrics exported to Prometheus.  Default is `None`. |
| `console` | Logs all metrics to the console (can be noisy). | TODO: allow for filtering of metric types/names via an environment variable. |

### Development

Run your application with the `METRICS_EXPORTERS=prometheus` environment variable, and then view all metric values by accessing [http://localhost:9102/](http://localhost:9102/)



