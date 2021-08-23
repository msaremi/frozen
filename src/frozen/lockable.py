from __future__ import annotations
from .core import *


class Errors(Errors):
	NoLocksDefined = \
		"No keys have been defined for `{}`. " \
		"Use `lock_permissions` parameter to define the locks."
	NoKeysDefined = \
		"No keys have been defined for `{}`. " \
		"Use `keys` parameter to define the keys."
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
		lock_permissions: Dict[str, Optional[Set]] = None,
		unlock_permissions: Dict[str, Optional[Set]] = None
):
	if args:
		cls = args[0]
		return LockableClassDecorator()(cls)
	else:
		return LockableClassDecorator(lock_permissions=lock_permissions, unlock_permissions=unlock_permissions)


class Lockable(ClassWrapperBase):
	def __init__(self, args, kwargs, wrapper_cls: Type[Lockable], decorator: LockableClassDecorator):
		self.__decorator = decorator
		self.__view = None
		ClassWrapperBase.__init__(self, args=args, kwargs=kwargs, wrapper_cls=wrapper_cls)

	def __load__(self, locks: Iterable[str] = None):
		self.__locks__ = set()

		if locks is not None and locks:
			for key in locks:
				self.lock(key)

	def __locked_error__(self, key: str, method: Callable) -> None:
		"""
		Throws an error when a locked method is called
		:param key:
		:param method:
		:return:
		"""
		raise LockedError(Errors.CallingLockedMethod.format(method.__qualname__, key))

	def __lock_error__(self, key: str, calling_cls) -> None:
		"""
		Throws an error when a class tries to lock this without permission
		:param key:
		:param calling_cls:
		:return:
		"""
		raise LockError(Errors.LockingNotAllowed.format(
			None if calling_cls is None else calling_cls.__qualname__, type(self).__qualname__, key
		))

	def __unlock_error__(self, key: str, calling_cls) -> None:
		"""
		Throws an error when a class tries to unlock this without permission.
		:param key:
		:param calling_cls:
		:return: None
		"""
		raise UnlockError(Errors.UnlockingNotAllowed.format(
			None if calling_cls is None else calling_cls.__qualname__, type(self).__qualname__, key
		))

	def __lock_key_error__(self, key: str):
		"""
		Throws an error when a class tries to unlock this with undefined key
		:param key:
		:return:
		"""
		raise KeyError(Errors.UnrecognizedKey.format(key))

	# noinspection PyMethodParameters
	@locked_in_view
	def lock(self, key: str) -> None:
		"""
		Tries to lock the object with `key`;
		If the locker is not permitted to use the key, raises a `LockError`.
		:param key: The key to lock the object
		:return: None
		"""
		if key in self.__decorator.locks:
			if self.__decorator.lock_permissions[key] is None:
				self.__locks__.add(key)
			else:
				calling_cls = None
				found = False

				for _, _class in trace_execution(self.__decorator.lock_permissions[key]):
					if _class is not None:
						found = next(
							(True for c in self.__decorator.lock_permissions[key] if issubclass(_class, c)),
							False
						)

						if calling_cls is None:
							calling_cls = _class

						if found:
							self.__locks__.add(key)
							break

				if not found:
					self.__lock_error__(key, calling_cls)
		else:
			self.__lock_key_error__(key)

	# noinspection PyMethodParameters
	@locked_in_view
	def unlock(self, key: str) -> None:
		if key in self.__decorator.locks:
			if self.__decorator.unlock_permissions[key] is None:
				self.__locks__.remove(key)
			else:
				calling_cls = None
				found = False

				for _, cls in trace_execution(self.__decorator.unlock_permissions[key]):
					if cls is not None:
						calling_cls = cls
						found = next(
							(True for c in self.__decorator.unlock_permissions[key] if issubclass(cls, c)),
							False
						)

						if found:
							self.__locks__.remove(key)
							break

				if not found:
					self.__unlock_error__(key, calling_cls)
		else:
			self.__lock_key_error__(key)

	# noinspection PyMethodParameters
	def locked(self, key: str) -> bool:
		"""
		Returns true if the object is locked with `key`
		:param key:
		:return:
		"""
		if key in self.__decorator.locks:
			return key in self.__locks__
		else:
			self.__lock_key_error__(key)

	def view(self):
		return self if isinstance(self, View) else LockableView(self)


