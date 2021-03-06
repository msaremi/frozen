from __future__ import annotations

import inspect
import itertools
import functools
from types import *
from typing import *
from collections import deque, defaultdict
from weakref import ref


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


CellType = type((lambda x: lambda: x)(None).__closure__[0])


def get_members(obj: object, superficial: bool = False) -> Generator[Tuple[str, Any]]:
	"""
	Written originally by Python authors --- modified version to increase speed
	Return all members of an object as (name, value) pairs sorted by name.
	Optionally, only return members that satisfy a given predicate.
	"""
	mro = (obj,) + obj.__mro__ if isinstance(obj, type) else ()
	processed = set()
	names = list(obj.__dict__.keys()) if superficial else dir(obj)

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

		yield key, value
		processed.add(key)


class ExecutionTracer:
	code_method_cache = dict()
	code_location_cache = dict()

	@staticmethod
	def _get_code_info(frame: FrameType, location_hint: Iterable[Type] | None = None, ):
		"""
		Given a code object, returns the (method, class) that this code belongs to.
		# :param code: The `code` object to get the info.
		:return: (method, class) tuple
		"""

		def search_locations(search_in: Iterable[Type], superficial: bool = False):
			"""
			Gets a list of candidate classes and search them to find the owner
			:param search_in: An Iterable of classes
			:param superficial: Do not search the base classes
			:return:
			"""

			def search_closure(closure: Tuple[CellType]):
				for cell in closure:
					cell_contents = cell.cell_contents

					if isinstance(cell_contents, (MethodType, FunctionType)) and cell_contents.__name__ == mtd_name:
						if code == cell_contents.__code__:
							return cell_contents, loc
						else:
							return search_closure(cell_contents.__closure__)

				return None, None

			for loc in search_in:
				if loc not in visited:
					visited.add(loc)

					for mtd_name, mtd in get_members(loc, superficial):  # Get all methods and functions of loc
						if isinstance(mtd, (MethodType, FunctionType)) and code.co_name == mtd_name:
							if code == mtd.__code__:  # If code equals the method's __code__ then the method is found
								return mtd, loc
							else:  # If they are not equal, we'll also search in the closure, which is useful when methods are decorated
								cell_method, cell_loc = search_closure(mtd.__closure__)

								if (cell_method, cell_loc) != (None, None):
									return cell_method, cell_loc
								else:  # Also, for static methods, if the code and function names are the same, we also search all subclasses
									sub_method, sub_loc = search_locations(loc.__subclasses__(), superficial=True)

									if (sub_method, sub_loc) != (None, None):
										return sub_method, sub_loc

			return None, None

		visited: Set[Type] = set()
		code = frame.f_code

		if code.co_argcount > 0:  # if code has at least one positional argument
			args = inspect.getargs(code).args  # get the arguments of the method: looking for 'self' or 'cls'
			first_arg = inspect.getargvalues(frame).locals[
				args[0]]  # first arg is either 'self' or 'cls' or neither
			cls = first_arg if isinstance(first_arg, type) else type(first_arg)  # get the 'cls' object
		else:
			cls = None

		return search_locations(itertools.chain(
			[] if cls is None else [cls],
			[] if location_hint is None else location_hint
		))

	@staticmethod
	def _get_code_info_from_cache(code: CodeType):
		method_ref = ExecutionTracer.code_method_cache[id(code)]
		location_ref = ExecutionTracer.code_location_cache[id(code)]

		if method_ref is None:
			method = None
		else:
			if method_ref() is not None:
				method = method_ref()
			else:
				raise KeyError()

		if location_ref is None:
			location = None
		else:
			if location_ref() is not None:
				location = location_ref()
			else:
				raise KeyError()

		return method, location

	@staticmethod
	def _update_code_info_cache(code: CodeType, method, location):
		if method is None:
			ExecutionTracer.code_method_cache[id(code)] = None
		else:
			ExecutionTracer.code_method_cache[id(code)] = ref(method)

		if method is None:
			ExecutionTracer.code_location_cache[id(code)] = None
		else:
			ExecutionTracer.code_location_cache[id(code)] = ref(location)

	def __call__(
			self,
			location_hint: Iterable[Type] | None = None,
			skip_frames: int = 1
	):
		frame = inspect.currentframe()

		for i in range(skip_frames):
			frame = frame.f_back

		while frame:
			try:
				method, location = ExecutionTracer._get_code_info_from_cache(frame.f_code)
			except KeyError:
				method, location = ExecutionTracer._get_code_info(frame, location_hint)
				ExecutionTracer._update_code_info_cache(frame.f_code, method, location)

			yield method, location
			frame = frame.f_back


