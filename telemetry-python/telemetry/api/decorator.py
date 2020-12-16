import logging
import typing
from decimal import Decimal
from enum import Enum
from typing import Dict, Optional

from opentelemetry.util.types import Attributes

from telemetry.api.telemetry import _repo_url


class trace:
    argument_types = (str, int, float, bool, Decimal, Enum)
    none_value = None

    def __init__(self,
                 *args,
                 category: Optional[str] = None,
                 tags: Optional[Dict[str, str]] = None,
                 attributes: Optional[Attributes] = None,
                 argument_tags: Optional[typing.Set[str]] = None,
                 argument_attributes: Optional[typing.Set[str]] = None):

        if len(args) == 1:
            self.function = args[0]
        else:
            self.function = None

        self.signature = None
        self.category = category
        self.tags = tags
        self.attributes = attributes
        self.argument_tags = argument_tags
        self.argument_attributes = argument_attributes

    def __set_name__(self, owner, name):
        self.owner = owner

    def __get__(self, instance, owner):
        self.instance = instance
        self.owner = owner
        from functools import partial
        return partial(self.__call__, instance)

    def get_category(self, fn):
        import inspect
        if hasattr(self, 'category') and self.category:
            return self.category
        elif hasattr(self, 'instance') and self.instance:
            if hasattr(self.owner, 'telemetry_category'):
                return getattr(self.owner, 'telemetry_category')
            else:
                return self.instance.__class__.__name__
        elif hasattr(self, 'owner') and self.owner:
            if hasattr(self.owner, 'telemetry_category'):
                return getattr(self.owner, 'telemetry_category')
            else:
                return self.owner.__name__
        else:
            return inspect.getmodule(fn).__name__

    def get_arg_values(self, args, kwargs, fn):
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

            # check that this argument is in our allowed list of types
            if type(value) not in self.argument_types:
                raise ValueError(f"Cannot set attribute/tag for argument '{name}' because it's type '{type(value)}' "
                                 f"is not in the allowed list of types.  If you think this type should be allowed, "
                                 f"then please file a bug request at {_repo_url()}")

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

    def wrapped_name(self, fn):
        import inspect

        name = fn.__name__
        if self.owner is not None:
            name = f"{self.owner.__name__}.{name}"
        elif self.instance is not None:
            name = f"{self.instance.__class__.__name__}.{name}"
        else:
            module = inspect.getmodule(fn)
            name = f"{module.__name__}.{name}"
        return name

    def decorate(self, fn):
        from telemetry import telemetry

        def wrapper(*call_args, **call_kwargs):
            with telemetry.tracer.span(self.category or self.get_category(self.function or fn), fn.__name__) as span:
                if self.tags:
                    for k, v in self.tags.items():
                        span.set_tag(k, v)
                if self.attributes:
                    for k, v in self.attributes.items():
                        span.set_attribute(k, v)

                # optimization that checks whether we should extract argument
                if self.argument_attributes or self.argument_tags:
                    # extract argument values
                    arg_values = self.get_arg_values(call_args, call_kwargs, fn)
                    if self.argument_tags:
                        for name in self.argument_tags:
                            if name not in arg_values:
                                logging.warning(
                                    f"@timed call refers to an argument, {name}, that was not found in the signature"
                                    f" for {fn.__name__}! This tag will not be added")
                            else:
                                span.set_tag(name, arg_values[name])

                    if self.argument_attributes:
                        for name in self.argument_attributes:
                            if name not in arg_values:
                                logging.warning(f"@timed call refers to an argument attribute was not found in the "
                                                f"signature for {fn.__name__}! This attribute will not be "
                                                f"added")
                            else:
                                span.set_attribute(name, arg_values[name])

                return fn(*call_args, **call_kwargs)

        return wrapper

    def __call__(self, *args, **kwargs):
        if len(args) == 1 and isinstance(args[0], typing.Callable):
            return self.decorate(args[0])
        else:
            return self.decorate(self.function)(*args, **kwargs)
