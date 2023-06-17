import datetime
import os
from subprocess import PIPE, run

def run_pgen (temperature, node=45, vdd=None, vth=None):
    result = None
    if temperature >= 77:
        if vdd == None and vth == None:
            result = run ("python ../CryoMOSFET/CryoMOSFET_77K/pgen.py -n {} -t {}".format \
            (node, temperature), stdout=PIPE, stderr=PIPE, universal_newlines=True, shell=True)
        else:
            result = run ("python ../CryoMOSFET/CryoMOSFET_77K/pgen.py -n {} -d {} -r {} -t {}".format \
                (node, vdd, vth, temperature), stdout=PIPE, stderr=PIPE, universal_newlines=True, shell=True)
    else:
        if vdd == None and vth == None:
            result = run ("python ../CryoMOSFET/CryoMOSFET_4K/pgen.py -n {} -t {}".format \
                (node, temperature), stdout=PIPE, stderr=PIPE, universal_newlines=True, shell=True)
        else:
            result = run ("python ../CryoMOSFET/CryoMOSFET_4K/pgen.py -n {} -d {} -r {} -t {}".format \
                (node, vdd, vth, temperature), stdout=PIPE, stderr=PIPE, universal_newlines=True, shell=True)
    return result.stdout


def set_targets (design_name, rtl_dir, out_dir):
    dir_names = ["./dc_compile/logic_synthesis/", "./dc_compile/critical_path_extraction/"]
    file_list = list ()
    for dir_name in dir_names:
        file_list = file_list + [dir_name+name_ for name_ in os.listdir (dir_name)]

    for file_name in file_list:
        if ".tcl" in file_name:
            f = open (file_name, "r")
            nf = open (file_name+"_", "w")
            lines = f.readlines ()
            for line in lines:
                if "set src_path" in line:
                    nf.write("set src_path \"{}\"\n".format(rtl_dir))
                elif "set out_path" in line:
                    nf.write("set out_path \"{}\"\n".format(out_dir))
                elif "set TOP_MODULE" in line:
                    nf.write ("set TOP_MODULE {}\n".format (design_name))
                else:
                    nf.write (line)
            f.close ()
            nf.close ()
            os.system ("rm {}".format (file_name))
            os.system ("mv {} {}".format (file_name+"_", file_name))
    return


def run_synthesis (design_name, temperature, out_dir, regen):
    # 300k ddc
    if regen or not os.path.isfile("{}/{}_critical_path_300k".format(out_dir, design_name)):
        if regen or not os.path.isfile("{}/{}_300k.ddc".format(out_dir, design_name)):
            os.system("make dc-topo-300k")
        else:
            pass
    else:
        pass
    # 300k-nowire ddc
    if regen or not os.path.isfile("{}/{}_critical_path_300k_nowire".format(out_dir, design_name)):
        if regen or not os.path.isfile("{}/{}_300k_nowire.ddc".format(out_dir, design_name)):
            os.system("make dc-topo-300k-nowire")
        else:
            pass
    else:
        pass
    # {temperature}k ddc (4k or 77k)
    if regen or not os.path.isfile("{}/{}_critical_path_{}k".format(out_dir, design_name, temperature)):
        if regen or not os.path.isfile("{}/{}_{}k.ddc".format(out_dir, design_name, temperature)):
            os.system("make dc-topo-{}k".format(temperature))
        else:
            pass
    else:
        pass
    # {temperature}k-nowire ddc (4k or 77k)
    if regen or not os.path.isfile("{}/{}_critical_path_{}k_nowire".format(out_dir, design_name, temperature)):
        if regen or not os.path.isfile("{}/{}_{}k_nowire.ddc".format(out_dir, design_name, temperature)):
            os.system("make dc-topo-{}k-nowire".format(temperature))
        else:
            pass
    else:
        pass
    return


def critical_path_analysis (design_name, temperature, out_dir):
    f = open ("{}/{}_critical_path_{}k".format (out_dir, design_name, temperature))
    lines = f.readlines ()
    paths = list ()
    token = 0
    for line in lines:
        if token == 0 and "clock network delay (ideal)" in line:
            token += 1
        elif token == 1 and "/" in line:
            paths.append ("/".join (line.split ("/")[:-2])+"*")
        elif token == 1 and "library setup time" in line:
            break
    return list (dict.fromkeys (paths))


