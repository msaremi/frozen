from .core import *
from collections import defaultdict


class LockedError(PermissionError):
	pass


class UnlockError(PermissionError):
	pass


class LockError(PermissionError):
	pass


def lockableclass(
		*args,
		lock_permissions: typing.Dict[str, typing.Optional[typing.Set]] = None,
		unlock_permissions: typing.Dict[str, typing.Optional[typing.Set]] = None
):
	if args:
		cls = args[0]
		return LockableClass()(cls)
	else:
		return LockableClass(lock_permissions=lock_permissions, unlock_permissions=unlock_permissions)


class LockableClass(ClassDecorator):
	def __init__(
			self,
			lock_permissions: typing.Dict[str, typing.Optional[typing.Set]] = None,
			unlock_permissions: typing.Dict[str, typing.Optional[typing.Set]] = None
	):
		"""

		:param lock_permissions: Example: {"key1": {Class1, Class2}, "key2: {Class2, Class3}}
		:param unlock_permissions: Same as `lock_permissions`
		"""
		if lock_permissions is None:
			raise ValueError(
				f"No locks have been defined for `@{self._decorator_function}`. "
				f"Use `lock_permissions` to define the locks."
			)

		if unlock_permissions is None:
			unlock_permissions = lock_permissions

		self._locks = set(lock_permissions.keys() | unlock_permissions.keys())
		self._lock_permissions: typing.Dict = defaultdict(lambda: None, lock_permissions)
		self._unlock_permissions: typing.Dict = defaultdict(lambda: None, unlock_permissions)

	def __call__(self, cls):
		"""
		Sanitize the class cls and returns a wrapper
		:param cls:
		:return:
		"""
		super().__call__(cls)

		for func in inspect.getmembers(cls, lambda x: inspect.isfunction(x)):
			try:
				self._locks.update(func.__locks__)
			except (AttributeError, TypeError):
				pass

		class LockableWrapper(cls, ClassDecorator.ClassWrapper):
			def __init__(self, *args, **kwargs):
				# Don't use super() in this context; it's not the usual inheritence patter.
				# In case of super(), if cls does not define __init__,
				# then the MRO proceeds to run ClassDecorator.ClassWrapper.__init__
				cls.__init__(self, *args, **kwargs)
				ClassDecorator.ClassWrapper.__init__(self, LockableWrapper, *args, **kwargs)

			def __construct__(self, locks: typing.Iterable[str] = None):
				self.__locks__ = set()

				if locks is not None and locks:
					for key in locks:
						self.lock(key)

			def __locked_error__(self, key: str, method: typing.Callable):
				"""
				Throws an error when a locked method is called
				:param key:
				:param method:
				:return:
				"""
				try:
					# noinspection PyUnresolvedReferences
					super().__locked_error__(key=str, method=method)
				except AttributeError:
					raise LockedError(
						f"`{method.__qualname__}` method is locked with key '{key}'."
					) from None

			def __lock_error__(self, key: str, calling_cls):
				"""
				Throws an error when a class tries to lock this without permission
				:param key:
				:param calling_cls:
				:return:
				"""
				try:
					# noinspection PyUnresolvedReferences
					super().__lock_error__(key=key, cls=calling_cls)
				except AttributeError:
					raise LockError(
						("Functions " if calling_cls is None else f"`{calling_cls.__qualname__}` objects ") +
						f"are not allowed to lock `{type(self).__qualname__}` objects using "
						f"'{key}' key."
					) from None

			def __unlock_error__(self, key: str, calling_cls):
				"""
				Throws an error when a class tries to unlock this without permission
				:param key:
				:param calling_cls:
				:return:
				"""
				try:
					# noinspection PyUnresolvedReferences
					super().__unlock_error__(key=key, cls=calling_cls)
				except AttributeError:
					raise UnlockError(
						("Functions " if calling_cls is None else f"`{calling_cls.__qualname__}` objects ") +
						f"are not allowed to unlock `{type(self).__qualname__}` objects using "
						f"'{key}' key."
					) from None

			def __lock_key_error__(self, key: str):
				"""
				Throws an error when a class tries to unlock this with undefined key
				:param key:
				:return:
				"""
				try:
					# noinspection PyUnresolvedReferences
					super().__lock_key_error__(key=key, cls=calling_cls)
				except AttributeError:
					raise KeyError(
						f"Unrecognized key '{key}'."
					) from None

			# noinspection PyMethodParameters
			def lock(cls_self, key: str):
				if key in self._locks:
					if self._lock_permissions[key] is None:
						cls_self.__locks__.add(key)
					else:
						calling_cls = None
						found = False

						for _, _class in trace_execution(self._lock_permissions[key]):
							if _class is not None and not issubclass(_class, ClassDecorator.ClassWrapper):
								found = next(
									(True for c in self._lock_permissions[key] if issubclass(_class, c)),
									False
								)

								if calling_cls is None:
									calling_cls = _class

								if found:
									cls_self.__locks__.add(key)
									break

						if not found:
							cls_self.__lock_error__(key, calling_cls)
				else:
					cls_self.__lock_key_error__(key)

			# noinspection PyMethodParameters
			def unlock(cls_self, key: str):
				if key in self._locks:
					if self._unlock_permissions[key] is None:
						cls_self.__locks__.remove(key)
					else:
						calling_cls = None
						found = False

						for _, _class in trace_execution(self._unlock_permissions[key]):
							if _class is not None and not issubclass(_class, ClassDecorator.ClassWrapper):
								calling_cls = _class
								found = next(
									(True for c in self._unlock_permissions[key] if issubclass(_class, c)),
									False
								)

								if found:
									cls_self.__locks__.remove(key)
									break

						if not found:
							cls_self.__unlock_error__(key, calling_cls)
				else:
					cls_self.__lock_key_error__(key)

			# noinspection PyMethodParameters
			def locked(cls_self, key: str) -> bool:
				"""
				Returns true if the object is locked with `key`
				:param key:
				:return:
				"""
				if key in self._locks:
					return key in cls_self.__locks__
				else:
					cls_self.__lock_key_error__(key)

		return LockableWrapper


def lockablemethod(*args, keys: typing.Set = None):
	if args:
		method = args[0]
		return LockableMethod()(method)
	else:
		return LockableMethod(keys=keys)


class LockableMethod(MethodDecorator):
	def __init__(self, keys: typing.Set = None):
		self._keys = frozenset(keys)

	def __call__(self, method: typing.Callable, *_):
		super().__call__(method)

		def lockable_wrapper(method_self, *args, **kwargs):
			# noinspection PyProtectedMember
			try:
				keys = self._keys.intersection(method_self.__locks__)

				if keys:
					method_self.__locked_error__(next(iter(keys)), method)
			except AttributeError:
				pass

			return method(method_self, *args, **kwargs)

		return super().__call__(method, lockable_wrapper)


LockableClass._decorator_function = lockableclass
LockableClass._method_decorator = LockableMethod
LockableMethod._decorator_function = lockablemethod
LockableMethod._class_decorator = LockableClass
