from copy import deepcopy
from inspect import isclass
from typing import Any

from pydantic import BaseModel


def diff[T: BaseModel](a: T, b: T) -> list[str]:
    changes: list[str] = []
    for key, field in a.__class__.model_fields.items():
        before = getattr(a, key)
        after = getattr(b, key)

        if (
            field.annotation
            and isclass(field.annotation)
            and issubclass(field.annotation, BaseModel)
        ):
            for change in diff(before, after):
                changes.append(f"{key}.{change}")
            continue

        if diff_item(before, after):
            changes.append(key)

    return changes


def diff_item(a: Any, b: Any) -> bool:
    a_ = deepcopy(a)
    b_ = deepcopy(b)

    if isinstance(a_, list):
        if not isinstance(b_, list):
            return True
        for i in a_:
            if i not in b_:
                return True
            b_.remove(i)
        if len(b_):
            return True
    elif isinstance(a_, dict):
        if not isinstance(b_, dict):
            return True
        for i in a_.keys():
            if i not in b_:
                return True
            if a_[i] != b_[i]:
                return True
            del b_[i]
        if len(b_):
            return True
    else:
        return a != b

    return False


def flatten_obj(obj: dict, sep: str = ".") -> dict[str, Any]:
    return _flatten_obj(obj, sep)


def _flatten_obj(obj: dict, sep: str = ".", current_path: str = "") -> dict[str, Any]:
    result = {}
    for key, value in obj.items():
        if current_path == "":
            path = key
        else:
            path = f"{current_path}{sep}{key}"

        if type(value) is dict:
            result |= _flatten_obj(value, sep, current_path=path)

        elif type(value) is list:
            for ind, item in enumerate(value):
                ind_path = f"{path}{sep}{ind}"
                if type(item) is dict:
                    result |= _flatten_obj(item, sep, current_path=f"{ind_path}{sep}{ind}")
                else:
                    result[ind_path] = item
        else:
            result[path] = value

    return result
