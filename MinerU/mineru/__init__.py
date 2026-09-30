# === inspect.getsource 补丁（必须在所有其他导入之前执行）===
# 分布版中 .py 源文件已删除（只保留 .pyc），但 torch 等库内部
# 调用 inspect.getsource() / inspect.getsourcelines() 读取源码会导致 OSError。
# 此补丁在找不到源码时返回占位代码，避免功能报错，同时允许安全删除所有 .py 文件。
import inspect as _inspect

_original_getsource = _inspect.getsource
_original_getsourcelines = _inspect.getsourcelines


def _safe_getsource(object):
    try:
        return _original_getsource(object)
    except (OSError, TypeError):
        return "pass\n"


def _safe_getsourcelines(object):
    try:
        return _original_getsourcelines(object)
    except (OSError, TypeError):
        return (["pass\n"], 0)


_inspect.getsource = _safe_getsource
_inspect.getsourcelines = _safe_getsourcelines
