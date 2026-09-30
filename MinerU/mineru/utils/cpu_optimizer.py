"""CPU 推理性能自动优化模块。

在进程启动早期调用 apply_cpu_optimizations()，根据当前机器的 CPU 核心数
自动设置合理的线程数环境变量，加速纯 CPU 推理场景（pipeline 后端）。

设计原则：
1. 仅在用户未手动设置环境变量时才设置，尊重用户覆盖。
2. 对 GPU 机器无害：CUDA/MPS 可用时跳过 PyTorch 线程设置。
3. 适用于任意 CPU 核心数，自动适配低端到高端机器。
4. 线程数取核心数的合理比例，避免过度并行导致内存压力和上下文切换开销。
"""
import os
import logging

# 注意：inspect.getsource() 补丁已移至 mineru/__init__.py（包入口），
# 确保在所有子模块导入之前生效，支持安全删除 .py 源文件。

_logger = logging.getLogger("mineru.cpu_optimizer")

# 标记是否已执行过，避免重复设置
_applied = False


def _get_cpu_count():
    """获取物理 CPU 核心数（首选物理核心，回退到逻辑核心数）。"""
    # 优先使用物理核心数（更准确反映推理能力）
    # os.cpu_count() 返回逻辑核心数（含超线程）
    logical = os.cpu_count() or 1

    # 尝试获取物理核心数（更保守，避免超线程导致的性能损失）
    try:
        import multiprocessing
        physical = multiprocessing.cpu_count()
        # 使用逻辑核心数，因为推理任务中 PyTorch/ONNX 能有效利用超线程
        # 但限制最大值避免过多线程导致内存压力
        return logical
    except Exception:
        return logical


def _is_gpu_available():
    """检测是否有可用的 GPU（CUDA/MPS）。

    GPU 可用时跳过线程优化，因为 GPU 推理不依赖 CPU 线程数。
    """
    try:
        import torch
        if torch.cuda.is_available():
            return True
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return True
    except Exception:
        pass
    return False


def apply_cpu_optimizations(force=False):
    """根据 CPU 核心数自动设置线程优化环境变量。

    参数:
        force: 是否强制重新设置（即使已经设置过）
    """
    global _applied
    if _applied and not force:
        return
    _applied = True

    cpu_count = _get_cpu_count()

    # 计算合理的线程数
    # - 1-4 核：使用全部核心
    # - 5-8 核：使用全部核心
    # - 9-16 核：使用 75% 核心（留出系统线程余量）
    # - 17+ 核：使用 70% 核心
    if cpu_count <= 8:
        torch_threads = cpu_count
        onnx_threads = cpu_count
        render_threads = min(6, cpu_count)
    elif cpu_count <= 16:
        torch_threads = max(4, int(cpu_count * 0.75))
        onnx_threads = max(4, int(cpu_count * 0.75))
        render_threads = 6
    else:
        torch_threads = max(8, int(cpu_count * 0.7))
        onnx_threads = max(8, int(cpu_count * 0.7))
        render_threads = 8

    # 限制最大值，避免内存压力
    torch_threads = min(torch_threads, 16)
    onnx_threads = min(onnx_threads, 16)
    render_threads = min(render_threads, 8)

    is_gpu = _is_gpu_available()

    settings = []

    # === PyTorch 线程优化（版面检测、OCR、公式识别）===
    # GPU 可用时跳过，避免影响 GPU 调度
    if not is_gpu:
        if os.getenv("OMP_NUM_THREADS") is None:
            os.environ["OMP_NUM_THREADS"] = str(torch_threads)
            settings.append(f"OMP_NUM_THREADS={torch_threads}")

        if os.getenv("MKL_NUM_THREADS") is None:
            os.environ["MKL_NUM_THREADS"] = str(torch_threads)
            settings.append(f"MKL_NUM_THREADS={torch_threads}")

        # torch.set_num_threads 在模型加载后才会生效，
        # 通过环境变量在更早期设置更可靠
        if os.getenv("TORCH_NUM_THREADS") is None:
            # 设置环境变量供后续代码读取（如果有）
            os.environ["TORCH_NUM_THREADS"] = str(torch_threads)
            settings.append(f"TORCH_NUM_THREADS={torch_threads}")

    # === ONNX Runtime 线程优化（表格识别模型）===
    # 即使有 GPU，表格识别在 pipeline 后端仍可能用 ONNX CPU 推理
    if os.getenv("MINERU_INTRA_OP_NUM_THREADS") is None:
        os.environ["MINERU_INTRA_OP_NUM_THREADS"] = str(onnx_threads)
        settings.append(f"MINERU_INTRA_OP_NUM_THREADS={onnx_threads}")

    if os.getenv("MINERU_INTER_OP_NUM_THREADS") is None:
        # inter_op 线程数通常设较小值，避免与 intra_op 竞争
        inter_threads = max(1, min(onnx_threads // 2, 4))
        os.environ["MINERU_INTER_OP_NUM_THREADS"] = str(inter_threads)
        settings.append(f"MINERU_INTER_OP_NUM_THREADS={inter_threads}")

    # === PDF 渲染线程优化 ===
    if os.getenv("MINERU_PDF_RENDER_THREADS") is None:
        os.environ["MINERU_PDF_RENDER_THREADS"] = str(render_threads)
        settings.append(f"MINERU_PDF_RENDER_THREADS={render_threads}")

    # === 处理窗口大小优化 ===
    # CPU 模式下减小窗口，降低内存峰值，同时让进度更新更频繁
    # batch_ratio=1 时（CPU模式），缩小窗口不影响吞吐，但能更细粒度上报进度
    if os.getenv("MINERU_PROCESSING_WINDOW_SIZE") is None:
        if not is_gpu:
            # CPU 模式：小窗口，每 2 页更新一次进度
            window = 2
        else:
            window = 64  # GPU 模式保持默认
        os.environ["MINERU_PROCESSING_WINDOW_SIZE"] = str(window)
        settings.append(f"MINERU_PROCESSING_WINDOW_SIZE={window}")

    # === OpenBLAS 线程优化 ===
    if not is_gpu:
        if os.getenv("OPENBLAS_NUM_THREADS") is None:
            os.environ["OPENBLAS_NUM_THREADS"] = str(torch_threads)
            settings.append(f"OPENBLAS_NUM_THREADS={torch_threads}")

    if settings:
        mode = "GPU" if is_gpu else "CPU"
        _logger.info(
            f"CPU 优化已启用 ({mode} 模式, {cpu_count} 核心): " + ", ".join(settings)
        )
