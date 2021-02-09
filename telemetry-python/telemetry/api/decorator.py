import functools
import inspect
import logging
import typing
from enum import Enum
from typing import Dict, Optional

import wrapt

from telemetry.api import Attribute
from telemetry.api.trace import AttributeValue

ArgumentLabeler = typing.Callable[[any], Optional[str]]
AttributeExtractor = typing.Callable[[Dict[str, any], typing.Callable[[any], any]], Dict[str, any]]

def extract_args(*args: str) -> Optional[AttributeExtractor]:
    def extract(values: Dict[str, any], fn) -> Dict[str, any]:
        out = {}
        for name in args:
            if name not in values:
                logging.warning(
                    f"@trace decorator refers to an argument, {name}, that was not found in the "
                    f"signature for {fn.__qualname__}! (this label will not be added)")
            else:
                out[name] = values[name]
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


    def wrap_span_attributes(self, fn, decorator_name: str, setter: typing.Callable[[str, any], None], extractor: Optional[AttributeExtractor]):
        def wrapped(*args, **kwargs):
            if extractor:
                try:
                    extracted = extractor(self.resolve_arguments(*args, **kwargs), self.target)
                    if extracted:
                        for name, value in extracted.items():
                            setter(name, value)
                except BaseException as ex:
                    logging.warning(
                        f"{decorator_name} decorator for {self.target.__qualname__} threw an exception during label extraction! {ex}")

            return fn(*args, **kwargs)

        return wrapped

@wrapt.decorator
class trace(object):
    extract_args = extract_args

    def __init__(self,
                 *,
                 category: Optional[str] = None,
                 attributes: Optional[typing.Mapping[Attribute, AttributeValue]] = None,
                 attribute_extractor: Optional[AttributeExtractor] = None,
                 label_extractor: Optional[AttributeExtractor] = None
                 ):

        self.signature = None
        self.category = category
        self.attributes = attributes or {}
        self.attribute_extractor = attribute_extractor
        self.label_extractor = label_extractor

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
                for a, value in self.attributes.items():
                    span.set(a, value)
                invocation = TracedInvocation(self, fn)
                wrapped_attributes = invocation.wrap_span_attributes(fn, "@trace", span.set_attribute, self.attribute_extractor)
                wrapped_labels = invocation.wrap_span_attributes(wrapped_attributes, "@trace", span.set_label, self.label_extractor)
                return wrapped_labels(*args, **kwargs)


