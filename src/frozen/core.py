from __future__ import annotations

import inspect
import itertools
import functools
from types import *
from typing import *
from collections import deque, defaultdict


class Errors:
	"""
	List of error messages in this module. Can be extended by other modules to express error messages.
	For internal use only.\n
	:cvar MethodNotImplemented: General error message for non-implemented methods of the base class.
	:cvar CallWithClassArg: Error message for when the class decorator has not been called with a class argument.
	:cvar CallWithMethodArg: Error message for when the method decorator has not been called with a method argument.
	:cvar ClassNotFinalized: Error message for when the methods of the class have been decorated,
		but the class itself has not.
	:cvar ViewMethodNotCallable: General error for when a method on a view object is not callable.
	"""
	MethodNotImplemented = \
		"`{}` method is not implemented."
	CallWithClassArg = \
		"`{}` class can only be called with class arguments."
	CallWithMethodArg = \
		"`{}` class can only be called with method arguments."
	ClassNotFinalized = \
		"`{}` class has not been finalized using a `{}` decorator."
	ViewMethodNotCallable = \
		"`{}` method is not callable on `{}` view objects."


def get_members(
		obj: type | object,
		predicate: Callable[[str, Any], bool] | None = None
) -> Generator[Tuple[str, Any]]:
	"""
	Written originally by Python authors --- modified version to increase speed
	Return all members of an object as (name, value) pairs sorted by name.
	Optionally, only return members that satisfy a given predicate.
	"""
	mro = (obj,) + obj.__mro__ if isinstance(obj, type) else ()
	processed = set()
	names = dir(obj)

	# :dd any DynamicClassAttributes to the list of names if object is a class;
	# this may result in duplicate entries if, for example, a virtual
	# attribute with the same name as a DynamicClassAttribute exists
	try:
		for base in obj.__bases__:
			for k, v in base.__dict__.items():
				if isinstance(v, DynamicClassAttribute):
					names.append(k)
	except AttributeError:
		pass

	for key in names:
		# First try to get the value via getattr.  Some descriptors don't
		# like calling their __get__ (see bug #1785), so fall back to
		# looking in the __dict__.
		try:
			value = getattr(obj, key)

			# handle the duplicate key
			if key in processed:
				raise AttributeError
		except AttributeError:
			for base in mro:
				if key in base.__dict__:
					value = base.__dict__[key]
					break
			else:
				# could be a (currently) missing slot member, or a buggy
				# __dir__; discard and move on
				continue

		if not predicate or predicate(key, value):
			yield key, value

		processed.add(key)


def trace_execution(
		location_hint: Iterable[Type] | None = None
) -> Generator[Tuple[MethodType | FunctionType, type] | Tuple[None, None]]:
	"""
	Yields the list of (method, class)'s of the current execution frame
	If the methods are not @staticmethod the algorithm finds the classes directly
	If the methods are `@staticmethod` the algorithm searches in `locations_hint` and their subclasses
	:param location_hint: List of candidate classes to search in.
	:return: Yields (method, location) frame-by-frame in execution stack.
	"""
	def get_code_info(code):
		"""
		Given a code object, returns the (method, class) that this code belongs to.
		:param code: The `code` object to get the info.
		:return: (method, class) tuple
		"""
		def search_locations(search_in: Iterable[Type]):
			"""
			Gets a list of candidate classes and search them to find the owner
			:param search_in: and Iterable of classes
			:return: 
			"""
			for loc in search_in:
				for method_name, method in get_members(  # Get all methods and functions of loc
						loc,
						lambda _, x: isinstance(x, (MethodType, FunctionType))
				):
					if code.co_name == method_name:
						if code == method.__code__:  # If code equals the method's __code__ then the method is found
							return method, loc
						else:  # However, for static methods, if the code and function names are the same, we also search all subclasses
							method, loc = search_locations(loc.__subclasses__())

							if (method, loc) != (None, None):
								return method, loc

			return None, None

		if code.co_argcount > 0:  # if code has at least one positional argument
			args = inspect.getargs(code).args  # get the arguments of the method: looking for 'self' or 'cls'
			first_arg = inspect.getargvalues(frame).locals[args[0]]  # first arg is either 'self' or 'cls' or neither
			cls = first_arg if isinstance(first_arg, type) else type(first_arg)  # get the 'cls' object
		else:
			cls = None

		return search_locations(itertools.chain(
			[] if cls is None else [cls],
			[] if location_hint is None else location_hint
		))

	try:  
		# Check if `get_code_info` exists as an attribute; else create it.
		trace_execution.get_code_info
	except AttributeError:
		# It sets the cached version of `get_code_info`. Caching keeps it from calling 
		# `get_code_info` over and over 
		trace_execution.get_code_info = functools.lru_cache()(get_code_info)

	frame = inspect.currentframe().f_back  # `f_back` to get the caller frame

	while frame:
		yield trace_execution.get_code_info(frame.f_code)
		frame = frame.f_back


