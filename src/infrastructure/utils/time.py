"""
企业级时间管理工具模块

提供全面的代码执行时间测试和性能监控功能，
严格遵循Google/Microsoft/Alibaba/Tencent编码规范。
"""

import asyncio
import functools
import inspect
import logging
import os
import platform
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
    Protocol,
    TextIO,
    Type,
    TypeVar,
    Union,
    overload,
)


# 类型定义
T = TypeVar('T')
R = TypeVar('R')
Decorator = Callable[[T], T]
TimerResult = Dict[str, Union[str, float, int]]


logger = logging.getLogger(__name__)


class TimerData:
    """计时器数据存储类"""

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
        """平均时间"""
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
    """性能分析报告类"""

    def __init__(self) -> None:
        self.timers: Dict[str, TimerData] = defaultdict(TimerData)
        self.start_times: Dict[str, float] = {}
        self.cpu_times: Dict[str, float] = {}
        self.memory_peaks: Dict[str, int] = {}


@dataclass
class TimerContext:
    """计时器上下文信息"""

    name: str
    start_time: float
    cpu_start: float
    memory_start: int
    level: int
    profile: PerformanceProfile
    silent: bool = False
    separator: str = '│   '


class TimerOutput(Protocol):
    """输出协议"""
    def output(self, message: str) -> None:
        ...


class ConsoleOutput:
    """控制台输出实现"""

    def __init__(self, file: TextIO = sys.stdout) -> None:
        self.file = file

    def output(self, message: str) -> None:
        print(message, file=self.file)


class FileOutput:
    """文件输出实现"""

    def __init__(self, filepath: Union[str, Path]) -> None:
        self.filepath = Path(filepath)
        self.filepath.parent.mkdir(parents=True, exist_ok=True)

    def output(self, message: str) -> None:
        with open(self.filepath, 'a', encoding='utf-8') as f:
            f.write(message + '\n')


@dataclass
class TimerConfig:
    """计时器配置"""

    enabled: bool = True
    log_level: int = logging.INFO
    precision: int = 6
    show_memory: bool = False
    show_cpu: bool = False
    recursive: bool = True
    output_handlers: List[TimerOutput] = field(default_factory=lambda: [ConsoleOutput()])


