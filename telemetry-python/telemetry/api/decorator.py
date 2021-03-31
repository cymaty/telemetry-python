import inspect
import logging
import typing
from enum import Enum
from typing import Dict, Optional

import wrapt

from telemetry.api import Attribute, Label
from telemetry.api.trace import AttributeValue

ArgumentLabeler = typing.Callable[[any], Optional[str]]
AttributeExtractor = typing.Callable[[Dict[str, any], typing.Callable[[any], any]], Dict[Attribute, any]]

def extract_args(*args: str, **kwargs) -> Optional[AttributeExtractor]:
    """
    Creates an `AttributeExtractor` that extracts one or more function arguments as attributes/labels.

    If `args` is set, the arguments will be added as `Attribute`'s with the same name.
    Example:

    Extract using name of the argument as the attribute/label name:
    ```
    @trace(attribute_extractor=extract_args('foo'), label_extractor=extract_args('bar'))
    def some_method(foo: str = 'default', bar: str = 'default'):
        // attribute 'foo' will be added with value of `foo` argument
        // label 'bar' will be added with value of `bar` argument
    ```

    Extract
    ```
    @trace(attribute_extractor=extract_args(foo=Attributes.FOO))
    def some_method(foo: str = 'default'):
        // attribute Attributes.FOO will be added with value of `foo` argument
    ```
    :param args: argument names to extract
    :param kwargs: argument names to Attribute or Label to use for that argument
    :return: `AttributeExtractor` that will extract the given argument names as attributes/labels
    """
    def extract(values: Dict[str, any], fn) -> Dict[Attribute, any]:
        out = {}

        for name in args:
            if name not in values:
                logging.warning(
                    f"@trace decorator refers to an argument '{name}' that was not found in the "
                    f"signature for {fn.__qualname__}! (this attribute will not be added)")
            else:
                out[Attribute(name, register=False)] = values[name]

        for name, value in kwargs.items():
            if name not in values:
                logging.warning(
                    f"@trace decorator refers to an argument '{name}' that was not found in the "
                    f"signature for {fn.__qualname__}! (this attribute will not be added)")
            else:
                if isinstance(value, Attribute):
                    out[value] = values[name]
                elif isinstance(value, str):
                    out[Attribute(value, register=False)] = values[name]
                elif value == Label:
                    out[Label(name, register=False)] = values[name]
                elif value == Attribute:
                    out[Attribute(name, register=False)] = values[name]
                else:
                    logging.warning(
                        f"@trace decorator has invalid mapping for argument '{name}'.  Expected one of Label, Attribute or str but got {type(value)}")
        return out
    return extract


class TracedInvocation:
    def __init__(self, owner, target):
        self.owner = owner
        self.target = target
        self.arg_values = None
        
    def resolve_arguments(self, *args, **kwargs) -> Dict[str, any]:

        if not self.arg_values is None:
            return self.arg_values

        import inspect

        # initialize with explicitly-passed kwargs
        arg_values = kwargs.copy()

        # resolve the function signature (if not yet resolved)
        if self.owner.signature is None:
            self.owner.signature = inspect.signature(self.target)


        def set_arg_value(name: str, value: any):
            # if None value, then set to predefined value of 'none_value'
            if value is None or value is inspect.Parameter.empty:
                arg_values[name] = None
                return

            # if value is an enum, then extract the name
            if isinstance(value, Enum):
                value = value.name

            arg_values[name] = value


        for i, (name, param) in enumerate(self.owner.signature.parameters.items()):
            if name == 'self' or name in arg_values:
                continue

            # we have positional argument
            if i < len(args):
                set_arg_value(name, args[i])
            else:
                if param.default:
                    set_arg_value(name, param.default)

        self.arg_values = arg_values

        return arg_values


    def wrap_span_attributes(self, fn, decorator_name: str, setter: typing.Callable[[Attribute, any], None], extractor: Optional[AttributeExtractor]):
        def wrapped(*args, **kwargs):
            if extractor:
                try:
                    extracted = extractor(self.resolve_arguments(*args, **kwargs), self.target)
                    if extracted:
                        for attrib, value in extracted.items():
                            setter(attrib, value)
                except BaseException as ex:
                    logging.warning(
                        f"{decorator_name} decorator for {self.target.__qualname__} threw an exception during label extraction! {ex}")

            return fn(*args, **kwargs)

        return wrapped

@wrapt.decorator
class trace(object):
    """
    Trace decorator that enables tracing of calls for the decorated method/function.

    category: override the trace category otherwise defaults to the qualified name of the decorated function/method
    attributes: static set of attributes (of type `telemetry.Attribute`) to set on the span
    attribute_extractor: a callable in the form:  (arguments, decorated_function) -> (attributes)
    label_extractor: a callable in the form:  (arguments, decorated_function) -> (labels)

    For `attribute_extractor` and `label_extractor` there is a helper function, `extract_args` that takes a list of argument names and
    will return an `AttributeExtractor` that will extract the argument values as attributes/labels.
    """
    extract_args = extract_args

    def __init__(self,
                 *,
                 category: Optional[str] = None,
                 attributes: Optional[typing.Mapping[Attribute, AttributeValue]] = None,
                 extractor: Optional[AttributeExtractor] = None
                 ):

        self.signature = None
        self.category = category
        self.attributes = attributes or {}
        self.extractor = extractor

    def _get_category(self, fn, instance):
        import inspect
        if hasattr(self, 'category') and self.category:
            return self.category
        elif instance:
            if hasattr(instance, 'telemetry_category'):
                return getattr(instance, 'telemetry_category')
            else:
                return f"{instance.__class__.__module__}.{instance.__class__.__name__}"
        else:
            return inspect.getmodule(fn).__name__

    def __call__(self, fn, instance, args, kwargs):
        from telemetry import telemetry

        if not callable(fn):
            raise Exception("Invalid use of @trace decorator. All arguments should be passed as keyword arguments, eg: @trace(category='foo')")
        else:
            if self.signature is None:
                self.signature = inspect.signature(fn)

            with telemetry.tracer.span(self._get_category(fn, instance), fn.__name__) as span:
                # set static attributes
                for a, value in self.attributes.items():
                    span.set(a, value)
                invocation = TracedInvocation(self, fn)
                wrapped_extracted = invocation.wrap_span_attributes(fn, "@trace", span.set, self.extractor)
                return wrapped_extracted(*args, **kwargs)