def get_object_descendents(
		obj: object,
		include_methods: bool = False
) -> Generator[Any]:
	"""
	Yields descendents of an object
	:param obj: The object to be inspected
	:param include_methods: Yield as well the member methods
	:return: Yield list of descendent objects of the current object
	"""
	queue: Deque[object] = deque({obj})
	visited: Set[int] = {id(obj)}

	while queue:
		obj = queue.popleft()

		yield obj

		members = get_members(
			obj,
			lambda k, x:
				not k.startswith('__') and  # filters private members
				not isinstance(x, BuiltinFunctionType) and  # filters build-in members
				not isinstance(x, type) and  # filters type objects
				not id(x) in visited and (  # filters visited members to avoid infinite cycles
					include_methods or not (
						# filters object methods, class methods, lambdas, and method attributes / static methods
						isinstance(x, (MethodType, FunctionType))
					)
				)
		)

		for name, obj in members:
			visited.add(id(obj))
			queue.append(obj)


def tailor_arguments(
		intended_method: Callable,
		augmented_method: Callable,
		has_self: bool = True,
		*args, **kwargs
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
	"""
	Tailors the argument list prepared for one function to be fit to another
	:param intended_method:
	:param augmented_method:
	:param has_self: If the functions take the 'self' argument
	:param args: List of positional arguments
	:param kwargs: Dictionary of keyword arguments
	:return: Tailored kwargs
	"""
	try:  # Using functool's cache to keep it from running over and over
		tailor_arguments.get_args_spec
	except AttributeError:
		tailor_arguments.get_args_spec = functools.lru_cache()(inspect.getfullargspec)

	def f(*_):
		pass

	# noinspection PyTypeChecker
	intended_spec = tailor_arguments.get_args_spec(intended_method if intended_method else f)
	# noinspection PyTypeChecker
	augmented_spec = tailor_arguments.get_args_spec(augmented_method if augmented_method else f)
	intended_kwargs = kwargs if intended_spec.varkw else dict(
		(k, kwargs[k]) for k in intended_spec.args if k in kwargs
	)
	# Since `self` is not ordinarily distinguishable
	# from other first args, it's passed explicitly
	start = 1 if has_self else 0   
	kwargs.update(dict(zip(intended_spec.args[start:], args[start:])))
	augmented_kwargs = kwargs if augmented_spec.varkw else dict(
		(k, kwargs[k]) for k in augmented_spec.args[start:] if k in kwargs
	)

	return intended_kwargs, augmented_kwargs


def wraps(
		wrapper: Union[Type, Callable],
		wrapped: Union[Type, Callable]
) -> None:
	"""
	Change the dunders of wrapper based on the wrapped
	:param wrapper:
	:param wrapped:
	:return:
	"""
	wrapper.__realname__ = wrapper.__name__
	wrapper.__name__ = wrapped.__name__
	wrapper.__qualname__ = wrapped.__qualname__
	wrapper.__doc__ = wrapped.__doc__
	wrapper.__module__ = wrapped.__module__


def forward_declarable(cls):
	method = cls.__class_getitem__

	def __class_getitem__wrapper(item):
		if isinstance(item, type) and issubclass(item, ForwardDec):
			item = item.__qualname__

		return method(item)

	cls.__class_getitem__ = __class_getitem__wrapper
	return cls


def locked_in_view(mth):
	def method_wrapper(self, *args, **kwargs):
		if isinstance(self, View):
			raise PermissionError(
				Errors.ViewMethodNotCallable.format(mth.__name__, type(self).__qualname__)
			)
		else:
			return mth(self, *args, **kwargs)

	return method_wrapper


class ForwardDec:
	pass


ClassDecoratorType = TypeVar('ClassDecoratorType', bound='ClassDecorator')
MethodDecoratorType = TypeVar('MethodDecoratorType', bound='MethodDecorator')


class DecorationUsageError(Exception):
	pass


class View(object):
	"""
	A proxy class of an arbitrary object.
	"""
	__proxy_cache = dict()
	__obj = None  # Necessary for the class to detect it as a member

	def __init__(self, obj):
		self.__obj = obj

	def __getattribute__(self, item):
		try:
			return object.__getattribute__(self, item)
		except AttributeError:
			value = getattr(self.__obj, item)

			# If the member of obj is a method, we'll pass the proxy to it, instead of obj
			if isinstance(value, MethodType):
				value = getattr(type(self.__obj), item)
				return value.__get__(self, type(self))
			# If the member is of one of the following type, return its view()
			# The view() method of ClassDecorator returns an ObjectView.
			# This makes recursive proxying possible.
			elif isinstance(value, ClassDecorator.ClassWrapper):
				return value.view()
			else:
				return value

	def __setattr__(self, key, value):
		try:
			object.__getattribute__(self, key)  # Raises error if key is not in self
			object.__setattr__(self, key, value)
		except AttributeError:
			setattr(self.__obj, key, value)

	def __delattr__(self, item):
		try:
			object.__getattribute__(self, item)
			object.__delattr__(self, item)
		except AttributeError:
			return delattr(self.__obj, item)

	@classmethod
	def _create_class_proxy(cls, object_class: type) -> type:
		"""
		The factory method that creates a proxy class based on class `object_class`
		:param object_class: The type based on which the proxy class will be create
		:return: The proxy class
		"""
		def make_method(method_name):
			def method(self, *args, **kw):
				return getattr(self._obj, method_name)(*args, **kw)

			return method

		# The dictionary holds python's special methods present in object_class
		special_methods = dict()

		for name in dir(object_class):
			value = getattr(object_class, name)

			if (
					not hasattr(cls, name) and  # if this cls does not have the method (we don't want to override this methods)
					isinstance(value, (WrapperDescriptorType, MethodDescriptorType))  #
					# WrapperDescriptorType == type(object.__init__), MethodDescriptorType == type(str.join)
			):
				special_methods[name] = make_method(name)

		return type(cls.__name__, (cls,), special_methods)

	def __new__(cls, *args, **kwargs):
		"""
		Creates a new Proxy(type(obj)) class
		:param obj: The object for whose type the proxy is created/returned.
		:param args:
		:param kwargs:
		"""
		# Reason for improvement of the function. The previous version raises error if calling copy() after view()
		# File "...\lib\copyreg.py", line 88, in __newobj__
		#   return cls.__new__(cls, *args)
		# TypeError: __new__() missing 1 required positional argument: 'obj'

		if len(args) == 0:  # When cls is being copied
			return object.__new__(cls)
		else:  # When new cls is created based on an obj
			obj = args[0]
			main_class = type(obj)

			try:
				proxy_class = cls.__proxy_cache[main_class]
			except KeyError:
				proxy_class = cls._create_class_proxy(main_class)
				wraps(proxy_class, main_class)
				cls.__proxy_cache[main_class] = proxy_class

			return object.__new__(proxy_class)


@forward_declarable
class ClassDecorator(Generic[ClassDecoratorType, MethodDecoratorType]):
	_decorator_function: FunctionType = None
	_method_decorator: Type[MethodDecoratorType] = None

	class ClassWrapper:
		def __init__(self, calling_class: Type[ClassDecoratorType.ClassWrapper], wrapped_class, *args, **kwargs):
			"""
			__init__ super-method to be overridden by ClassWrappers
			overriding
			:param calling_class:
			:param args:
			:param kwargs:
			"""
			# Search the `mro` and find the first non-wrapped class to extract its __init__ signature
			# This class is the one that user enters the arguments based on, therefore, we extract its parameters
			i, intended_class = next((
				(i, cls) for i, cls in enumerate(calling_class.mro())
				if not issubclass(cls, ClassDecorator.ClassWrapper)
			))
			__init__ = None if intended_class.__init__ == object.__init__ else intended_class.__init__
			intended_kwargs, construct_kwargs = tailor_arguments(
				__init__, calling_class.__construct__, True, self, *args, **kwargs
			)
			calling_class.__construct__(self, **construct_kwargs)
			# Call wrapped_class with kwargs if it is a ClassDecorator; else, with intended_kwargs
			wrapped_class.__init__(self, *args, **(intended_kwargs if i == 1 else kwargs))

		def __construct__(self, **kwargs):
			raise NotImplementedError(Errors.MethodNotImplemented.format(self.__construct__.__qualname__))

		def view(self):
			raise NotImplementedError(Errors.MethodNotImplemented.format(self.view.__qualname__))

	# noinspection PyProtectedMember
	@property
	def _method_specs(self) -> Set[MethodSpec[ClassDecoratorType, MethodDecoratorType]]:
		return current_decorator_specs[type(self)]

	def __call__(self, cls, wrapper: type = None):
		"""
		Sanitizes the class cls and returns a wrapper.
		Called twice by the child class!
		:param cls:
		:return:
		"""
		if wrapper is None:  # First call
			if not isinstance(cls, type):
				raise TypeError(Errors.CallWithClassArg.format(type(self).__name__))
		else:  # Second call
			try:  # If method wrapper has not been used for this class, the entry has not been formed
				del current_decorator_specs[type(self)]
			except KeyError:
				pass
			wraps(wrapper, cls)
			return wrapper


@forward_declarable
class MethodDecorator(Generic[ClassDecoratorType, MethodDecoratorType]):
	"""
	Base method decorator class. For internal use only.\n
	:cvar _decorator_function: The decorator function that is publicly available.
	:cvar _class_decorator: The pared class decorator.
	"""
	_decorator_function: FunctionType = None
	_class_decorator: Type[ClassDecoratorType] = None
	__last_decorator_spec: Optional[MethodSpec[ClassDecoratorType, MethodDecoratorType]] = None

	def __call__(self, method: Callable, wrapper: Callable = None):
		if wrapper is None:
			if not isinstance(method, FunctionType):  # Remember that methods are functions before they are bound to classes
				raise TypeError(Errors.CallWithMethodArg.format(type(self).__name__))

			spec = MethodSpec[ClassDecoratorType, MethodDecoratorType](method, self)

			if (  # If the previous class has been finalized or we're still on the same class
					MethodDecorator.__last_decorator_spec is None or  # First time a method is decorated
					len(current_decorator_specs) == 0 or  # First time a method is decorated on the new class
					MethodDecorator.__last_decorator_spec.has_same_class(spec)  # We're still on the current class
			):
				# Save the last wrapper for comparison to the next one, and store the decorator spec in a dictionary
				MethodDecorator.__last_decorator_spec = spec
				current_decorator_specs[spec.class_decorator_type].add(spec)
			else:
				raise DecorationUsageError(
					Errors.ClassNotFinalized.format(
						MethodDecorator.__last_decorator_spec.decorated_class_qualname,
						current_decorator_specs[spec.class_decorator_type].pop().class_decorator_name
					)
				)
		else:
			wraps(wrapper, method)
			return wrapper


class MethodSpec(Generic[ClassDecoratorType, MethodDecoratorType]):
	"""
	Holds a wrapped method specifications.
	This will be used by the ClassDecorator to track the decorated functions. For internal use only.
	"""
	def __init__(self, method: Callable, decorator: MethodDecoratorType):
		self._method = method
		self._decorator = decorator

	@property
	def decorated_method(self) -> Callable:
		return self._method

	@property
	def decorated_module(self) -> ModuleType:
		return inspect.getmodule(self._method)

	@property
	def decorated_class_qualname(self) -> str:
		method_qualname = self._method.__qualname__
		return method_qualname[:method_qualname.rfind('.')]

	@property
	def method_decorator(self) -> MethodDecoratorType:
		return self._decorator

	@property
	def method_decorator_type(self) -> Type[MethodDecoratorType]:
		return type(self._decorator)

	@property
	def method_decorator_name(self) -> str:
		# noinspection PyProtectedMember
		return self._decorator._decorator_function.__name__

	@property
	def class_decorator_type(self) -> Type[ClassDecoratorType]:
		# noinspection PyProtectedMember
		return self._decorator._class_decorator

	@property
	def class_decorator_name(self) -> str:
		# noinspection PyProtectedMember
		return self._decorator._class_decorator._decorator_function.__name__

	def has_same_class(self, other: MethodSpec[ClassDecoratorType, MethodDecoratorType]) -> bool:
		return (
				self.decorated_module == other.decorated_module and
				self.decorated_class_qualname == other.decorated_class_qualname
		)


class ModuleElements:
	"""
	Can be inherited by internal classes.
	"""
	def __init__(self, mth, cls):
		self._mth = mth
		self._cls = cls

	@property
	def mth(self) -> Callable:
		return self._mth

	@property
	def cls(self) -> Callable:
		return self._cls


current_decorator_specs: DefaultDict[Type, Set[MethodSpec[ClassDecoratorType, MethodDecoratorType]]] = \
	defaultdict(lambda: set())