def insert_paths (temperature, paths):
    file_name = "dc_compile/critical_path_extraction/critical_path_{}k_nowire.tcl".format (temperature)
    f = open (file_name, "r")
    nf = open (file_name+"_", "w")

    command = "redirect ${out_path}/${TOP_MODULE}_critical_path_" + str (temperature) + "k_nowire " + \
                "{report_timing"
    for path in [paths[0], paths[-1]]:
        command += " -through [get_pins -of_objects {" + path + "}]"
    command += "}\n"

    lines = f.readlines ()
    for line in lines:
        if "report_timing" in line:
            nf.write (command)
        else:
            nf.write (line)
    f.close ()
    nf.close ()
    os.system ("rm {}".format (file_name))
    os.system ("mv {} {}".format (file_name+"_", file_name))
    return


def run_delay_extraction (design_name, temperature, out_dir, regen):
    # 300K critical path (transistor + wire).
    if regen or not os.path.isfile("{}/{}_critical_path_300k".format(out_dir, design_name)):
        os.system ("make critical-300k")
    else:
        pass
    # 300K critical path (transistor only).
    if regen or not os.path.isfile("{}/{}_critical_path_300k_nowire".format(out_dir, design_name)):
        paths = critical_path_analysis (design_name, 300, out_dir)
        insert_paths (300, paths)
        os.system ("make critical-300k-nowire")
    else:
        pass
    # Critical path at target temperature (transistor + wire).
    if regen or not os.path.isfile("{}/{}_critical_path_{}k".format(out_dir, design_name, temperature)):
        os.system ("make critical-{}k".format(temperature))
    else:
        pass
    # Critical path at target temperature (transistor only).
    if regen or not os.path.isfile("{}/{}_critical_path_{}k_nowire".format(out_dir, design_name, temperature)):
        paths = critical_path_analysis (design_name, temperature, out_dir)
        insert_paths (temperature, paths)
        os.system ("make critical-{}k-nowire".format(temperature))
    else:
        pass
    return