def is_calling_class_valid(
		allowed_classes: Set[type] | None,
		from_frame: int = 0
) -> Tuple[bool, type | None]:
	calling_class = None
	found = False
	_, cls = next(trace_execution(allowed_classes, skip_frames=from_frame + 2))

	if cls is not None:
		found = next(
			(True for c in allowed_classes if issubclass(cls, c)),
			False
		)

		calling_class = cls

	return found, calling_class


def get_descendents(
		obj: object,
		include_methods: bool = False,
		visit_children: Callable[None, bool] = None
) -> Generator[Any]:
	"""
	Yields descendents of an object
	:param obj: The object to be inspected
	:param include_methods: Yield as well the member methods
	:param visit_children: A callback that determines whether the children of the last visited object should be visited.
		If `None`, always visit the children.
	:return: Yield list of descendent objects of the current object
	"""
	queue: Deque[object] = deque({obj})
	visited: Set[int] = {id(obj)}

	while queue:
		obj = queue.popleft()

		yield obj

		if visit_children is None or visit_children():
			for name, member in get_members(obj):
				if not (
						name.startswith('__') or  # Filters dunder members
						isinstance(member, BuiltinFunctionType) or  # Filters build-in members
						isinstance(member, type) or  # Filters type objects
						id(member) in visited or (  # Filters visited members to avoid infinite cycles
							# `MethodType` adds in object instance methods, class methods, lambdas, and method attributes;
							# `FunctionType` adds in static methods.
							not include_methods and
							isinstance(member, (MethodType, FunctionType))
						)
				):
					visited.add(id(member))
					queue.append(member)


def tailor_arguments(
		intended_method: Callable,
		augmented_method: Optional[Callable],
		args: tuple,
		kwargs: dict,
		ignore_intended_params: int = 0,
		ignore_augmented_params: int = 0,
) -> Tuple[Dict[str, Any], Dict[str, Any] | None]:
	"""
	Tailors the argument list prepared for one function to be fit to another.\n
	:param intended_method: The method the user intends to run.
	:param augmented_method: The method that is augmented to the intended method.
	:param args: List of positional arguments.
	:param kwargs: Dictionary of keyword arguments.
	:param ignore_intended_params: Ignores the first n number of the intended function signature.
	:param ignore_augmented_params: Ignores the first n number of the augmented function signature.
	:return: Tailored kwargs for both `intended_method` and `augmented_method`.
	"""

	try:  # Using functools' cache to keep it from recomputing the FullArgSpec
		tailor_arguments.get_args_spec
	except AttributeError:
		tailor_arguments.get_args_spec = functools.lru_cache()(inspect.getfullargspec)

	# noinspection PyTypeChecker
	intended_spec: inspect.FullArgSpec = tailor_arguments.get_args_spec(intended_method)
	intended_kwargs = kwargs.copy() if intended_spec.varkw else dict(
		(k, kwargs[k])
		for k in intended_spec.args[len(args):] + intended_spec.kwonlyargs
		if k in kwargs
	)

	if augmented_method is not None:
		# noinspection PyTypeChecker
		augmented_spec: inspect.FullArgSpec = tailor_arguments.get_args_spec(augmented_method)
		kwargs.update(dict(zip(intended_spec.args[ignore_intended_params:], args)))
		augmented_kwargs = kwargs if augmented_spec.varkw else dict(
			(k, kwargs[k])
			for k in augmented_spec.args[ignore_augmented_params:] + augmented_spec.kwonlyargs
			if k in kwargs
		)
	else:
		augmented_kwargs = None

	return intended_kwargs, augmented_kwargs


def wraps(
		wrapper: Union[Type, Callable],
		wrapped: Union[Type, Callable]
) -> None:
	"""
	Change the relevant dunders of the wrapper based on the wrapped
	:param wrapper:
	:param wrapped:
	:return:
	"""
	wrapper.__realname__ = wrapper.__name__
	"""`__realname__` is a dunder specifically used by frozen decoders. Its primary use is debugging."""
	wrapper.__name__ = wrapped.__name__
	wrapper.__qualname__ = wrapped.__qualname__
	wrapper.__doc__ = wrapped.__doc__
	wrapper.__module__ = wrapped.__module__


