"""
This module adds the alienability feature to classes
"""

from __future__ import annotations
from frozen.core import *


class Errors(Errors):
	"""
	List of error messages in this module.
	:cvar CallingAlienMethod: Error message for when an alien method is called.
	:cvar NoFriendsDefined: Error message for when no friends have been introduced to the decorator.
	"""
	CallingAlienMethod = \
		"Alien `{}` object is not allowed to call `{}` method."
	NoFriendsDefined = \
		"No friends have been defined for `{}` decorator. " \
		"Use `friends` parameter to define the friends."


class AlienError(PermissionError):
	pass


class Alienatable(ClassWrapperBase['AlienatableClassDecoratorData']):
	def __load__(self, locks: Iterable[str] = None) -> None:
		pass

	def __alien_error__(self, calling_cls: type, method: Callable) -> None:
		"""
		Raises an error when an alien method is called. Can be overridden. \n
		:param method: The frozen method that was called.
		:raises FrozenError: Always raises an error.
		"""
		raise AlienError(Errors.CallingAlienMethod.format(
				None if calling_cls is None else calling_cls.__qualname__,
				method.__qualname__
		))


def alienatableclass(
		*args,
		friends: Dict[str, Optional[Set[type]]] | Set[type] = None
):
	if args:
		cls = args[0]
		return alienatable.cls()(cls)
	else:
		return alienatable.cls(friends=friends)


class AlienatableClassDecorator(ClassDecorator['AlienatableClassDecorator', 'AlienatableMethodDecorator']):
	def __init__(self, friends: Union[Dict[str, Optional[Set[Type]]], Set[Type]] = None):
		if friends is None:
			raise ValueError(Errors.NoFriendsDefined.format(self._decorator_function.__qualname__))
		elif isinstance(friends, dict):
			friends = friends.items()
		elif isinstance(friends, Iterable):
			friends = {None: friends}.items()

		friends = dict((k, frozenset(v)) for k, v in friends)
		self.friends: DefaultDict = defaultdict(lambda: frozenset(), friends)

	def __call__(self, cls, *_):
		super().__call__(cls)

		class AlienatableWrapper(cls, Alienatable):
			__decorator__ = AlienatableClassDecoratorData(self, cls)

			def __init__(*args, **kwargs):
				Alienatable.__init__(
					self=args[0],
					args=args[1:],
					kwargs=kwargs,
					wrapper_cls=AlienatableWrapper,
				)

		super().__call__(cls, AlienatableWrapper)
		return AlienatableWrapper


class AlienatableClassDecoratorData(ClassDecoratorData):
	friends: DefaultDict[str, Optional[Set[type]]]

	def __init__(
			self,
			decorator: AlienatableClassDecorator,
			cls: type
	):
		self.friends = decorator.friends

		# for spec in decorator.method_specs:
		# 	self.friends.update(spec.method_decorator.friend_list)

		if issubclass(cls, Alienatable):
			wrapper = AlienatableClassDecorator.get_wrapper_class(cls)

			for key, cls_set in wrapper.__decorator__.friends.items():
				if self.friends[key] is None:
					self.friends[key] = cls_set
				else:
					self.friends[key].update(cls_set)


def alienatablemethod(*args, friend_list: Iterable[str] | str = None):
	if args:
		method = args[0]
		return alienatable.mth()(method)
	else:
		return alienatable.mth(friend_list=friend_list)


class AlienatableMethodDecorator(MethodDecorator['AlienatableClassDecorator', 'AlienatableMethodDecorator']):
	def __init__(self, friend_list: Iterable[str] | str = None):
		if isinstance(friend_list, Iterable):
			self.friend_list = frozenset(friend_list)
		elif isinstance(friend_list, str):
			self.friend_list = frozenset({friend_list})
		elif friend_list is None:
			self.friend_list = frozenset()

	@functools.lru_cache()
	def get_valid_classes(self, cls):
		wrapper = AlienatableClassDecorator.get_wrapper_class(cls)
		friends = wrapper.__decorator__.friends if wrapper is not None else set()
		allowed_classes = set().union(*(friends[key] for key in self.friend_list | {None}))
		return allowed_classes

	def __call__(self, method: Callable, *_):
		super().__call__(method)

		def alienatable_wrapper(*args, **kwargs):
			obj = args[0]

			if isinstance(obj, Alienatable) or isinstance(obj, View):
				allowed_classes = self.get_valid_classes(type(obj))
				found, calling_classes = is_calling_class_valid(allowed_classes)

				if found:
					return method(*args, **kwargs)
				else:
					obj.__alien_error__(calling_classes[0], method)
			else:
				raise DecorationUsageError(
					Errors.ClassNotFinalized.format(
						obj.__class__.__qualname__,
						alienatableclass.__name__
					)
				)

		return super().__call__(method, alienatable_wrapper)


class ModuleElements(ModuleElements):
	@staticmethod
	def cls(friends: Dict[str, Optional[Set[type]]] | Set[type] = None) -> AlienatableClassDecorator:
		return AlienatableClassDecorator(friends=friends)

	@staticmethod
	def mth(friend_list: Iterable[str] | str = None) -> AlienatableMethodDecorator:
		return AlienatableMethodDecorator(friend_list=friend_list)


AlienatableClassDecorator._decorator_function = alienatableclass
AlienatableClassDecorator._class_wrapper_base = Alienatable
AlienatableClassDecorator._method_decorator = AlienatableMethodDecorator
AlienatableMethodDecorator._decorator_function = alienatablemethod
AlienatableMethodDecorator._class_decorator = AlienatableClassDecorator
alienatable = ModuleElements()