def report_perf_power (design_name, temperature, node, vdd, vth, out_dir):
    critical_delays = list ()
    dynamic_powers = list ()
    static_powers = list ()
    total_powers = list ()
    file_names = ["300k", "300k_nowire", "{}k".format (temperature), "{}k_nowire".format (temperature)]
    
    for file_name in file_names:
        f = open ("{}/{}_critical_path_".format(out_dir, design_name) + file_name, "r")
        lines = f.readlines ()
        for line in lines:
            if "data arrival time" in line:
                critical_delays.append (float (line.split ()[-1]))
                break
        f.close ()
        f = open ("{}/{}_power_".format(out_dir, design_name) + file_name, "r")
        lines = f.readlines ()
        for line in lines:
            data = line.split ()
            if len (data) < 6:
                continue
            elif design_name in data[0]:
                dynamic_powers.append (float (data[1])*1e-6 + float (data[2])*1e-6)
                static_powers.append (float (data[3])*1e-9)
                total_powers.append (float (data[4])*1e-6)
    
    # If the wire-delay value is negative,
    if critical_delays[0] < critical_delays[1]:
        critical_delays[1] = critical_delays[0]
    if critical_delays[2] < critical_delays[3]:
        critical_delays[3] = critical_delays[2]

    critical_delays_total = list ()
    critical_delays_tran = list ()
    critical_delays_wire = list ()
    powers_total = list ()
    powers_static = list ()
    powers_dynamic = list ()

    critical_delays_total = [critical_delays[0], critical_delays[2]]
    critical_delays_tran = [critical_delays[1], critical_delays[3]]
    critical_delays_wire = [critical_delays[0] - critical_delays[1], critical_delays[2] - critical_delays[3]]
    powers_total = [total_powers[0], total_powers[2]]
    powers_static = [static_powers[0], static_powers[2]]
    powers_dynamic = [dynamic_powers[0], dynamic_powers[2]]

    pgen_300k_freepdk = run_pgen (300, node, 1.1, 0.46893) # FreePDK45nm.
    pgen_300k = run_pgen (300, node, 1.25, 0.46893) # Intel 45nm CPU.
    pgen_temp = run_pgen (temperature, node, vdd, vth)

    pgen_ref_freepdk = dict ()
    lines = pgen_300k_freepdk.split ("\n")
    for line in lines:
        if "Vdd" in line:
            pgen_ref_freepdk["Vdd"] = float (line.split ()[1])
        if "Ion" in line:
            pgen_ref_freepdk["Ion"] = float (line.split ()[1])
        if "Isub" in line:
            pgen_ref_freepdk["Isub"] = float (line.split ()[1])
        if "Igate" in line:
            pgen_ref_freepdk["Igate"] = float (line.split ()[1])
            break

    pgen_ref = dict ()
    lines = pgen_300k.split ("\n")
    for line in lines:
        if "Vdd" in line:
            pgen_ref["Vdd"] = float (line.split ()[1])
        if "Ion" in line:
            pgen_ref["Ion"] = float (line.split ()[1])
        if "Isub" in line:
            pgen_ref["Isub"] = float (line.split ()[1])
        if "Igate" in line:
            pgen_ref["Igate"] = float (line.split ()[1])
            break

    pgen_target = dict ()
    lines = pgen_temp.split ("\n")
    for line in lines:
        if "Vdd" in line:
            pgen_target["Vdd"] = float (line.split ()[1])
        if "Ion" in line:
            pgen_target["Ion"] = float (line.split ()[1])
        if "Isub" in line:
            pgen_target["Isub"] = float (line.split ()[1])
        if "Igate" in line:
            pgen_target["Igate"] = float (line.split ()[1])
            break

    # To compensate for the different voltage level at 300K (vs. 1.1V of FreePDK 45nm).
    # Transistor speed-up (Ion/Vdd)
    trans_speedup_300k = (pgen_ref["Ion"]/pgen_ref["Vdd"]) / (pgen_ref_freepdk["Ion"]/pgen_ref_freepdk["Vdd"])
    # Dynamic power reduction (Vdd^2)
    dyn_reduction_300k = ((pgen_ref["Vdd"]**2) / (pgen_ref_freepdk["Vdd"]**2))
    # Static power reduction (Isub+Igate)
    stat_reduction_300k = ((pgen_ref["Vdd"]*(pgen_ref["Isub"]+pgen_ref["Igate"])) \
                      / (pgen_ref_freepdk["Vdd"]*(pgen_ref_freepdk["Isub"]+pgen_ref_freepdk["Igate"])))
    
    critical_delays_total_prev = critical_delays_total[0]
    critical_delays_tran[0] = critical_delays_tran[0] / trans_speedup_300k
    critical_delays_total[0] = critical_delays_tran[0] + critical_delays_wire[0]
    speedup_300k = critical_delays_total_prev/critical_delays_total[0]

    powers_dynamic[0] = powers_dynamic[0] * dyn_reduction_300k * speedup_300k
    powers_static[0] = powers_static[0] * stat_reduction_300k
    powers_total[0] = powers_dynamic[0] + powers_static[0]

    # Caculate the critical-path delay and power at the target temperature.
    # Transistor speed-up (Ion/Vdd)
    trans_speedup = (pgen_target["Ion"]/pgen_target["Vdd"]) / (pgen_ref_freepdk["Ion"]/pgen_ref_freepdk["Vdd"])
    # Dynamic power reduction (Vdd^2)
    dyn_reduction = ((pgen_target["Vdd"]**2) / (pgen_ref_freepdk["Vdd"]**2))
    # Static power reduction (Isub+Igate)
    stat_reduction = ((pgen_target["Vdd"]*(pgen_target["Isub"]+pgen_target["Igate"])) \
                      / (pgen_ref_freepdk["Vdd"]*(pgen_ref_freepdk["Isub"]+pgen_ref_freepdk["Igate"])))

    critical_delays_tran[1] = critical_delays_tran[1] / trans_speedup
    critical_delays_total[1] = critical_delays_tran[1] + critical_delays_wire[1]
    speedup = critical_delays_total_prev/critical_delays_total[1]

    powers_dynamic[1] = powers_dynamic[1] * dyn_reduction * speedup
    powers_static[1] = powers_static[1] * stat_reduction
    powers_total[1] = powers_dynamic[1] + powers_static[1]

    print ("================")
    print ("Critical-path delay at 300K")
    print ("  Total delay:\t\t{0:.6f} [ns]".format (critical_delays_total[0]))
    print ("    Transistor:\t\t{0:.6f} [ns]".format (critical_delays_tran[0]))
    print ("    Wire:\t\t{0:.6f} [ns]\n".format (critical_delays_wire[0]))

    print ("Critical-path delay at {}K".format (temperature))
    print ("  Total delay:\t\t{0:.6f} [ns]".format (critical_delays_total[1]))
    print ("    Transistor:\t\t{0:.6f} [ns]".format (critical_delays_tran[1]))
    print ("    Wire:\t\t{0:.6f} [ns]\n".format (critical_delays_wire[1]))
    
    print ("Speed-up:\t\t{0:.6f} times\n".format (critical_delays_total[0]/critical_delays_total[1]))

    print ("================")
    print ("Power consumption at 300K")
    print ("  Total power:\t\t{0:.6f} [W]".format (powers_total[0]))
    print ("    Static power:\t{0:.6f} [W]".format (powers_static[0]))
    print ("    Dynamic power:\t{0:.6f} [W]\n".format (powers_dynamic[0]))

    print ("Power consumption at {}K".format (temperature))
    print ("  Total power:\t\t{0:.6f} [W]".format (powers_total[1]))
    print ("    Static power:\t{0:.6f} [W]".format (powers_static[1]))
    print ("    Dynamic power:\t{0:.6f} [W]\n".format (powers_dynamic[1]))
    
    print ("Power reduction:\t{0:.6f} times\n".format (powers_total[0]/powers_total[1]))

    ### ourput
    freq = round(1/critical_delays_total[1], 2)
    p_stat = round(powers_static[1], 5)
    p_dyn = round(powers_dynamic[1], 5)
    ###
    freq_300k = round(1/critical_delays_total[0], 2)
    p_stat_300k = round(powers_static[0], 5)
    p_dyn_300k = round(powers_dynamic[0], 5)

    return freq, p_stat, p_dyn, freq_300k, p_stat_300k, p_dyn_300k