def locked_in_view(method: FunctionType | MethodType):
	"""
	Decorates a method to be locked in view. Used by class wrappers.
	:param method:
	:return:
	"""
	def method_wrapper(self, *args, **kwargs):
		if isinstance(self, View):
			raise PermissionError(
				Errors.ViewMethodNotCallable.format(method.__name__, type(self).__qualname__)
			)
		else:
			return method(self, *args, **kwargs)

	wraps(method_wrapper, method)
	return method_wrapper


ClassDecoratorType = TypeVar('ClassDecoratorType', bound='ClassDecorator')
ClassDecoratorDataType = TypeVar('ClassDecoratorDataType', bound='ClassDecoratorData')
MethodDecoratorType = TypeVar('MethodDecoratorType', bound='MethodDecorator')


class DecorationUsageError(Exception):
	"""
	Raised when the decorations are problematic.
	"""
	pass


class View(object):
	"""
	A proxy class of an arbitrary object.
	"""
	__proxy_cache = dict()
	__obj__ = None  # Necessary for the class to detect it as a member

	def __init__(self, obj, **kwargs):
		self.__obj__ = obj

	def __getattribute__(self, item):
		try:
			return object.__getattribute__(self, item)
		except AttributeError:
			value = getattr(self.__obj__, item)

			# If the member of obj is a method, we'll pass the proxy to it, instead of obj
			if isinstance(value, MethodType):
				value = getattr(type(self.__obj__), item)
				return value.__get__(self, type(self))
			# If the member is of one of the following type, return its view()
			# The view() method of ClassDecorator returns an ObjectView.
			# This makes recursive proxying possible.
			elif isinstance(value, ClassWrapperBase):
				return value.view()
			else:
				return value

	def __setattr__(self, key, value):
		try:
			object.__getattribute__(self, key)  # Raises error if key is not in self
			object.__setattr__(self, key, value)
		except AttributeError:
			setattr(self.__obj__, key, value)

	def __delattr__(self, item):
		try:
			object.__getattribute__(self, item)
			object.__delattr__(self, item)
		except AttributeError:
			return delattr(self.__obj__, item)

	@classmethod
	def _create_class_proxy(cls, object_class: type) -> type:
		"""
		The factory method that creates a proxy class based on class `object_class`
		:param object_class: The type based on which the proxy class will be create
		:return: The proxy class
		"""
		def make_method(method_name):
			def method(*args, **kwargs):
				return getattr(args[0].__obj__, method_name)(*args[1:], **kwargs)

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

		# Remember: `proxy_class` (the returned class) inherits `__new__` from
		# `View` (this class) or `object_class` if I do not redeclare it.
		# The `__new__` method is called when the proxy is being copied and
		# it must be `object`'s `__new__`.
		special_methods[object.__new__.__name__] = object.__new__
		return type(cls.__name__, (cls,), special_methods)

	def __new__(cls, obj, *args, **kwargs):
		"""
		Creates a new Proxy(type(obj)) class
		:param obj: The object for whose type the proxy is created/returned.
		:param args:
		:param kwargs:
		"""

		main_class = type(obj)

		try:
			proxy_class = cls.__proxy_cache[main_class]
		except KeyError:
			proxy_class = cls._create_class_proxy(main_class)
			wraps(proxy_class, main_class)
			cls.__proxy_cache[main_class] = proxy_class

		return object.__new__(proxy_class)


