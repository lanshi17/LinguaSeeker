"""企业级计时器与性能监控工具。

提供代码执行时间测试、性能分析功能，适配ACMG管线。
支持上下文管理器、装饰器、嵌套计时等多种使用方式。
"""

import asyncio
import functools
import inspect
from loguru import logger as loguru_logger
import resource
import sys
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    TextIO,
    Type,
    TypeVar,
    Union,
)


T = TypeVar('T')
Decorator = Callable[[T], T]
TimerResult = Dict[str, Union[str, float, int]]

logger = loguru_logger


class TimerData:
    """计时器统计数据存储"""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """重置所有统计数据"""
        self.count: int = 0
        self.total: float = 0.0
        self.min: float = float('inf')
        self.max: float = 0.0

    def update(self, duration: float) -> None:
        """更新统计数据"""
        self.count += 1
        self.total += duration
        if duration < self.min:
            self.min = duration
        if duration > self.max:
            self.max = duration

    @property
    def avg(self) -> float:
        """平均时间（秒）"""
        return self.total / self.count if self.count > 0 else 0.0

    def to_dict(self) -> TimerResult:
        """转换为字典格式"""
        return {
            'count': self.count,
            'total': self.total,
            'avg': self.avg,
            'min': self.min,
            'max': self.max,
        }


class PerformanceProfile:
    """性能分析档案"""

    def __init__(self) -> None:
        self.timers: Dict[str, TimerData] = defaultdict(TimerData)


@dataclass
class TimerContext:
    """计时器执行上下文"""

    name: str
    start_time: float
    level: int
    silent: bool = False
    indent: str = "  "


class ConsoleOutput:
    """控制台输出适配"""

    def __init__(self, file: TextIO = sys.stdout) -> None:
        self.file = file

    def output(self, message: str) -> None:
        """输出消息到控制台"""
        logger.info(message)


class FileOutput:
    """文件输出适配"""

    def __init__(self, filepath: Union[str, Path]) -> None:
        self.filepath = Path(filepath)
        self.filepath.parent.mkdir(parents=True, exist_ok=True)

    def output(self, message: str) -> None:
        """输出消息到文件"""
        with open(self.filepath, 'a', encoding='utf-8') as f:
            f.write(message + '\n')


@dataclass
class TimerConfig:
    """全局计时器配置"""

    enabled: bool = True
    precision: int = 4
    show_memory: bool = False
    recursive: bool = True
    output_handlers: List[Union[ConsoleOutput, FileOutput]] = field(
        default_factory=lambda: [ConsoleOutput()]
    )


class GlobalTimerManager:
    """单例全局计时器管理器"""

    _instance: Optional['GlobalTimerManager'] = None
    _lock = threading.Lock()

    def __new__(cls) -> 'GlobalTimerManager':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, 'initialized'):
            self.config = TimerConfig()
            self.profile = PerformanceProfile()
            self.level = 0
            self.initialized = True

    @classmethod
    def reset(cls) -> None:
        """重置全局管理器"""
        cls._instance = None