def clean_up ():
    os.system ("make clean")
    return

def run_cmos_model(temperature, 
                  node, 
                  vdd, 
                  vth, 
                  design_name, 
                  rtl_dir, 
                  out_dir,
                  regen_synth, 
                  regen_result):

    vdd = vdd if vdd > 0 else 1.25     # Vdd of 45nm Intel CPU
    vth = vth if vth > 0 else 0.46893  # Vth of 45nm Intel CPU

    # output directory gen.
    if not os.path.isdir(out_dir):
        os.mkdir(out_dir)

    # Input-requirement checking.
    if node != 45:
        print ("Currently, CryoPipeline only supports 45nm.")
        exit ()
    if not any ((temperature == key_) for key_ in [300, 77, 4]):
        print ("Currently, CryoPipeline only supports 300K, 77K, and 4K.")
        exit ()
    
    # Run
    start_time = datetime.datetime.now ()
    run_pgen (temperature, node, vdd, vth)
    set_targets(design_name, rtl_dir, out_dir)
    run_synthesis (design_name, temperature, out_dir, regen_synth)
    run_delay_extraction (design_name, temperature, out_dir, regen_result)
    freq, p_stat, p_dyn, freq_300k, p_stat_300k, p_dyn_300k = report_perf_power (design_name, temperature, node, vdd, vth, out_dir)
    clean_up()
    end_time = datetime.datetime.now ()

    print("{} {}K Start time: {}".format(design_name, temperature, start_time))
    print("{} {}K End time: {}".format(design_name, temperature, end_time))
    
    area = 0 # no area support
    return freq, p_stat, p_dyn, freq_300k, p_stat_300k, p_dyn_300k, area
