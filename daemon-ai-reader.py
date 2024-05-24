import sys, getopt, re, time
import subprocess as sp
from os import listdir
from os.path import isfile, join, exists

SMI_QUERY      = ['index','gpu_name','utilization.gpu','power.draw','power.max_limit']
SMI_QUERY_FLAT = ','.join(SMI_QUERY)
DELAY_S        = 5
PRECISION      = 2
LIVE_DISPLAY   = False

def print_usage():
    print('python3 nvidiasmi-reader.py [--help] [--live] [--output=' + OUTPUT_FILE + '] [--delay=' + str(DELAY_S) + ' (in sec)] [--precision=' + str(PRECISION) + ' (number of decimal)]')

###########################################
# Read NVIDIA SMI
###########################################
##########
# nvidia-smi -L
# nvidia-smi --help-query-gpu

#"utilization.gpu"
#Percent of time over the past sample period during which one or more kernels was executing on the GPU.
#The sample period may be between 1 second and 1/6 second depending on the product.

#"utilization.memory"
#Percent of time over the past sample period during which global (device) memory was being read or written.
#The sample period may be between 1 second and 1/6 second depending on the product.
##########

def __generic_smi(command : str):
    try:
        csv_like_data = sp.check_output(command.split(),stderr=sp.STDOUT).decode('ascii').split('\n')
        smi_data = [cg_data.split(',') for cg_data in csv_like_data[:-1]] # end with ''
    except sp.CalledProcessError as e:
        raise RuntimeError("command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))
    return smi_data

def discover_smi():
    COMMAND = "nvidia-smi -L"
    return __generic_smi(COMMAND)

def __convert_cg_to_dict(header : list, data_single_gc : list):
    results = {}
    for position, query in enumerate(SMI_QUERY):
        if 'N/A' in data_single_gc[position]:
            value = 'NA'
        elif '[' in header[position]: # if a unit is written, like [MiB], we have to strip it from value
            value = float(re.sub("[^\d\.]", "", data_single_gc[position]))
        else:
            value = data_single_gc[position].strip()
        results[query] = value
    return results

def query_smi():
    COMMAND = "nvidia-smi --query-gpu=" + SMI_QUERY_FLAT + " --format=csv"
    smi_data = __generic_smi(COMMAND)
    header = smi_data[0]
    data   = smi_data[1:]
    return [__convert_cg_to_dict(header, data_single_gc) for data_single_gc in data]

###########################################
# Main loop, read periodically
###########################################
def loop_read():
    launch_at = time.time_ns()
    while True:
        time_begin = time.time_ns()

        smi_measures = query_smi()
        output(smi_measures=smi_measures, time_since_launch=int((time_begin-launch_at)/(10**9)))

        time_to_sleep = (DELAY_S*10**9) - (time.time_ns() - time_begin)
        if time_to_sleep>0: time.sleep(time_to_sleep/10**9)
        else: print('Warning: overlap iteration', -(time_to_sleep/10**9), 's')

def output(smi_measures : list, time_since_launch : int):

    if LIVE_DISPLAY and smi_measures:
        total_draw  = 0
        total_limit = 0
        for gc_as_dict in smi_measures:
            print(gc_as_dict['index'] + ':', str(gc_as_dict['utilization.gpu']) + '%', str(gc_as_dict['power.draw']) + '/' + str(gc_as_dict['power.max_limit']) + ' W')
            total_draw += gc_as_dict['power.draw']
            total_limit+= gc_as_dict['power.max_limit']
        print('Total:', str(round(total_draw,PRECISION)) + '/' + str(round(total_limit,PRECISION)) + ' W')
        print('---')

###########################################
# Entrypoint, manage arguments
###########################################
if __name__ == '__main__':

    short_options = 'hd:p:'
    long_options = ['help', 'delay=', 'precision=']

    try:
        arguments, values = getopt.getopt(sys.argv[1:], short_options, long_options)
    except getopt.error as err:
        print(str(err))
        print_usage()
    for current_argument, current_value in arguments:
        if current_argument in ('-h', '--help'):
            print_usage()
            sys.exit(0)
        elif current_argument in('-p', '--precision'):
            PRECISION= int(current_value)
        elif current_argument in('-d', '--delay'):
            DELAY_S= float(current_value)

    try:
        # Find domains
        print('>SMI GC found:')
        for gc in discover_smi(): print(gc[0])
        # Launch
        loop_read()
    except KeyboardInterrupt:
        print('Program interrupted')
        sys.exit(0)