class GlobalTimerManager:
    """全局计时器管理器"""

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
    企业级计时器类

    提供代码执行时间测试、性能监控和统计分析功能，
    支持上下文管理器、装饰器和直接调用等多种使用方式。

    使用示例：
        # 上下文管理器方式
        with Timer('数据处理'):
            process_data()

        # 装饰器方式
        @Timer()
        def my_function():
            pass

        # 代码块计时
        timer = Timer('task')
        timer.start()
        # 执行代码
        timer.stop()
        print(timer.duration)
    """

    _manager = GlobalTimerManager()

    def __init__(
        self,
        name: Optional[str] = None,
        silent: bool = False,
        show_memory: Optional[bool] = None,
        show_cpu: Optional[bool] = None,
    ) -> None:
        self.name = name
        self.silent = silent
        self.show_memory = show_memory
        self.show_cpu = show_cpu
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.cpu_start: Optional[float] = None
        self.cpu_end: Optional[float] = None
        self.memory_start: int = 0
        self.memory_end: int = 0
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
        if self.end_time is None:
            return time.perf_counter() - self.start_time
        return self.end_time - self.start_time

    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self.start_time is not None and self.end_time is None

    def _get_current_memory(self) -> int:
        """获取当前内存使用量（Bytes）"""
        current_system = platform.system()
        if current_system == 'Linux' or current_system == 'Darwin':
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        else:
            return 0

    def _get_current_cpu(self) -> float:
        """获取当前CPU时间（秒）"""
        current_usage = resource.getrusage(resource.RUSAGE_SELF)
        return current_usage.ru_utime + current_usage.ru_stime

    def start(self) -> None:
        """开始计时"""
        if not self.config.enabled:
            return

        self.name = self.name or f"timer_{id(self)}"
        self.start_time = time.perf_counter()
        self.cpu_start = self._get_current_cpu()
        self.memory_start = self._get_current_memory()

        self.context = TimerContext(
            name=self.name,
            start_time=self.start_time,
            cpu_start=self.cpu_start or 0.0,
            memory_start=self.memory_start,
            level=self._manager.level,
            profile=self.profile,
            silent=self.silent,
        )

        if self.config.recursive:
            self._manager.level += 1

        if not self.silent:
            self._log_start()

    def stop(self) -> float:
        """
        停止计时并返回持续时间

        Returns:
            float: 持续时间（秒）
        """
        if not self.config.enabled or self.start_time is None:
            return 0.0

        self.end_time = time.perf_counter()
        self.cpu_end = self._get_current_cpu()
        self.memory_end = self._get_current_memory()

        duration = self.duration

        if self.context:
            self.context.profile.timers[self.name].update(duration)

        if not self.silent:
            self._log_end(duration)

        if self.config.recursive and self._manager.level > 0:
            self._manager.level -= 1

        return duration

    def _log_start(self) -> None:
        """记录开始日志"""
        if not self.config.output_handlers:
            return

        indent = self.context.separator * self.context.level if self.context else ''
        message = f"{indent}▶ {self.name}..."

        for handler in self.config.output_handlers:
            handler.output(message)

    def _log_end(self, duration: float) -> None:
        """记录结束日志"""
        if not self.config.output_handlers:
            return

        indent = self.context.separator * self.context.level if self.context else ''
        parts = [f"{indent}◆ {self.name}", f"{duration:.{self.config.precision}f}s"]

        show_memory = self.show_memory if self.show_memory is not None else self.config.show_memory
        if show_memory:
            memory_diff = (self.memory_end - self.memory_start) / 1024 / 1024
            parts.append(f"RAM: {memory_diff:+.1f}MB")

        show_cpu = self.show_cpu if self.show_cpu is not None else self.config.show_cpu
        if show_cpu and self.cpu_start is not None and self.cpu_end is not None:
            cpu_time = self.cpu_end - self.cpu_start
            parts.append(f"CPU: {cpu_time:.{self.config.precision}f}s")

        message = ' | '.join(parts)

        for handler in self.config.output_handlers:
            handler.output(message)

    def __enter__(self) -> 'Timer':
        """上下文管理器入口"""
        self.start()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Any,
    ) -> None:
        """上下文管理器出口"""
        self.stop()

    def __call__(self, func: T) -> T:
        """
        装饰器调用

        Args:
            func: 要装饰的函数

        Returns:
            包装后的函数
        """
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            name = self.name or func.__name__
            with Timer(name, silent=self.silent, show_memory=self.show_memory, show_cpu=self.show_cpu):
                return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            name = self.name or func.__name__
            with Timer(name, silent=self.silent, show_memory=self.show_memory, show_cpu=self.show_cpu):
                return await func(*args, **kwargs)

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    def reset(self) -> None:
        """重置计时器"""
        self.start_time = None
        self.end_time = None
        self.cpu_start = None
        self.cpu_end = None
        self.memory_start = 0
        self.memory_end = 0


class SuiteTimer:
    """
    测试套件计时器

    用于测量整个测试套件的执行时间，并生成性能报告
    """

    def __init__(self, name: str = 'Test Suite') -> None:
        self.name = name
        self.total_timer = Timer(name, silent=True)
        self.test_timers: Dict[str, Timer] = {}
        self.setup_timers: Dict[str, Timer] = {}
        self.teardown_timers: Dict[str, Timer] = {}
        self.report_file: Optional[Path] = None

    def start(self) -> None:
        """开始测试套件计时"""
        self.total_timer.start()
        print(f"\n{'='*80}")
        print(f"🚀 {self.name} 开始执行")
        print(f"{'='*80}\n")

    def stop(self) -> float:
        """停止测试套件计时"""
        duration = self.total_timer.stop()
        print(f"\n{'='*80}")
        print(f"✅ {self.name} 执行完成")
        print(f"总执行时间: {duration:.6f}秒")
        print(f"{'='*80}\n")
        self.print_summary()
        return duration

    def test_timer(self, name: str) -> Timer:
        """获取测试方法计时器"""
        if name not in self.test_timers:
            self.test_timers[name] = Timer(f'🧪 {name}', show_cpu=True, show_memory=True)
        return self.test_timers[name]

    def setup_timer(self, name: str) -> Timer:
        """获取setUp方法计时器"""
        if name not in self.setup_timers:
            self.setup_timers[name] = Timer(f'⚙️ setUp: {name}', silent=True)
        return self.setup_timers[name]

    def teardown_timer(self, name: str) -> Timer:
        """获取tearDown方法计时器"""
        if name not in self.teardown_timers:
            self.teardown_timers[name] = Timer(f'🧹 tearDown: {name}', silent=True)
        return self.teardown_timers[name]

    def print_summary(self) -> None:
        """打印执行摘要"""
        print("\n📊 执行时间汇总:")
        print("="*50)

        suite_profile = GlobalTimerManager().profile

        if self.test_timers:
            print("\n单元测试执行时间:")
            sorted_tests = sorted(
                suite_profile.timers.items(),
                key=lambda x: x[1].total,
                reverse=True
            )
            for name, data in sorted_tests:
                if name.startswith('🧪'):
                    print(f"{name}: {data.total:.{GlobalTimerManager().config.precision}f}s (avg: {data.avg:.{GlobalTimerManager().config.precision}f}s, count: {data.count})")

        if self.setup_timers:
            print("\nsetup 方法执行时间:")
            for name, timer in self.setup_timers.items():
                if timer.duration > 0:
                    print(f"{timer.name}: {timer.duration:.6f}s")

        if self.teardown_timers:
            print("\nteardown 方法执行时间:")
            for name, timer in self.teardown_timers.items():
                if timer.duration > 0:
                    print(f"{timer.name}: {timer.duration:.6f}s")

    def __enter__(self) -> 'SuiteTimer':
        """上下文管理器入口"""
        self.start()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Any,
    ) -> None:
        """上下文管理器出口"""
        self.stop()


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
    """获取计时器统计信息"""
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


def save_timer_report(filepath: Union[str, Path]) -> None:
    """保存计时器报告到文件"""
    manager = GlobalTimerManager()
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("# 性能测试报告\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write("## 计时器统计\n")
        f.write("| 名称 | 次数 | 总时间(秒) | 平均时间(秒) | 最短时间(秒) | 最长时间(秒) |\n")
        f.write("| --- | --- | --- | --- | --- | --- |\n")

        for name, data in sorted(manager.profile.timers.items(), key=lambda x: x[1].total, reverse=True):
            stats = data.to_dict()
            f.write(f"| {name} | {stats['count']} | {stats['total']:.6f} | {stats['avg']:.6f} | {stats['min']:.6f} | {stats['max']:.6f} |\n")


# 便捷装饰器

def timer(
    name: Optional[str] = None,
    show_memory: bool = False,
    show_cpu: bool = False,
    silent: bool = False,
) -> Decorator:
    """便捷计时装饰器"""
    def decorator(func: T) -> T:
        return Timer(name, show_memory=show_memory, show_cpu=show_cpu, silent=silent)(func)
    return decorator


# 模块级函数

@contextmanager
def measure_time(
    name: str,
    show_memory: bool = False,
    show_cpu: bool = False,
    silent: bool = False,
) -> Generator[Timer, None, None]:
    """
    上下文管理器便捷函数

    Args:
        name: 计时器名称
        show_memory: 是否显示内存信息
        show_cpu: 是否显示CPU信息
        silent: 是否静默模式

    Yields:
        Timer: 计时器实例
    """
    with Timer(name, show_memory=show_memory, show_cpu=show_cpu, silent=silent) as t:
        yield t


async def measure_time_async(
    name: str,
    show_memory: bool = False,
    show_cpu: bool = False,
    silent: bool = False,
) -> Timer:
    """支持异步的上下文管理器便捷函数"""
    return Timer(name, show_memory=show_memory, show_cpu=show_cpu, silent=silent)


__all__ = [
    'Timer',
    'SuiteTimer',
    'TimerConfig',
    'TimerData',
    'PerformanceProfile',
    'timer',
    'measure_time',
    'measure_time_async',
    'get_global_timer',
    'reset_global_timer',
    'configure_timer',
    'get_timer_stats',
    'clear_timer_stats',
    'save_timer_report',
]
