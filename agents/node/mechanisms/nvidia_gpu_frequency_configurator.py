from typing import Any

import pynvml


def apply(value: Any):
    pynvml.nvmlInit()

    set_clock(value.gpu_id, graphics_clock=value.graphics_clock, memory_clock=value.memory_clock)
    
    cleanup()


def get_options():

    gpu_count = get_gpus()
    options = {}
    for gpu_id in range(gpu_count):
        gpu_name = get_gpu_name(gpu_id)
        clock_ranges = get_available_clock_ranges(gpu_id)
        options[gpu_name] = clock_ranges

    return options

def get_state():
    return ""

def get_gpus():
    """
    Get the number of GPUs available on the system.
    """
    return pynvml.nvmlDeviceGetCount()

def get_gpu_name(gpu_id: int):
    """
    Get the name of a specific GPU.
    :param gpu_id: ID of the GPU (e.g., 0, 1, ...).
    """
    handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_id)
    return pynvml.nvmlDeviceGetName(handle)

def get_current_clock(gpu_id: int):
    """
    Get the current clock speeds (graphics and memory) for a GPU.
    :param gpu_id: ID of the GPU.
    :return: Dictionary with current clock speeds.
    """
    handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_id)
    graphics_clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_GRAPHICS)
    memory_clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM)
    return {'graphics_clock': graphics_clock, 'memory_clock': memory_clock}

def get_available_clock_ranges(gpu_id: int):
    """
    Get the available clock ranges supported by the GPU for graphics and memory.
    :param gpu_id: ID of the GPU.
    :return: Dictionary with min/max clock speeds.
    """
    handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_id)
    min_graphics_clock = pynvml.nvmlDeviceGetMinClock(handle, pynvml.NVML_CLOCK_GRAPHICS)
    max_graphics_clock = pynvml.nvmlDeviceGetMaxClock(handle, pynvml.NVML_CLOCK_GRAPHICS)
    min_memory_clock = pynvml.nvmlDeviceGetMinClock(handle, pynvml.NVML_CLOCK_MEM)
    max_memory_clock = pynvml.nvmlDeviceGetMaxClock(handle, pynvml.NVML_CLOCK_MEM)

    return {
        'graphics': {'min': min_graphics_clock, 'max': max_graphics_clock},
        'memory': {'min': min_memory_clock, 'max': max_memory_clock}
    }

def set_clock(gpu_id: int, graphics_clock: int = None, memory_clock: int = None):
    """
    Set fixed clock speeds for a GPU for both graphics and memory.
    :param gpu_id: GPU ID to configure.
    :param graphics_clock: Desired fixed graphics clock.
    :param memory_clock: Desired fixed memory clock.
    """
    handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_id)

    if graphics_clock:
        pynvml.nvmlDeviceSetGpuLockedClocks(handle, graphics_clock, graphics_clock)
    if memory_clock:
        pynvml.nvmlDeviceSetMemoryLockedClocks(handle, memory_clock, memory_clock)

    print(f"Set GPU {gpu_id} to graphics clock: {graphics_clock}, memory clock: {memory_clock}")

def reset_clocks(gpu_id: int):
    """
    Reset GPU clocks to their default values.
    :param gpu_id: ID of the GPU.
    """
    handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_id)
    pynvml.nvmlDeviceResetGpuLockedClocks(handle)
    pynvml.nvmlDeviceResetMemoryLockedClocks(handle)
    print(f"Clocks reset for GPU {gpu_id}.")

def cleanup():
    """
    Shut down NVML properly.
    """
    pynvml.nvmlShutdown()

#
# if __name__ == "__main__":
#     # Example usage of the NvidiaGpuFrequencyConfigurator class
#     configurator = NvidiaGpuFrequencyConfigurator()
#
#     try:
#         # List all GPUs and their current clock speeds
#         gpu_count = configurator.get_gpus()
#         print(f"Number of GPUs: {gpu_count}")
#
#         for gpu_id in range(gpu_count):
#             gpu_name = configurator.get_gpu_name(gpu_id)
#             print(f"GPU {gpu_id}: {gpu_name}")
#
#             # Get current clock speeds
#             current_clocks = configurator.get_current_clock(gpu_id)
#             print(f"  Current Graphics Clock: {current_clocks['graphics_clock']} MHz")
#             print(f"  Current Memory Clock: {current_clocks['memory_clock']} MHz")
#
#             # Get available clock ranges
#             clock_ranges = configurator.get_available_clock_ranges(gpu_id)
#             print(
#                 f"  Available Graphics Clock Range: {clock_ranges['graphics']['min']} - {clock_ranges['graphics']['max']} MHz")
#             print(
#                 f"  Available Memory Clock Range: {clock_ranges['memory']['min']} - {clock_ranges['memory']['max']} MHz")
#
#             # Set new clock speeds (example - adjust as needed)
#             configurator.set_clock(gpu_id, graphics_clock=1500, memory_clock=7000)
#
#         # Reset clocks for the first GPU (example)
#         configurator.reset_clocks(gpu_id=0)
#
#     finally:
#         # Ensure NVML is cleaned up properly
#         configurator.cleanup()
#
#         if __name__ == "__main__":
#             # Example usage of the NvidiaGpuFrequencyConfigurator class
#             configurator = NvidiaGpuFrequencyConfigurator()
#
#             try:
#                 # List all GPUs and their current clock speeds
#                 gpu_count = configurator.get_gpus()
#                 print(f"Number of GPUs: {gpu_count}")
#
#                 for gpu_id in range(gpu_count):
#                     gpu_name = configurator.get_gpu_name(gpu_id)
#                     print(f"GPU {gpu_id}: {gpu_name}")
#
#                     # Get current clock speeds
#                     current_clocks = configurator.get_current_clock(gpu_id)
#                     print(f"  Current Graphics Clock: {current_clocks['graphics_clock']} MHz")
#                     print(f"  Current Memory Clock: {current_clocks['memory_clock']} MHz")
#
#                     # Get available clock ranges
#                     clock_ranges = configurator.get_available_clock_ranges(gpu_id)
#                     print(
#                         f"  Available Graphics Clock Range: {clock_ranges['graphics']['min']} - {clock_ranges['graphics']['max']} MHz")
#                     print(
#                         f"  Available Memory Clock Range: {clock_ranges['memory']['min']} - {clock_ranges['memory']['max']} MHz")
#
#                     # Set new clock speeds (example - adjust as needed)
#                     configurator.set_clock(gpu_id, graphics_clock=1500, memory_clock=7000)
#
#                 # Reset clocks for the first GPU (example)
#                 configurator.reset_clocks(gpu_id=0)
#
#             finally:
#                 # Ensure NVML is cleaned up properly
#                 configurator.cleanup()