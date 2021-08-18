from .core import *
from collections import defaultdict


class Errors(Errors):
	NoLocksDefined = \
		"No locks have been defined for `{}`. " \
		"Use `lock_permissions` to define the locks."
	CallingLockedMethod = \
		"`{}` method is locked with key '{}'."
	LockingNotAllowed = \
		"`{}` objects are not allowed to lock `{}` objects using '{}' key."
	UnlockingNotAllowed = \
		"`{}` objects are not allowed to unlock `{}` objects using '{}' key."
	UnrecognizedKey = \
		"Unrecognized key '{}'."


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
			raise ValueError(Errors.NoLocksDefined.format(self._decorator_function))
		elif isinstance(lock_permissions, dict):
			lock_permissions = lock_permissions.items()

		lock_permissions = dict((k, set(v)) for k, v in lock_permissions)

		if unlock_permissions is None:
			unlock_permissions = lock_permissions
		else:
			if isinstance(unlock_permissions, dict):
				unlock_permissions = unlock_permissions.items()

			unlock_permissions = dict((k, set(v)) for k, v in unlock_permissions)

		self._locks = set(lock_permissions.keys() | unlock_permissions.keys())
		self._lock_permissions: typing.Dict = defaultdict(lambda: None, lock_permissions)
		self._unlock_permissions: typing.Dict = defaultdict(lambda: None, unlock_permissions)

	def __call__(self, cls, *_):
		"""
		Sanitize the class cls and returns a wrapper
		:param cls:
		:return:
		"""
		super().__call__(cls)

		# TODO: revisit this part
		for func in inspect.getmembers(cls, lambda x: inspect.isfunction(x)):
			try:
				self._locks.update(func.__locks__)
			except (AttributeError, TypeError):
				pass

		class LockableView(ClassDecorator.ObjectView):
			__locks__: set

			def __init__(self, obj):
				self.__locks__ = obj.__locks__
				ClassDecorator.ObjectView.__init__(self, obj)

			def lock(self, key: str):
				raise PermissionError(
					Errors.ViewMethodNotCallable.format(LockableView.lock.__name__, cls.__qualname__)
				)

			def unlock(self, key: str):
				raise PermissionError(
					Errors.ViewMethodNotCallable.format(LockableView.unlock.__name__, cls.__qualname__)
				)

		class LockableWrapper(cls, ClassDecorator.ClassWrapper):
			def __init__(self, *args, **kwargs):
				# This will call LockableWrapper.__construct__ and then cls.__init__
				self.__view = None
				ClassDecorator.ClassWrapper.__init__(self, LockableWrapper, cls, *args, **kwargs)

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
					raise LockedError(Errors.CallingLockedMethod.format(method.__qualname__, key)) from None

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
					raise LockError(Errors.LockingNotAllowed.format(
						None if calling_cls is None else calling_cls.__qualname__, type(self).__qualname__, key
					)) from None

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
					raise UnlockError(Errors.UnlockingNotAllowed.format(
						None if calling_cls is None else calling_cls.__qualname__, type(self).__qualname__, key
					)) from None

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
					raise KeyError(Errors.UnrecognizedKey.format(key)) from None

			# noinspection PyMethodParameters
			def lock(myself, key: str) -> None:
				"""
				Tries to lock the object with `key`;
				If the locker is not permitted to use the key, raises a `LockError`.
				:param key: The key to lock the object
				:return: None
				"""
				if key in self._locks:
					if self._lock_permissions[key] is None:
						myself.__locks__.add(key)
					else:
						calling_cls = None
						found = False

						for _, _class in trace_execution(self._lock_permissions[key]):
							if _class is not None:
								found = next(
									(True for c in self._lock_permissions[key] if issubclass(_class, c)),
									False
								)

								if calling_cls is None:
									calling_cls = _class

								if found:
									myself.__locks__.add(key)
									break

						if not found:
							myself.__lock_error__(key, calling_cls)
				else:
					myself.__lock_key_error__(key)

			# noinspection PyMethodParameters
			def unlock(myself, key: str) -> None:
				if key in self._locks:
					if self._unlock_permissions[key] is None:
						myself.__locks__.remove(key)
					else:
						calling_cls = None
						found = False

						for _, _class in trace_execution(self._unlock_permissions[key]):
							if _class is not None:
								calling_cls = _class
								found = next(
									(True for c in self._unlock_permissions[key] if issubclass(_class, c)),
									False
								)

								if found:
									myself.__locks__.remove(key)
									break

						if not found:
							myself.__unlock_error__(key, calling_cls)
				else:
					myself.__lock_key_error__(key)

			# noinspection PyMethodParameters
			def locked(myself, key: str) -> bool:
				"""
				Returns true if the object is locked with `key`
				:param key:
				:return:
				"""
				if key in self._locks:
					return key in myself.__locks__
				else:
					myself.__lock_key_error__(key)

			def view(self):
				if self.__view is None:
					self.__view = LockableView(self)

				return self.__view

		for lock in self._lock_permissions:
			self._lock_permissions[lock].add(cls)

		for lock in self._unlock_permissions:
			self._unlock_permissions[lock].add(cls)

		super().__call__(cls, LockableWrapper)
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

		def lockable_wrapper(myself, *args, **kwargs):
			if isinstance(myself, ClassDecorator.ObjectView):
				# noinspection PyProtectedMember
				locks = myself.__locks__ | myself._ObjectView__obj.__locks__
			else:
				locks = myself.__locks__

			keys = self._keys.intersection(locks)

			if keys:
				myself.__locked_error__(next(iter(keys)), method)
			else:
				return method(myself, *args, **kwargs)

		return super().__call__(method, lockable_wrapper)


LockableClass._decorator_function = lockableclass
LockableClass._method_decorator = LockableMethod
LockableMethod._decorator_function = lockablemethod
LockableMethod._class_decorator = LockableClass
lockable = ModuleElements(mth=lockablemethod, cls=lockableclass)