class LockableView(View):
	__locks__: set

	def __init__(self, obj: Lockable):
		View.__init__(self, obj)
		self.__locks__ = obj.__locks__


class LockableClassDecorator(ClassDecorator[b'LockableClassDecorator', b'LockableMethodDecorator']):
	def __init__(
			self,
			lock_permissions: Dict[str, Optional[Set]] = None,
			unlock_permissions: Dict[str, Optional[Set]] = None
	):
		"""

		:param lock_permissions: Example: {"key1": {Class1, Class2}, "key2: {Class2, Class3}}
		:param unlock_permissions: Same as `lock_permissions`
		"""
		if lock_permissions is None:
			raise ValueError(Errors.NoLocksDefined.format(self._decorator_function))
		elif isinstance(lock_permissions, dict):
			lock_permissions = lock_permissions.items()

		lock_permissions = dict(
			(k, {v} if isinstance(v, type) else set(v))
			for k, v in lock_permissions if v is not None
		)

		if unlock_permissions is None:
			unlock_permissions = lock_permissions
		else:
			if isinstance(unlock_permissions, dict):
				unlock_permissions = unlock_permissions.items()

			unlock_permissions = dict(
				(k, {v} if isinstance(v, type) else set(v))
				for k, v in unlock_permissions if v is not None
			)

		self._locks = set(lock_permissions.keys() | unlock_permissions.keys())
		self._lock_permissions: Dict = defaultdict(lambda: None, lock_permissions)
		self._unlock_permissions: Dict = defaultdict(lambda: None, unlock_permissions)

	@property
	def locks(self):
		return self._locks

	@property
	def lock_permissions(self):
		return self._lock_permissions

	@property
	def unlock_permissions(self):
		return self._unlock_permissions

	def __call__(self, cls, *_):
		super().__call__(cls)

		for spec in self._method_specs:
			self._locks.update(spec.method_decorator.keys)

		for lock in self._lock_permissions:
			self._lock_permissions[lock].add(cls)

		for lock in self._unlock_permissions:
			self._unlock_permissions[lock].add(cls)

		class LockableWrapper(cls, Lockable):
			def __init__(*args, **kwargs):
				# The reason why I do not use `self`:
				# We do not know the name of the `self` argument in `cls.__init__`;
				# All we know is it will be the first argument, i.e. args[0].
				# To avoid name conflict between `self` and `**kwargs`, I do not use `self`.
				Lockable.__init__(
					self=args[0],
					args=args[1:],
					kwargs=kwargs,
					wrapper_cls=LockableWrapper,
					decorator=self,
				)

		return super().__call__(cls, LockableWrapper)


def lockablemethod(*args, keys: Set = None):
	if args:
		method = args[0]
		return LockableMethodDecorator()(method)
	else:
		return LockableMethodDecorator(keys=keys)


class LockableMethodDecorator(MethodDecorator[b'LockableClassDecorator', b'LockableMethodDecorator']):
	def __init__(self, keys: Set = None):
		if keys is not None:
			self._keys = frozenset(keys)
		else:
			raise ValueError(Errors.NoKeysDefined.format(self._decorator_function.__name__))

	def __call__(self, method: Callable, *_):
		super().__call__(method)

		def lockable_wrapper(myself, *args, **kwargs):
			if isinstance(myself, View):
				# noinspection PyProtectedMember
				locks = myself.__locks__ | myself._View__obj.__locks__
			else:
				locks = myself.__locks__

			keys = self._keys.intersection(locks)

			if keys:
				myself.__locked_error__(next(iter(keys)), method)
			else:
				return method(myself, *args, **kwargs)

		return super().__call__(method, lockable_wrapper)

	@property
	def keys(self):
		return self._keys


LockableClassDecorator._decorator_function = lockableclass
LockableClassDecorator._method_decorator = LockableMethodDecorator
LockableMethodDecorator._decorator_function = lockablemethod
LockableMethodDecorator._class_decorator = LockableClassDecorator
lockable = ModuleElements(mth=lockablemethod, cls=lockableclass)