class Timer:
    """
    高性能计时器类。

    用于代码执行时间测试、性能监控与分析。
    支持上下文管理器、装饰器、嵌套计时。

    示例：
        # 上下文方式
        with Timer('任务名'):
            do_something()

        # 装饰器方式
        @Timer()
        def my_func():
            pass

        # 手动方式
        timer = Timer('计时')
        timer.start()
        do_something()
        duration = timer.stop()
    """

    _manager = GlobalTimerManager()

    def __init__(
        self,
        name: Optional[str] = None,
        silent: bool = False,
        show_memory: bool = False,
    ) -> None:
        self.name = name or f"timer_{id(self)}"
        self.silent = silent
        self.show_memory = show_memory or self.config.show_memory
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.context: Optional[TimerContext] = None

    @property
    def config(self) -> TimerConfig:
        """获取配置"""
        return self._manager.config

    @property
    def profile(self) -> PerformanceProfile:
        """获取性能档案"""
        return self._manager.profile

    @property
    def duration(self) -> float:
        """获取持续时间（秒）"""
        if self.start_time is None:
            return 0.0
        end = self.end_time or time.perf_counter()
        return end - self.start_time

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self.start_time is not None and self.end_time is None

    @staticmethod
    def _get_rss_mb() -> float:
        """获取当前内存使用量（MB）"""
        try:
            usage = resource.getrusage(resource.RUSAGE_SELF)
            return usage.ru_maxrss / 1024.0  # Convert to MB
        except Exception:
            return 0.0

    def start(self) -> None:
        """开始计时"""
        if not self.config.enabled:
            return

        self.start_time = time.perf_counter()
        self.context = TimerContext(
            name=self.name,
            start_time=self.start_time,
            level=self._manager.level,
            silent=self.silent,
            indent="  " * self._manager.level,
        )

        if self.config.recursive:
            self._manager.level += 1

        if not self.silent:
            self._log_start()

    def stop(self) -> float:
        """停止计时并返回持续时间（秒）"""
        if not self.config.enabled or self.start_time is None:
            return 0.0

        self.end_time = time.perf_counter()
        duration = self.duration

        # 更新统计
        self.profile.timers[self.name].update(duration)

        if not self.silent:
            self._log_end(duration)

        if self.config.recursive and self._manager.level > 0:
            self._manager.level -= 1

        return duration

    def _log_start(self) -> None:
        """记录开始日志"""
        if not self.config.output_handlers or not self.context:
            return

        indent = self.context.indent
        message = f"{indent}⏱ {self.name}..."

        for handler in self.config.output_handlers:
            handler.output(message)

    def _log_end(self, duration: float) -> None:
        """记录结束日志"""
        if not self.config.output_handlers or not self.context:
            return

        indent = self.context.indent
        parts = [f"{indent}✓ {self.name}", f"{duration:.{self.config.precision}f}s"]

        if self.show_memory:
            mem = self._get_rss_mb()
            parts.append(f"memory: {mem:.1f}MB")

        message = " | ".join(parts)
        for handler in self.config.output_handlers:
            handler.output(message)

    def __enter__(self) -> 'Timer':
        """上下文管理器入口"""
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """上下文管理器出口"""
        self.stop()

    def __call__(self, func: T) -> T:
        """装饰器支持"""

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with Timer(self.name or func.__name__, self.silent, self.show_memory):
                return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            with Timer(self.name or func.__name__, self.silent, self.show_memory):
                return await func(*args, **kwargs)

        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    def reset(self) -> None:
        """重置计时器"""
        self.start_time = None
        self.end_time = None


# 全局工具函数

def get_global_timer() -> GlobalTimerManager:
    """获取全局计时器管理器"""
    return GlobalTimerManager()


def reset_global_timer() -> None:
    """重置全局计时器管理器"""
    GlobalTimerManager.reset()


def configure_timer(config: TimerConfig) -> None:
    """配置全局计时器"""
    manager = GlobalTimerManager()
    manager.config = config


def get_timer_stats(name: str) -> Optional[TimerResult]:
    """获取指定计时器的统计信息"""
    manager = GlobalTimerManager()
    if name in manager.profile.timers:
        return manager.profile.timers[name].to_dict()
    return None


def clear_timer_stats(name: Optional[str] = None) -> None:
    """清除计时器统计信息"""
    manager = GlobalTimerManager()
    if name:
        if name in manager.profile.timers:
            manager.profile.timers[name].reset()
    else:
        manager.profile.timers.clear()


def print_timer_stats() -> None:
    """打印所有计时器统计信息"""
    manager = GlobalTimerManager()
    if not manager.profile.timers:
        print("No timers recorded")
        return

    print("\n" + "=" * 70)
    print("计时器统计汇总".center(70))
    print("=" * 70)
    print(f"{'名称':<30} {'次数':>6} {'总时间':>12} {'平均':>12} {'最小':>12} {'最大':>12}")
    print("-" * 70)

    for name in sorted(manager.profile.timers.keys()):
        data = manager.profile.timers[name]
        stats = data.to_dict()
        print(
            f"{name:<30} {stats['count']:>6d} "
            f"{stats['total']:>12.4f}s {stats['avg']:>12.4f}s "
            f"{stats['min']:>12.4f}s {stats['max']:>12.4f}s"
        )

    print("=" * 70 + "\n")


def timer(name: Optional[str] = None, show_memory: bool = False) -> Decorator:
    """便捷装饰器"""

    def decorator(func: T) -> T:
        return Timer(name, show_memory=show_memory)(func)

    return decorator


@contextmanager
def measure_time(
    name: str,
    show_memory: bool = False,
    silent: bool = False,
) -> Generator[Timer, None, None]:
    """上下文管理器便捷函数"""
    with Timer(name, silent=silent, show_memory=show_memory) as t:
        yield t


__all__ = [
    'Timer',
    'TimerConfig',
    'TimerData',
    'PerformanceProfile',
    'timer',
    'measure_time',
    'get_global_timer',
    'reset_global_timer',
    'configure_timer',
    'get_timer_stats',
    'clear_timer_stats',
    'print_timer_stats',
]
