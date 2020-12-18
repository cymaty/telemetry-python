import inspect
import logging
import typing
from enum import Enum
from typing import Dict, Optional

import wrapt

from telemetry.api.trace import Attributes

ArgumentTagger = typing.Callable[[any], Optional[str]]
AttributeExtractor = typing.Callable[[Dict[str, any], typing.Callable[[any], any]], Dict[str, any]]

def extract_args(*args: str) -> Optional[AttributeExtractor]:
    def extract(values: Dict[str, any], fn) -> Dict[str, any]:
        out = {}
        for name in args:
            if name not in values:
                logging.warning(
                    f"@trace decorator refers to an argument, {name}, that was not found in the "
                    f"signature for {fn.__qualname__}! (this tag will not be added)")
            else:
                out[name] = values[name]
        return out
    return extract


@wrapt.decorator
class trace(object):
    def __init__(self,
                 category: Optional[str] = None,
                 tags: Optional[Dict[str, str]] = None,
                 attributes: Optional[Attributes] = None,
                 attribute_extractor: Optional[AttributeExtractor] = None,
                 tag_extractor: Optional[AttributeExtractor] = None
                 ):

        self.signature = None
        self.category = category
        self.tags = tags
        self.attributes = attributes
        self.attribute_extractor = attribute_extractor
        self.tag_extractor = tag_extractor

    def _get_category(self, fn, instance):
        import inspect
        if hasattr(self, 'category') and self.category:
            return self.category
        elif instance:
            if hasattr(instance, 'telemetry_category'):
                return getattr(instance, 'telemetry_category')
            else:
                return self.instance.__class__.__qualname__
        else:
            return inspect.getmodule(fn).__name__

    def _extract_arg_values(self, args, kwargs, fn):
        import inspect

        # initialize with explicitly-passed kwargs
        arg_values = kwargs.copy()

        # resolve the function signature (if not yet resolved)
        if self.signature is None:
            self.signature = inspect.signature(fn)

        def set_arg_value(name: str, value: any):
            # if None value, then set to predefined value of 'none_value'
            if value is None or value is inspect.Parameter.empty:
                arg_values[name] = self.none_value
                return

            # if value is an enum, then extract the name
            if isinstance(value, Enum):
                value = value.name

            arg_values[name] = value

        for i, (name, param) in enumerate(self.signature.parameters.items()):
            if name == 'self' or name in arg_values:
                continue

            # we have positional argument
            if i < len(args):
                set_arg_value(name, args[i])
            else:
                if param.default:
                    set_arg_value(name, param.default)

        return arg_values

    def __call__(self, fn, instance, args, kwargs):
        from telemetry import telemetry

        if self.signature is None:
            self.signature = inspect.signature(fn)

        with telemetry.tracer.span(self._get_category(fn, instance), fn.__name__) as span:
            if self.tags:
                for k, v in self.tags.items():
                    span.set_tag(k, v)
            if self.attributes:
                for k, v in self.attributes.items():
                    span.set_attribute(k, v)

            # optimization that checks whether we should extract argument
            if self.attribute_extractor or self.tag_extractor:
                # extract argument values
                arg_values = self._extract_arg_values(args, kwargs, fn)
                if self.tag_extractor:
                    try:
                        extracted = self.tag_extractor(arg_values, fn)
                        if extracted:
                            for name, value in extracted.items():
                                span.set_tag(name, value)
                    except BaseException as ex:
                        logging.warning(
                            f"@trace decorator for {fn.__qualname__} threw and exception during tag extraction! {ex}")

                if self.attribute_extractor:
                    try:
                        extracted = self.attribute_extractor(arg_values, fn)
                        if extracted:
                            for name, value in extracted.items():
                                span.set_attribute(name, value)
                    except BaseException as ex:
                        logging.warning(
                            f"@trace decorator for {fn.__qualname__} threw and exception during attribute extraction! {ex}")

            return fn(*args, **kwargs)

