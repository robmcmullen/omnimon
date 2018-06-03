#!/usr/bin/env python
""" Convert udis module level data into a single dictionary structure for all
known processors and save it into cputables.py

"""
import os
import glob

from udis_fast.flags import pcr, und, z80bit, lbl, comment, flag_label, flag_return, flag_jump, flag_branch


def fix_opcode_table(cpu, allow_undoc=False):
    """ Find the NOP opcode and add the 'flag' variable if it doesn't exist so
    calling programs don't have to use a try statement to see if there are 3 or
    4 values in the tuple.
    """
    table = cpu['opcodeTable']
    labels = cpu.get('labelTargets', {})
    jump = cpu.get('jumpOpcodes', set())
    branch = cpu.get('branchOpcodes', set())
    branch_modes = cpu.get('branchModes', set())
    exclude_modes = cpu.get('modesExclude', set())
    ret = cpu.get('returnOpcodes', set())
    possibilities = []
    nop = 0x00
    found_undoc = False
    fixed_table = {}
    for opcode, optable in list(table.items()):
        try:
            length, mnemonic, mode, flag = optable
        except ValueError:
            length, mnemonic, mode = optable
            flag = 0
        if flag & und:
            found_undoc = True
            if not allow_undoc:
                continue
        if mode in labels:
            flag |= flag_label
        if mnemonic in ret:
            flag |= flag_return
        elif mode not in exclude_modes:
            if mnemonic in jump:
                flag |= flag_jump
            elif mnemonic in branch or mode in branch_modes:
                flag |= flag_branch
        fixed_table[opcode] = (length, mnemonic, mode, flag)
        if mnemonic == "nop" and flag == 0:
            nop = opcode
    cpu['opcodeTable'] = fixed_table
    return nop, found_undoc


def read_udis(pathname):
    """ Read all the processor-specific opcode info and pull into a container
    dictionary keyed on the processor name.
    
    The udis files have module level data, so this pulls the data from multiple
    cpus into a single structure that can then be refereced by processor name.
    For example, to find the opcode table in the generated dictionary for the
    6502 processor, use:
    
    cpus['6502']['opcodeTable']
    """
    files = glob.glob("%s/*.py" % pathname)
    cpus = {}
    for filename in files:
        localfile = os.path.basename(filename)
        with open(filename, "r") as fh:
            source = fh.read()
            if "import cputables" in source:
                continue
            if "addressModeTable" in source and "opcodeTable" in source:
                cpu_name, _ = os.path.splitext(localfile)
                g = {"pcr": pcr, "und": und, "z80bit": z80bit, "lbl": lbl, "comment": comment}
                d = {}
                try:
                    exec(source, g, d)
                    if 'opcodeTable' in d:
                        cpus[cpu_name] = d
                        nop, found_undoc = fix_opcode_table(d, False)
                        cpus[cpu_name]["nop"] = nop
                        if found_undoc:
                            # reload because dict was modified in fix_opcode_table
                            d = {}
                            exec(source, g, d)
                            cpu_name = "%sundoc" % cpu_name
                            cpus[cpu_name] = d
                            nop, found_undoc = fix_opcode_table(d, True)
                            cpus[cpu_name]["nop"] = nop
                except SyntaxError:
                    # ignore any python 3 files
                    pass
    return cpus


if __name__ == "__main__":
    import sys
    import argparse
    
    supported_cpus = read_udis(".")
    output = []
    import pprint
    output.append("# Autogenerated from udis source! Do not edit here, change udis source instead.")
    output.append("processors =\\")
    for line in pprint.pformat(supported_cpus).splitlines():
        output.append(line.strip())
#    print supported_cpus
    with open("cputables.py", "w") as fh:
        fh.write("\n".join(output))
        fh.write("\n")
