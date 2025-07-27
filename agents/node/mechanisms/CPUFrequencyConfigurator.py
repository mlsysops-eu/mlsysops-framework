from cpufreq import cpuFreq
from agents.mlsysops.logger_util import logger


def initialize(inbound_queue, outbound_queue,agent_state=None):
    pass


async def apply(self, payload: dict[str, any]) -> bool:
    """
    Apply CPU frequency settings based on the provided payload.

    Expected payload structure:
        {
            "core_id": int,
            "frequency": str  # e.g., "2.3GHz"
        }

    Args:
        payload (dict): Dictionary containing CPU configuration details.

    Returns:
        bool: True if applied successfully, False otherwise.
    """
    try:
        core_id = payload.get("core_id")
        frequency = payload.get("frequency")

        if core_id is None or frequency is None:
            raise ValueError("Payload must contain 'core_id' and 'frequency'")

        # Example: Apply the frequency (actual implementation depends on your mechanism)
        # For now, just log or simulate
        logger.debug(f"Applying CPU frequency: {frequency} to core {core_id}")
        
        return True
    except Exception as e:
        logger.error(f"Error applying CPU settings: {e}")
        return False

def get_options():
    """
    Retrieves the list of CPU available frequencies.

    This function calls another function to gather the available CPU
    frequencies supported by the system. These frequencies indicate
    the operating speeds at which the CPU can efficiently function, in
    harmony with system requirements and capabilities.

    Returns:
        list: A list of frequencies supported by the CPU.
    """

    return get_cpu_available_frequencies()

def get_state():
    """
    Retrieves the current CPU frequencies.

    This function retrieves the current frequency of the CPU cores using the
    `get_cpu_current_frequencies` method or function.

    Returns:
        list: A list of integers representing the current frequencies of the CPU cores. The
        frequencies are usually measured in MHz.
    """
    return get_cpu_current_frequencies()


def get_cpu_available_frequencies():
    cpufreq = cpuFreq()
    frequencies = {
        "min": cpufreq.get_min_freq(),
        "max": cpufreq.get_max_freq()
         }
    return frequencies


def get_cpu_current_frequencies():
    cpufreq = cpuFreq()
    current_freqs = cpufreq.get_frequencies()
    return current_freqs

def reset_to_governor(governor: str = "ondemand"):
    cpufreq = cpuFreq()
    try:
        cpufreq.set_governor(governor)
        print(f"Successfully reset CPU governor to '{governor}'")
    except Exception as e:
        print(f"Error setting governor: {e}")

def set_governor(governor: str, cpu: str = "all"):
    """
    Set the CPU governor for specific CPU or all CPUs.

    :param governor: The governor to set (e.g., 'userspace', 'performance').
    :param cpu: The CPU core to set the governor for ('all' or e.g. 'cpu0').
    """
    cpufreq = cpuFreq()
    try:
        if cpu == "all":
            cpufreq.set_governor(governor)
        else:
            cpufreq.set_governor(cpu=cpu, governor=governor)
        print(f"Successfully set governor to '{governor}' for {cpu}")
    except Exception as e:
        print(f"Error setting governor: {e}")

def set_to_min(cpu: str = "all"):
    """
    Set CPU frequency to the minimum available frequency.
    """
    frequencies = get_cpu_available_frequencies()
    min_freq = min(frequencies)
    print(f"Setting {cpu} to minimum frequency: {min_freq} kHz")
    if cpu == "all":
        set_governor("userspace", cpu="all")
        cpu.set_frequencies(min_freq)
    else:
        # If the CPU is specific, directly use the list of overall frequencies
        set_governor("userspace", cpu=cpu)
        cpu.set_frequencies(min_freq, cpu)

    print(f"Set {cpu} to minimum frequency: {min_freq} kHz")

def set_to_max(cpu: str = "all"):
    """
    Set CPU frequency to the maximum available frequency.
    """
    frequencies = get_cpu_available_frequencies()
    max_freq = max(frequencies)

    if cpu == "all":
        set_governor("userspace", cpu="all")
        cpu.set_frequencies(max_freq)
    else:
        set_governor("userspace", cpu=cpu)
        cpu.set_frequencies(max_freq, cpu)

    print(f"Set {cpu} to maximum frequency: {max_freq} kHz")
