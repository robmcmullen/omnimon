##########################################################################
#
# Processor specific code

# CPU = "6502"
# Description = "MOS Technology (and others) 6502 8-bit microprocessor."
# DataWidth = 8  # 8-bit data
# AddressWidth = 16  # 16-bit addresses

# Maximum length of an instruction (for formatting purposes)
maxLength = 3

# Leadin bytes for multibyte instructions
leadInBytes = []

# Addressing mode table
# List of addressing modes and corresponding format strings for operands.
addressModeTable = {
"implicit"    : "",
"absolute"    : "${1:02X}{0:02X}",
"absolutex"   : "${1:02X}{0:02X},x",
"absolutey"   : "${1:02X}{0:02X},y",
"accumulator" : "a",
"immediate"   : "#${0:02X}",
"indirectx"   : "(${0:02X},x)",
"indirecty"   : "(${0:02X}),y",
"indirect"    : "(${1:02X}{0:02X})",
"relative"    : "${0:04X}",
"zeropage"    : "${0:02X}",
"zeropagex"   : "${0:02X},x",
"zeropagey"   : "${0:02X},y",
}

# Address modes that reference an address
# Any opcodes that use one of these address modes refer to an absolute
# address in memory, and are a candidate to be replaced by a label
labelTargets = set(["absolute", "absolutex", "absolutey", "indirect", "indirectx", "indirecty", "zeropage", "zeropagex", "zeropagey"])

jumpOpcodes = set(["jmp"])
branchModes = set(["relative"])
branchOpcodes = set(["jsr"])
modesExclude = set(["indirect"])
returnOpcodes = set(["rts", "rti", "brk"])

