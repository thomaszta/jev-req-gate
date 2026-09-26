"""jev_req_gate — 用 Jev (TypeSafe System One) 给 LLM 生成的需求做质量门禁。

基于 MECE 5 面（表述/内容/现实/关系/治理）× 22 个原子问题，
把需求+上下文打包成 state，让 Jev 并行判断，代码按阈值路由：放行 / 转人工 / 打回。
"""

__version__ = "0.6.2"

from .core import decide, normalize_sdk_response, run_gate  # noqa: F401
from .profiles import (  # noqa: F401
    CORE_SCORES,
    DEFAULT_PROFILE,
    DEFAULT_THRESHOLDS,
    load_profile,
    load_thresholds,
)
from .store import Store, request_hash  # noqa: F401
from .labels import evaluate, export, load  # noqa: F401

__all__ = [
    "__version__",
    "DEFAULT_PROFILE",
    "DEFAULT_THRESHOLDS",
    "CORE_SCORES",
    "load_profile",
    "load_thresholds",
    "decide",
    "normalize_sdk_response",
    "run_gate",
    "Store",
    "request_hash",
    "evaluate",
    "export",
    "load",
]