class MultiView:
	"""
	A MultiView class; a View class for multiple decorators. Returns a MultiView class that inherits from `View`.
	"""
	__combination_cache = dict()

	@classmethod
	def _create_multi_class(cls, classes: Tuple[Type[View], ...]):
		def __init__(self, obj: object, **kwargs):
			"""
			Call all `__init__` methods; ignore those view classes that do not define `__init__`
			"""
			for c in classes:
				if object.__init__.__name__ in c.__dict__:
					tailored_kwargs, _ = tailor_arguments(
						intended_method=c.__init__,
						augmented_method=None,
						args=tuple(),
						kwargs=kwargs,
						ignore_intended_params=2
					)
					c.__init__(self, obj, **tailored_kwargs)

			View.__init__(self, obj)

		def view(self: View, **kwargs):
			"""
			Returns a view of a view.
			:param self: The view object.
			:param kwargs:
			:return: The view of view object.
			"""
			multi_obj: View = object.__new__(type(self))
			multi_obj.__init__(self, **kwargs)
			return multi_obj

		name = f"{MultiView.__name__}[{', '.join(c.__qualname__ for c in classes)}]"
		methods = {
			object.__init__.__name__: __init__,
			object.__new__.__name__: object.__new__,
			view.__name__: view
		}
		return type(name, classes, methods)

	def __new__(cls, classes: FrozenSet[Type[View]], obj: object, **kwargs):
		try:
			multi_class = cls.__combination_cache[classes]
		except KeyError:
			multi_class = cls._create_multi_class(tuple(classes))
			cls.__combination_cache[classes] = multi_class

		multi_obj: View = object.__new__(multi_class)
		multi_obj.__init__(obj, **kwargs)  # Since Python does not invoke multi_obj.__init__
		return multi_obj


class ClassWrapperBase(Generic[ClassDecoratorDataType]):
	__decorator__: ClassDecoratorDataType
	__cls__: type

	@staticmethod
	def __is_wrapper(cls: Type[ClassWrapperBase] | type) -> bool:
		"""
		Checks if cls is a class wrapper, i.e. ClassWrapperBase's grandchild.\n
		:param cls: The class to be checked
		:return: `True` or `False`
		"""
		return (
				len(cls.__bases__) == 2 and
				len(cls.__bases__[1].__bases__) > 0 and
				cls.__bases__[1].__bases__[0] == ClassWrapperBase
		)

	@staticmethod
	def __get_wrapper_view(cls: type) -> Type[View]:
		"""
		Get the wrapper view of a wrapper.\n
		:param cls: The wrapper.
		:return:
		"""
		base: Type[ClassWrapperBase] | type = cls.__bases__[1]
		return base.View

	def __init_subclass__(cls: Type[ClassWrapperBase] | type, **kwargs):
		if ClassWrapperBase.__is_wrapper(cls):
			if ClassWrapperBase.__is_wrapper(cls.__bases__[0]):
				# noinspection PyUnresolvedReferences
				cls.__cls__ = cls.__bases__[0].__cls__
			else:
				cls.__cls__ = cls.__bases__[0]

	def __init__(self, args, kwargs, wrapper_cls: Type[ClassWrapperBase]):
		"""
		__init__ super-method to be overridden by ClassWrappers.\n
		:param args: packed *args of the child __init__
		:param kwargs: packed **kwargs of the child __init__
		:param wrapper_cls: The wrapper class whose __init__ has been called
		"""

		# The function to be replaced by object.__init__;
		# object.__init__'s signature takes both *args and **kwargs,
		# but raises an error if called by those arguments.
		# noinspection PyShadowingNames
		def object__init__(self):
			return self

		wrapped_cls: Type[ClassWrapperBase] | type = wrapper_cls.__bases__[0]
		parent_cls: Type[ClassWrapperBase] | type = wrapper_cls.__bases__[1]
		decorated_cls = wrapper_cls.__cls__
		intended_method = object__init__ if decorated_cls.__init__ == object.__init__ else decorated_cls.__init__
		intended_kwargs, augmented_kwargs = tailor_arguments(
			intended_method=intended_method,
			augmented_method=parent_cls.__load__,
			ignore_intended_params=1,
			ignore_augmented_params=1,
			args=args,
			kwargs=kwargs
		)
		# Call `__init__`'s bottom to top and then call the decorated class's `__init__`!
		# Call `wrapped_cls.__init__` with kwargs if it is a ClassWrapper; else, with intended_kwargs.
		parent_cls.__load__(self, **augmented_kwargs)
		wrapped_cls.__init__(self, *args, **(intended_kwargs if wrapped_cls == decorated_cls else kwargs))

		# if wrapped_cls == decorated_cls:
		# 	parent_cls.__load__(self, **augmented_kwargs)
		# 	wrapped_cls.__init__(self, *args, **intended_kwargs)
		# else:
		# 	wrapped_cls.__init__(self, *args, **kwargs)
		# 	parent_cls.__load__(self, **augmented_kwargs)

	def __load__(self, **kwargs):
		raise NotImplementedError(Errors.MethodNotImplemented.format(self.__load__.__qualname__))

	def view(self, **kwargs):
		"""
		Returns a view of the decorated object. Handles all frozen decorations and returns a MultiView.
		Do not overload, unless you want to make it un-implemented!
		:param kwargs:
		:return:
		"""
		view_classes: Set[Type[View]] = set()

		for cls in type(self).mro():
			if ClassWrapperBase.__is_wrapper(cls):
				view_cls = ClassWrapperBase.__get_wrapper_view(cls)
				view_classes.add(view_cls)

		return MultiView(frozenset(view_classes), self, **kwargs)

	class View(View):
		"""
		The base View class of a decorator.
		"""
		pass