# Op Code Table
# Key is numeric opcode (possibly multiple bytes)
# Value is a list:
#   # bytes
#   mnemonic
#   addressing mode
#   flags (e.g. pcr)
opcodeTable = {
0x00 : [ 1, "brk", "implicit"        ],
0x01 : [ 2, "ora", "indirectx"       ],
0x02 : [ 1, "hlt", "implicit", und   ],
0x03 : [ 2, "slo", "indirectx", und  ],
0x04 : [ 2, "nop", "zeropage", und   ],
0x05 : [ 2, "ora", "zeropage"        ],
0x06 : [ 2, "asl", "zeropage"        ],
0x07 : [ 2, "slo", "zeropage", und   ],
0x08 : [ 1, "php", "implicit"        ],
0x09 : [ 2, "ora", "immediate"       ],
0x0a : [ 1, "asl", "accumulator"     ],
0x0b : [ 2, "anc", "immediate", und  ],
0x0c : [ 3, "nop", "absolute", und   ],
0x0d : [ 3, "ora", "absolute"        ],
0x0e : [ 3, "asl", "absolute"        ],
0x0f : [ 3, "slo", "absolute", und   ],

0x10 : [ 2, "bpl", "relative", pcr   ],
0x11 : [ 2, "ora", "indirecty"       ],
0x12 : [ 1, "hlt", "implicit", und   ],
0x13 : [ 2, "slo", "indirecty", und  ],
0x14 : [ 2, "nop", "zeropagex", und  ],
0x15 : [ 2, "ora", "zeropagex"       ],
0x16 : [ 2, "asl", "zeropagex"       ],
0x17 : [ 2, "slo", "zeropagex", und  ],
0x18 : [ 1, "clc", "implicit"        ],
0x19 : [ 3, "ora", "absolutey"       ],
0x1a : [ 1, "nop", "implicit", und   ],
0x1b : [ 3, "slo", "absolutey", und  ],
0x1c : [ 3, "nop", "absolutex", und  ],
0x1d : [ 3, "ora", "absolutex"       ],
0x1e : [ 3, "asl", "absolutex"       ],
0x1f : [ 3, "slo", "absolutex", und  ],

0x20 : [ 3, "jsr", "absolute"        ],
0x21 : [ 2, "and", "indirectx"       ],
0x22 : [ 1, "hlt", "implicit", und   ],
0x23 : [ 2, "rla", "indirecty", und  ],
0x24 : [ 2, "bit", "zeropage"        ],
0x25 : [ 2, "and", "zeropage"        ],
0x26 : [ 2, "rol", "zeropage"        ],
0x27 : [ 2, "rla", "zeropage", und   ],
0x28 : [ 1, "plp", "implicit"        ],
0x29 : [ 2, "and", "immediate"       ],
0x2a : [ 1, "rol", "accumulator"     ],
0x2b : [ 2, "anc", "immediate", und  ],
0x2c : [ 3, "bit", "absolute"        ],
0x2d : [ 3, "and", "absolute"        ],
0x2e : [ 3, "rol", "absolute"        ],
0x2f : [ 3, "rla", "absolute", und   ],

0x30 : [ 2, "bmi", "relative", pcr   ],
0x31 : [ 2, "and", "indirecty"       ],
0x32 : [ 1, "hlt", "implicit", und   ],
0x34 : [ 2, "nop", "zeropagex", und  ],
0x35 : [ 2, "and", "zeropagex"       ],
0x36 : [ 2, "rol", "zeropagex"       ],
0x37 : [ 2, "rla", "zeropagex", und  ],
0x38 : [ 1, "sec", "implicit"        ],
0x39 : [ 3, "and", "absolutey"       ],
0x3a : [ 1, "nop", "implicit", und   ],
0x3b : [ 3, "rla", "absolutey", und  ],
0x3c : [ 3, "nop", "absolutex", und  ],
0x3d : [ 3, "and", "absolutex"       ],
0x3e : [ 3, "rol", "absolutex"       ],
0x3f : [ 3, "rla", "absolutex", und  ],

0x40 : [ 1, "rti", "implicit"        ],
0x41 : [ 2, "eor", "indirectx"       ],
0x42 : [ 1, "hlt", "implicit", und   ],
0x43 : [ 2, "sre", "indirectx", und  ],
0x44 : [ 2, "nop", "zeropage", und   ],
0x45 : [ 2, "eor", "zeropage"        ],
0x46 : [ 2, "lsr", "zeropage"        ],
0x47 : [ 2, "sre", "zeropage", und   ],
0x48 : [ 1, "pha", "implicit"        ],
0x49 : [ 2, "eor", "immediate"       ],
0x4a : [ 1, "lsr", "accumulator"     ],
0x4b : [ 2, "alr", "immediate", und  ],
0x4c : [ 3, "jmp", "absolute"        ],
0x4d : [ 3, "eor", "absolute"        ],
0x4e : [ 3, "lsr", "absolute"        ],
0x4f : [ 3, "sre", "absolute", und   ],

0x50 : [ 2, "bvc", "relative", pcr   ],
0x51 : [ 2, "eor", "indirecty"       ],
0x52 : [ 1, "hlt", "implicit", und   ],
0x53 : [ 2, "sre", "indirecty", und  ],
0x54 : [ 2, "nop", "zeropagex", und  ],
0x55 : [ 2, "eor", "zeropagex"       ],
0x56 : [ 2, "lsr", "zeropagex"       ],
0x57 : [ 2, "sre", "zeropagex", und  ],
0x58 : [ 1, "cli", "implicit"        ],
0x59 : [ 3, "eor", "absolutey"       ],
0x5a : [ 1, "nop", "implicit", und   ],
0x5b : [ 3, "sre", "absolutey", und  ],
0x5c : [ 3, "nop", "absolutex", und  ],
0x5d : [ 3, "eor", "absolutex"       ],
0x5e : [ 3, "lsr", "absolutex"       ],
0x5f : [ 3, "sre", "absolutex", und  ],

0x60 : [ 1, "rts", "implicit"        ],
0x61 : [ 2, "adc", "indirectx"       ],
0x62 : [ 1, "hlt", "implicit", und   ],
0x63 : [ 2, "rra", "indirectx", und  ],
0x64 : [ 2, "nop", "zeropage", und   ],
0x65 : [ 2, "adc", "zeropage"        ],
0x66 : [ 2, "ror", "zeropage"        ],
0x67 : [ 2, "rra", "zeropage", und   ],
0x68 : [ 1, "pla", "implicit"        ],
0x69 : [ 2, "adc", "immediate"       ],
0x6a : [ 1, "ror", "accumulator"     ],
0x6b : [ 2, "arr", "immediate", und  ],
0x6c : [ 3, "jmp", "indirect"        ],
0x6d : [ 3, "adc", "absolute"        ],
0x6e : [ 3, "ror", "absolute"        ],
0x6f : [ 3, "rra", "absolute", und   ],

0x70 : [ 2, "bvs", "relative", pcr   ],
0x71 : [ 2, "adc", "indirecty"       ],
0x72 : [ 1, "hlt", "implicit", und   ],
0x73 : [ 2, "rra", "indirecty", und  ],
0x74 : [ 2, "nop", "zeropagex", und  ],
0x75 : [ 2, "adc", "zeropagex"       ],
0x76 : [ 2, "ror", "zeropagex"       ],
0x77 : [ 2, "rra", "zeropagex", und  ],
0x78 : [ 1, "sei", "implicit"        ],
0x79 : [ 3, "adc", "absolutey"       ],
0x7a : [ 1, "nop", "implicit", und   ],
0x7b : [ 3, "rra", "absolutey", und  ],
0x7c : [ 3, "nop", "absolutex", und  ],
0x7d : [ 3, "adc", "absolutex"       ],
0x7e : [ 3, "ror", "absolutex"       ],
0x7f : [ 3, "rra", "absolutex", und  ],

0x80 : [ 2, "nop", "immediate", und  ],
0x81 : [ 2, "sta", "indirectx"       ],
0x82 : [ 2, "nop", "immediate", und  ],
0x83 : [ 2, "sax", "indirectx", und  ],
0x84 : [ 2, "sty", "zeropage"        ],
0x85 : [ 2, "sta", "zeropage"        ],
0x86 : [ 2, "stx", "zeropage"        ],
0x87 : [ 2, "sax", "zeropage", und   ],
0x88 : [ 1, "dey", "implicit"        ],
0x89 : [ 2, "nop", "immediate", und  ],
0x8a : [ 1, "txa", "implicit"        ],
0x8b : [ 2, "xaa", "immediate", und  ],
0x8c : [ 3, "sty", "absolute"        ],
0x8d : [ 3, "sta", "absolute"        ],
0x8e : [ 3, "stx", "absolute"        ],
0x8f : [ 3, "sax", "absolute", und   ],

0x90 : [ 2, "bcc", "relative", pcr   ],
0x91 : [ 2, "sta", "indirecty"       ],
0x92 : [ 1, "hlt", "implicit", und   ],
0x93 : [ 2, "sha", "indirecty", und  ],
0x94 : [ 2, "sty", "zeropagex"       ],
0x95 : [ 2, "sta", "zeropagex"       ],
0x96 : [ 2, "stx", "zeropagey"       ],
0x97 : [ 2, "sax", "zeropagey", und  ],
0x98 : [ 1, "tya", "implicit"        ],
0x99 : [ 3, "sta", "absolutey"       ],
0x9a : [ 1, "txs", "implicit"        ],
0x9b : [ 3, "shs", "absolutey", und  ],
0x9c : [ 3, "shy", "absolutex", und  ],
0x9d : [ 3, "sta", "absolutex"       ],
0x9e : [ 3, "shx", "absolutey", und  ],
0x9f : [ 3, "sha", "absolutey", und  ],

0xa0 : [ 2, "ldy", "immediate"       ],
0xa1 : [ 2, "lda", "indirectx"       ],
0xa2 : [ 2, "ldx", "immediate"       ],
0xa3 : [ 2, "lax", "indirectx", und  ],
0xa4 : [ 2, "ldy", "zeropage"        ],
0xa5 : [ 2, "lda", "zeropage"        ],
0xa6 : [ 2, "ldx", "zeropage"        ],
0xa7 : [ 2, "lax", "zeropage", und   ],
0xa8 : [ 1, "tay", "implicit"        ],
0xa9 : [ 2, "lda", "immediate"       ],
0xaa : [ 1, "tax", "implicit"        ],
0xab : [ 2, "atx", "immediate", und  ],
0xac : [ 3, "ldy", "absolute"        ],
0xad : [ 3, "lda", "absolute"        ],
0xae : [ 3, "ldx", "absolute"        ],
0xaf : [ 3, "lax", "absolute", und   ],

0xb0 : [ 2, "bcs", "relative", pcr   ],
0xb1 : [ 2, "lda", "indirecty"       ],
0xb2 : [ 1, "hlt", "implicit", und   ],
0xb3 : [ 2, "lax", "indirecty", und  ],
0xb4 : [ 2, "ldy", "zeropagex"       ],
0xb5 : [ 2, "lda", "zeropagex"       ],
0xb6 : [ 2, "ldx", "zeropagey"       ],
0xb7 : [ 2, "lax", "zeropagey", und  ],
0xb8 : [ 1, "clv", "implicit"        ],
0xb9 : [ 3, "lda", "absolutey"       ],
0xba : [ 1, "tsx", "implicit"        ],
0xbb : [ 3, "lar", "absolutey", und  ],
0xbc : [ 3, "ldy", "absolutex"       ],
0xbd : [ 3, "lda", "absolutex"       ],
0xbe : [ 3, "ldx", "absolutey"       ],
0xbf : [ 3, "lax", "absolutey", und  ],

0xc0 : [ 2, "cpy", "immediate"       ],
0xc1 : [ 2, "cmp", "indirectx"       ],
0xc2 : [ 2, "nop", "immediate", und  ],
0xc3 : [ 2, "dcp", "indirectx", und  ],
0xc4 : [ 2, "cpy", "zeropage"        ],
0xc5 : [ 2, "cmp", "zeropage"        ],
0xc6 : [ 2, "dec", "zeropage"        ],
0xc7 : [ 2, "dcp", "zeropage", und   ],
0xc8 : [ 1, "iny", "implicit"        ],
0xc9 : [ 2, "cmp", "immediate"       ],
0xca : [ 1, "dex", "implicit"        ],
0xcb : [ 2, "sbx", "immediate", und  ],
0xcc : [ 3, "cpy", "absolute"        ],
0xcd : [ 3, "cmp", "absolute"        ],
0xce : [ 3, "dec", "absolute"        ],
0xcf : [ 3, "dcp", "absolute", und   ],

0xd0 : [ 2, "bne", "relative", pcr   ],
0xd1 : [ 2, "cmp", "indirecty"       ],
0xd2 : [ 1, "hlt", "implicit", und   ],
0xd3 : [ 2, "dcp", "indirecty", und  ],
0xd4 : [ 2, "nop", "zeropagex", und  ],
0xd5 : [ 2, "cmp", "zeropagex"       ],
0xd6 : [ 2, "dec", "zeropagex"       ],
0xd7 : [ 2, "dcp", "zeropagex", und  ],
0xd8 : [ 1, "cld", "implicit"        ],
0xd9 : [ 3, "cmp", "absolutey"       ],
0xda : [ 1, "nop", "implicit", und   ],
0xdb : [ 3, "dcp", "absolutey", und  ],
0xdc : [ 3, "nop", "absolutex", und  ],
0xdd : [ 3, "cmp", "absolutex"       ],
0xde : [ 3, "dec", "absolutex"       ],
0xdf : [ 3, "dcp", "absolutex", und  ],

0xe0 : [ 2, "cpx", "immediate"       ],
0xe1 : [ 2, "sbc", "indirectx"       ],
0xe2 : [ 2, "nop", "immediate", und  ],
0xe3 : [ 2, "isc", "indirectx", und  ],
0xe4 : [ 2, "cpx", "zeropage"        ],
0xe5 : [ 2, "sbc", "zeropage"        ],
0xe6 : [ 2, "inc", "zeropage"        ],
0xe7 : [ 2, "isc", "zeropage", und   ],
0xe8 : [ 1, "inx", "implicit"        ],
0xe9 : [ 2, "sbc", "immediate"       ],
0xea : [ 1, "nop", "implicit"        ],
0xeb : [ 2, "sbc", "immediate", und  ],
0xec : [ 3, "cpx", "absolute"        ],
0xed : [ 3, "sbc", "absolute"        ],
0xee : [ 3, "inc", "absolute"        ],
0xef : [ 3, "isc", "absolute", und   ],

0xf0 : [ 2, "beq", "relative", pcr   ],
0xf1 : [ 2, "sbc", "indirecty"       ],
0xf2 : [ 1, "hlt", "implicit", und   ],
0xf3 : [ 2, "isc", "indirecty", und  ],
0xf4 : [ 2, "nop", "zeropagex", und  ],
0xf5 : [ 2, "sbc", "zeropagex"       ],
0xf6 : [ 2, "inc", "zeropagex"       ],
0xf7 : [ 2, "isc", "zeropagex", und  ],
0xf8 : [ 1, "sed", "implicit"        ],
0xf9 : [ 3, "sbc", "absolutey"       ],
0xfa : [ 1, "nop", "implicit", und   ],
0xfb : [ 3, "isc", "absolutey", und  ],
0xfc : [ 3, "nop", "absolutex", und  ],
0xfd : [ 3, "sbc", "absolutex"       ],
0xfe : [ 3, "inc", "absolutex"       ],
0xff : [ 3, "isc", "absolutex", und  ],

}

# End of processor specific code
##########################################################################
