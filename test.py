# ==============================================================================
# Unified Rich Style Setup for Hugging Face Transformers
# ==============================================================================
import sys
import logging
import warnings

# 1. 初始化全局 Console (这是核心，所有输出必须走同一个 Console)
from rich.logging import RichHandler

# ------------------------------------------------------------------------------
# Part A: 暴力 Patch Tqdm (让进度条变 Rich)
# ------------------------------------------------------------------------------
import tqdm
import tqdm.auto
import tqdm.std
from tqdm.rich import tqdm as rich_tqdm

class RichTqdmWrapper(rich_tqdm):
    def __init__(self, *args, **kwargs):
        kwargs.pop("ascii", None)              # 移除不兼容参数
        super().__init__(*args, **kwargs)

tqdm.auto.tqdm = RichTqdmWrapper
tqdm.std.tqdm = RichTqdmWrapper
tqdm.tqdm = RichTqdmWrapper
sys.modules['tqdm'].tqdm = RichTqdmWrapper

from transformers import pipeline

# ------------------------------------------------------------------------------
# Part B: 接管 Logging (让日志变 Rich)
# ------------------------------------------------------------------------------
def setup_rich_logging():
    # 1. 配置 Root Logger (捕获所有未被特殊处理的库日志)
    # 这一步保证了 huggingface_hub 等其他库也能用上 Rich
    logging.basicConfig(
        level="INFO",
        format="%(message)s",       # RichHandler 自带时间/等级，这里只留消息
        datefmt="[%X]",
        handlers=[RichHandler(
            markup=True,
            rich_tracebacks=True,
            show_path=False         # 保持界面清爽，不显示文件名
        )],
        force=True                  # 强制覆盖之前的配置
    )

    # 2. 导入 transformers (此时导入是安全的)
    import transformers

    # 3. 【关键】禁用 Transformers 自带的丑陋 Handler
    transformers.logging.disable_default_handler()

    # 4. 设置 Transformers 的日志等级
    # transformers.logging.set_verbosity_info()

    # 5. 手动把 RichHandler 挂载到 Transformers 的 Logger 上
    # 虽然有了 Root Logger 理论上会 propagate，但显式挂载更稳健
    # 这样可以防止 Transformers 内部某些逻辑重新添加 Handler
    hf_logger = logging.getLogger("transformers")
    hf_logger.handlers = [] # 清空残留
    hf_logger.addHandler(RichHandler(markup=True, show_path=False, log_time_format='[%X]'))
    hf_logger.propagate = False # 防止冒泡给 Root Logger 导致打印两次

    # 对 HuggingFace Hub 做同样的处理 (负责下载的部分)
    import huggingface_hub
    hub_logger = logging.getLogger("huggingface_hub")
    hub_logger.handlers = []
    hub_logger.addHandler(RichHandler(markup=True, log_time_format='[%X]'))
    hub_logger.propagate = False

# 执行配置
setup_rich_logging()

# ==============================================================================
# Part C: 业务代码测试
# ==============================================================================
logging.info(f"[bold cyan]Rich 环境初始化完成！[/bold cyan]")

# 这里的日志应该是 Rich 风格的 (左侧有蓝色的 INFO 图标)
# 下载进度条应该是 Rich 风格的 (红色/彩色平滑条)
pipe = pipeline("text-classification", model="distilbert-base-uncased-finetuned-sst-2-english")

# 打印一下模型架构，看看 Rich 渲染长文本的效果
import logging
log = logging.getLogger("transformers")
log.info("模型加载成功，架构如下：")
log.info(pipe.model) # 这一行如果打印出来会非常长且带有高亮