class ClassDecoratorData:
	"""
	ClassDecoratorData base class.
	"""
	pass


class ClassDecorator(Generic[ClassDecoratorType, MethodDecoratorType]):
	_decorator_function: FunctionType = None
	_method_decorator: Type[MethodDecoratorType] = None
	_class_wrapper_base: Type[ClassWrapperBase] = None

	@classmethod
	def get_wrapper_class(cls, target_cls: type) -> Type[ClassWrapperBase] | type | None:
		wrapper_type = cls._class_wrapper_base

		for c in target_cls.__mro__:
			if len(c.__bases__) == 2 and c.__bases__[1] == wrapper_type:
				return c

		return None

	# noinspection PyProtectedMember
	@property
	def method_specs(self) -> Set[MethodSpec[ClassDecoratorType, MethodDecoratorType]]:
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
		"""
		The decorated method that this object is holding the specs.
		"""
		return self._method

	@property
	def decorated_module(self) -> ModuleType:
		"""
		The decorated method's module that this object is holding the specs.
		"""
		return inspect.getmodule(self._method)

	@property
	def decorated_class_qualname(self) -> str:
		"""
		The decorated method's class qualname that this object is holding the specs.
		"""
		method_qualname = self._method.__qualname__
		return method_qualname[:method_qualname.rfind('.')]

	@property
	def method_decorator(self) -> MethodDecoratorType:
		"""
		The method decorator object of the decorated method.
		"""
		return self._decorator

	@property
	def method_decorator_type(self) -> Type[MethodDecoratorType]:
		"""
		The method decorator class of the decorated method.
		"""
		return type(self._decorator)

	@property
	def method_decorator_name(self) -> str:
		"""
		The method decorator function name used to decorate the decorated method.
		"""
		# noinspection PyProtectedMember
		return self._decorator._decorator_function.__name__

	@property
	def class_decorator_type(self) -> Type[ClassDecoratorType]:
		"""
		The pairing class decorator class of the method decorator class of the decorated method.
		"""
		# noinspection PyProtectedMember
		return self._decorator._class_decorator

	@property
	def class_decorator_name(self) -> str:
		"""
		The pairing class decorator function name used along with this method's method decorator.
		"""
		# noinspection PyProtectedMember
		return self._decorator._class_decorator._decorator_function.__name__

	def has_same_class(self, other: MethodSpec[ClassDecoratorType, MethodDecoratorType]) -> bool:
		"""
		Returns `True` if the methods of `self` and `other` specs belong to the same class.
		"""
		return (
				self.decorated_module == other.decorated_module and
				self.decorated_class_qualname == other.decorated_class_qualname
		)


class ModuleElements:
	"""
	Can be inherited by internal classes.
	"""
	def __call__(self, *args, **kwargs):
		raise NotImplementedError(Errors.MethodNotImplemented.format(ModuleElements.__call__.__qualname__))

	# @staticmethod
	# def cls(*args, **kwargs) -> ClassDecorator:
	# 	raise NotImplementedError(Errors.MethodNotImplemented.format(ModuleElements.cls.__qualname__))

	@staticmethod
	def method(*args, **kwargs) -> MethodDecorator:
		raise NotImplementedError(Errors.MethodNotImplemented.format(ModuleElements.method.__qualname__))


current_decorator_specs: DefaultDict[Type, Set[MethodSpec[ClassDecoratorType, MethodDecoratorType]]] = \
	defaultdict(lambda: set())
"""
Hold information about the current class that is being decorated. 
Used to make sure that the process is being done correctly.
"""
trace_execution = ExecutionTracer()