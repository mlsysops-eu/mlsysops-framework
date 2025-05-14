from cpufreq import cpuFreq


def initialize():
    pass

# TODO change to paylod
async def apply(value: dict[str, any]):
    """
    Applies the given CPU frequency settings based on the provided parameters.

    This method modifies the CPU's frequency settings by either applying the changes across
    all CPUs or targeting a specific CPU. The modifications set a new minimum and maximum
    frequency based on the input values.

    Args:
        value (dict):
         {
            "command": "reset" | "set",
            "cpu": "all" | "0,1,2...",
            "frequency" : "min" | "max" | "1000000 Hz"
        }
    """
    print(f"-----------CPU Set success ------> {value} ")
    return

    if "command" not in value:
        return


    match value['command']:
        case "reset":
            reset_to_governor()
            return
        case "set":
            cpufreq = cpuFreq()
            set_governor(governor="userspace", cpu="all")
            try:
                # Set frequency for all CPUs
                cpufreq.set_governor("userspace", cpu="all")
                if value['cpu'] == "all":
                    if value['cpu'] == "min":
                        set_to_min()
                    elif value['cpu'] == "max":
                        set_to_max()
                    else:
                        cpufreq.set_frequencies(value['frequency'])
                else:
                    # Set frequency for a specific CPU
                    cpufreq.set_governor("userspace", cpu=value['cpu'])
                    cpufreq.set_frequencies(int(value['frequency']), value['cpu'])
                print(f"Frequency successfully set {value}")
            except Exception as e:
                print(f"Error setting CPU frequency: {e}")
            finally:
                reset_to_governor()

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
    frequencies = cpufreq.get_available_frequencies()
    print("Available Frequencies (kHz):")
    for cpu, freqs in frequencies.items():
        print(f"  {cpu}: {freqs}")


def get_cpu_current_frequencies():
    cpufreq = cpuFreq()
    current_freqs = cpufreq.get_frequencies()
    print("Current Frequencies (kHz):")
    for cpu, freq in current_freqs.items():
        print(f"  {cpu}: {freq}")

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
