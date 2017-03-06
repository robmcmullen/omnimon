##########################################################################
#
# Processor specific code

# CPU = "65816"
# Description = "Western Design Center 65816 8/16-bit microprocessor."
# DataWidth = 8/16  # 8-bit or 16-bit data depending on processor mode
# AddressWidth = 16/24  # 16-bit or 24-bit addresses depending on processor mode

# Maximum length of an instruction (for formatting purposes)
maxLength = 4

# Leadin bytes for multibyte instructions
leadInBytes = []

# Addressing mode table
# List of addressing modes and corresponding format strings for operands.
addressModeTable = {
"implicit"                : "",
"absolute"                : "${1:02X}{0:02X}",
"absolutex"               : "${1:02X}{0:02X},x",
"absolutey"               : "${1:02X}{0:02X},y",
"accumulator"             : "a",
"immediate"               : "#${0:02X}",
"indirectx"               : "(${0:02X},x)",
"indirecty"               : "(${0:02X}),y",
"indirect"                : "(${1:02X}{0:02X})",
"relative"                : "${0:04X}",
"relativelong"            : "${0:04X}",
"zeropage"                : "${0:02X}",
"zeropagex"               : "${0:02X},x",
"zeropagey"               : "${0:02X},y",
"indirectzeropage"        : "(${0:02X})",
"absoluteindexedindirect" : "(${1:02X}{0:02X},x)",
"stackrelative"           : "${0:02X},s",
"stackrelativeindirecty"  : "(${0:02X},s),y",
"absolutelong"            : "${2:02X}{1:02X}{0:02X}",
"absolutelongx"           : "${2:02X}{1:02X}{0:02X},x",
"absoluteindirectx"       : "(${1:02X}{0:02X},x)",
"absoluteindirectlong"    : "[${1:02X}{0:02X}]",
"directpageindirect"      : "(${0:02X})",
"directpageindirectlong"  : "[${0:02X}]",
"directpageindirectlongy" : "[${0:02X}],y",
"blockmove"               : "${0:02X},${1:02X}",
}

# Address modes that reference an address
# Any opcodes that use one of these address modes refer to an absolute
# address in memory, and are a candidate to be replaced by a label
labelTargets = set(["absolute", "absolutex", "absolutey", "indirect", "indirectx", "indirecty", "zeropage", "zeropagex", "zeropagey", "indirectzeropage", "absoluteindexedindirect", "absolutelong", "absolutelongx", "absoluteindirectx", "absoluteindirectlong", "directpageindirect", "directpageindirectlong", "directpageindirectlongy", "blockmove"])

jumpOpcodes = set(["jmp"])
branchModes = set(["relative", "relativelong"])
branchOpcodes = set(["jsr"])
modesExclude = set(["indirect", "absoluteindexedindirect"])
returnOpcodes = set(["rts", "rti", "brk"])

# Op Code Table
# Key is numeric opcode (possibly multiple bytes)
# Value is a list:
#   # bytes
#   mnemonic
#   addressing mode
#   flags (e.g. pcr)

# regex conversion from http://www.zophar.net/fileuploads/2/10538ivwiu/65816info.txt
# find:    ([0-9A-F]+)      ([A-Z]+)     (.+?)( +)([1-4])
# replace: 0x\1 : [ \5, "\2",  "\3"\4],
opcodeTable = {
0x00 : [ 1, "brk",  "implicit"                ],
0x01 : [ 2, "ora",  "indirectx"               ],
0x02 : [ 2, "cop",  "zeropage"                ],
0x03 : [ 2, "ora",  "stackrelative"           ],
0x04 : [ 2, "tsb",  "zeropage"                ],
0x05 : [ 2, "ora",  "zeropage"                ],
0x06 : [ 2, "asl",  "zeropage"                ],
0x07 : [ 2, "ora",  "directpageindirectlong"  ],
0x08 : [ 1, "php",  "implicit"                ],
0x09 : [ 2, "ora",  "immediate"               ],
0x0a : [ 1, "asl",  "accumulator"             ],
0x0b : [ 1, "phd",  "implicit"                ],
0x0c : [ 3, "tsb",  "absolute"                ],
0x0d : [ 3, "ora",  "absolute"                ],
0x0e : [ 3, "asl",  "absolute"                ],
0x0f : [ 4, "ora",  "absolutelong"            ],

0x10 : [ 2, "bpl",  "relative", pcr           ],
0x11 : [ 2, "ora",  "indirecty"               ],
0x12 : [ 2, "ora",  "indirectzeropage"        ],
0x13 : [ 2, "ora",  "stackrelativeindirecty"  ],
0x14 : [ 2, "trb",  "zeropage"                ],
0x15 : [ 2, "ora",  "zeropagex"               ],
0x16 : [ 2, "asl",  "zeropagex"               ],
0x17 : [ 2, "ora",  "directpageindirectlongy" ],
0x18 : [ 1, "clc",  "implicit"                ],
0x19 : [ 3, "ora",  "absolutey"               ],
0x1a : [ 1, "inc",  "accumulator"             ],
0x1b : [ 1, "tcs",  "implicit"                ],
0x1c : [ 3, "trb",  "absolute"                ],
0x1d : [ 3, "ora",  "absolutex"               ],
0x1e : [ 3, "asl",  "absolutex"               ],
0x1f : [ 4, "ora",  "absolutelongx"           ],

0x20 : [ 3, "jsr",  "absolute"                ],
0x21 : [ 2, "and",  "indirectx"               ],
0x22 : [ 4, "jsr",  "absolutelong"            ],
0x23 : [ 2, "and",  "stackrelative"           ],
0x24 : [ 2, "bit",  "zeropage"                ],
0x25 : [ 2, "and",  "zeropage"                ],
0x26 : [ 2, "rol",  "zeropage"                ],
0x27 : [ 2, "and",  "directpageindirectlong"  ],
0x28 : [ 1, "plp",  "implicit"                ],
0x29 : [ 2, "and",  "immediate"               ],
0x2a : [ 1, "rol",  "accumulator"             ],
0x2b : [ 1, "pld",  "implicit"                ],
0x2c : [ 3, "bit",  "absolute"                ],
0x2d : [ 3, "and",  "absolute"                ],
0x2e : [ 3, "rol",  "absolute"                ],
0x2f : [ 4, "and",  "absolutelong"            ],

0x30 : [ 2, "bmi",  "relative", pcr           ],
0x31 : [ 2, "and",  "indirecty"               ],
0x32 : [ 2, "and",  "indirectzeropage"        ],
0x33 : [ 2, "and",  "stackrelativeindirecty"  ],
0x34 : [ 2, "bit",  "zeropagex"               ],
0x35 : [ 2, "and",  "zeropagex"               ],
0x36 : [ 2, "rol",  "zeropagex"               ],
0x37 : [ 2, "and",  "directpageindirectlongy" ],
0x38 : [ 1, "sec",  "implicit"                ],
0x39 : [ 3, "and",  "absolutey"               ],
0x3a : [ 1, "dec",  "accumulator"             ],
0x3b : [ 1, "tsc",  "implicit"                ],
0x3c : [ 3, "bit",  "absolutex"               ],
0x3d : [ 3, "and",  "absolutex"               ],
0x3e : [ 3, "rol",  "absolutex"               ],
0x3f : [ 4, "and",  "absolutelongx"           ],

0x40 : [ 1, "rti",  "implicit"                ],
0x41 : [ 2, "eor",  "indirectx"               ],
0x42 : [ 2, "wdm",  "zeropage"                ],
0x43 : [ 2, "eor",  "stackrelative"           ],
0x44 : [ 3, "mvp",  "blockmove"               ],
0x45 : [ 2, "eor",  "zeropage"                ],
0x46 : [ 2, "lsr",  "zeropage"                ],
0x47 : [ 2, "eor",  "directpageindirectlong"  ],
0x48 : [ 1, "pha",  "implicit"                ],
0x49 : [ 2, "eor",  "immediate"               ],
0x4a : [ 1, "lsr",  "accumulator"             ],
0x4b : [ 1, "phk",  "implicit"                ],
0x4c : [ 3, "jmp",  "absolute"                ],
0x4d : [ 3, "eor",  "absolute"                ],
0x4e : [ 3, "lsr",  "absolute"                ],
0x4f : [ 4, "eor",  "absolutelong"            ],

0x50 : [ 2, "bvc",  "relative", pcr           ],
0x51 : [ 2, "eor",  "indirecty"               ],
0x52 : [ 2, "eor",  "indirectzeropage"        ],
0x53 : [ 2, "eor",  "stackrelativeindirecty"  ],
0x54 : [ 3, "mvn",  "blockmove"               ],
0x55 : [ 2, "eor",  "zeropagex"               ],
0x56 : [ 2, "lsr",  "zeropagex"               ],
0x57 : [ 2, "eor",  "directpageindirectlongy" ],
0x58 : [ 1, "cli",  "implicit"                ],
0x59 : [ 3, "eor",  "absolutey"               ],
0x5a : [ 1, "phy",  "implicit"                ],
0x5b : [ 1, "tcd",  "implicit"                ],
0x5c : [ 4, "jmp",  "absolutelong"            ],
0x5d : [ 3, "eor",  "absolutex"               ],
0x5e : [ 3, "lsr",  "absolutex"               ],
0x5f : [ 4, "eor",  "absolutelongx"           ],

0x60 : [ 1, "rts",  "implicit"                ],
0x61 : [ 2, "adc",  "indirectx"               ],
0x62 : [ 3, "per",  "absolute"                ],
0x63 : [ 2, "adc",  "stackrelative"           ],
0x64 : [ 2, "stz",  "zeropage"                ],
0x65 : [ 2, "adc",  "zeropage"                ],
0x66 : [ 2, "ror",  "zeropage"                ],
0x67 : [ 2, "adc",  "directpageindirectlong"  ],
0x68 : [ 1, "pla",  "implicit"                ],
0x69 : [ 2, "adc",  "immediate"               ],
0x6a : [ 1, "ror",  "accumulator"             ],
0x6b : [ 1, "rtl",  "implicit"                ],
0x6c : [ 3, "jmp",  "indirect"                ],
0x6d : [ 3, "adc",  "absolute"                ],
0x6e : [ 3, "ror",  "absolute"                ],
0x6f : [ 4, "adc",  "absolutelong"            ],

0x70 : [ 2, "bvs",  "relative", pcr           ],
0x71 : [ 2, "adc",  "indirecty"               ],
0x72 : [ 2, "adc",  "indirectzeropage"        ],
0x73 : [ 2, "adc",  "stackrelativeindirecty"  ],
0x74 : [ 2, "stz",  "zeropagex"               ],
0x74 : [ 2, "stz",  "zeropagex"               ],
0x75 : [ 2, "adc",  "zeropagex"               ],
0x76 : [ 2, "ror",  "zeropagex"               ],
0x77 : [ 2, "adc",  "directpageindirectlongy" ],
0x78 : [ 1, "sei",  "implicit"                ],
0x79 : [ 3, "adc",  "absolutey"               ],
0x7a : [ 1, "ply",  "implicit"                ],
0x7b : [ 1, "tdc",  "implicit"                ],
0x7c : [ 3, "jmp",  "absoluteindexedindirect" ],
0x7d : [ 3, "adc",  "absolutex"               ],
0x7e : [ 3, "ror",  "absolutex"               ],
0x7f : [ 4, "adc",  "absolutelongx"           ],

0x80 : [ 2, "bra",  "relative", pcr           ],
0x81 : [ 2, "sta",  "indirectx"               ],
0x82 : [ 3, "brl",  "relativelong", pcr       ],
0x83 : [ 2, "sta",  "stackrelative"           ],
0x84 : [ 2, "sty",  "zeropage"                ],
0x85 : [ 2, "sta",  "zeropage"                ],
0x86 : [ 2, "stx",  "zeropage"                ],
0x87 : [ 2, "sta",  "directpageindirectlong"  ],
0x88 : [ 1, "dey",  "implicit"                ],
0x89 : [ 2, "bit",  "immediate"               ],
0x8a : [ 1, "txa",  "implicit"                ],
0x8b : [ 1, "phb",  "implicit"                ],
0x8c : [ 3, "sty",  "absolute"                ],
0x8d : [ 3, "sta",  "absolute"                ],
0x8e : [ 3, "stx",  "absolute"                ],
0x8f : [ 4, "sta",  "absolutelong"            ],

0x90 : [ 2, "bcc",  "relative", pcr           ],
0x91 : [ 2, "sta",  "indirecty"               ],
0x92 : [ 2, "sta",  "indirectzeropage"        ],
0x93 : [ 2, "sta",  "stackrelativeindirecty"  ],
0x94 : [ 2, "sty",  "zeropagex"               ],
0x95 : [ 2, "sta",  "zeropagex"               ],
0x96 : [ 2, "stx",  "zeropagey"               ],
0x97 : [ 2, "sta",  "directpageindirectlongy" ],
0x98 : [ 1, "tya",  "implicit"                ],
0x99 : [ 3, "sta",  "absolutey"               ],
0x9a : [ 1, "txs",  "implicit"                ],
0x9b : [ 1, "txy",  "implicit"                ],
0x9c : [ 3, "stz",  "absolute"                ],
0x9d : [ 3, "sta",  "absolutex"               ],
0x9e : [ 3, "stz",  "absolutex"               ],
0x9f : [ 4, "sta",  "absolutelongx"           ],

0xa0 : [ 2, "ldy",  "immediate"               ],
0xa1 : [ 2, "lda",  "indirectx"               ],
0xa2 : [ 2, "ldx",  "immediate"               ],
0xa3 : [ 2, "lda",  "stackrelative"           ],
0xa4 : [ 2, "ldy",  "zeropage"                ],
0xa5 : [ 2, "lda",  "zeropage"                ],
0xa6 : [ 2, "ldx",  "zeropage"                ],
0xa7 : [ 2, "lda",  "directpageindirectlong"  ],
0xa8 : [ 1, "tay",  "implicit"                ],
0xa9 : [ 2, "lda",  "immediate"               ],
0xaa : [ 1, "tax",  "implicit"                ],
0xab : [ 1, "plb",  "implicit"                ],
0xac : [ 3, "ldy",  "absolute"                ],
0xad : [ 3, "lda",  "absolute"                ],
0xae : [ 3, "ldx",  "absolute"                ],
0xaf : [ 4, "lda",  "absolutelong"            ],

0xb0 : [ 2, "bcs",  "relative", pcr           ],
0xb1 : [ 2, "lda",  "indirecty"               ],
0xb2 : [ 2, "lda",  "indirectzeropage"        ],
0xb3 : [ 2, "lda",  "stackrelativeindirecty"  ],
0xb4 : [ 2, "ldy",  "zeropagex"               ],
0xb5 : [ 2, "lda",  "zeropagex"               ],
0xb6 : [ 2, "ldx",  "zeropagey"               ],
0xb7 : [ 2, "lda",  "directpageindirectlongy" ],
0xb8 : [ 1, "clv",  "implicit"                ],
0xb9 : [ 3, "lda",  "absolutey"               ],
0xba : [ 1, "tsx",  "implicit"                ],
0xbb : [ 1, "tyx",  "implicit"                ],
0xbc : [ 3, "ldy",  "absolutex"               ],
0xbd : [ 3, "lda",  "absolutex"               ],
0xbe : [ 3, "ldx",  "absolutey"               ],
0xbf : [ 4, "lda",  "absolutelongx"           ],

0xc0 : [ 2, "cpy",  "immediate"               ],
0xc1 : [ 2, "cmp",  "indirectx"               ],
0xc2 : [ 2, "rep",  "immediate"               ],
0xc3 : [ 2, "cmp",  "stackrelative"           ],
0xc4 : [ 2, "cpy",  "zeropage"                ],
0xc5 : [ 2, "cmp",  "zeropage"                ],
0xc6 : [ 2, "dec",  "zeropage"                ],
0xc7 : [ 2, "cmp",  "directpageindirectlong"  ],
0xc8 : [ 1, "iny",  "implicit"                ],
0xc9 : [ 2, "cmp",  "immediate"               ],
0xca : [ 1, "dex",  "implicit"                ],
0xcb : [ 1, "wai",  "implicit"                ],
0xcc : [ 3, "cpy",  "absolute"                ],
0xcd : [ 3, "cmp",  "absolute"                ],
0xce : [ 3, "dec",  "absolute"                ],
0xcf : [ 4, "cmp",  "absolutelong"            ],

0xd0 : [ 2, "bne",  "relative", pcr           ],
0xd1 : [ 2, "cmp",  "indirecty"               ],
0xd2 : [ 2, "cmp",  "indirectzeropage"        ],
0xd3 : [ 2, "cmp",  "stackrelativeindirecty"  ],
0xd4 : [ 2, "pei",  "directpageindirect"      ],
0xd5 : [ 2, "cmp",  "zeropagex"               ],
0xd6 : [ 2, "dec",  "zeropagex"               ],
0xd7 : [ 2, "cmp",  "directpageindirectlongy" ],
0xd8 : [ 1, "cld",  "implicit"                ],
0xd9 : [ 3, "cmp",  "absolutey"               ],
0xda : [ 1, "phx",  "implicit"                ],
0xdb : [ 1, "stp",  "implicit"                ],
0xdc : [ 3, "jmp",  "absoluteindirectlong"    ],
0xdd : [ 3, "cmp",  "absolutex"               ],
0xde : [ 3, "dec",  "absolutex"               ],
0xdf : [ 4, "cmp",  "absolutelongx"           ],

0xe0 : [ 2, "cpx",  "immediate"               ],
0xe1 : [ 2, "sbc",  "indirectx"               ],
0xe2 : [ 2, "sep",  "immediate"               ],
0xe3 : [ 2, "sbc",  "stackrelative"           ],
0xe4 : [ 2, "cpx",  "zeropage"                ],
0xe5 : [ 2, "sbc",  "zeropage"                ],
0xe6 : [ 2, "inc",  "zeropage"                ],
0xe7 : [ 2, "sbc",  "directpageindirectlong"  ],
0xe8 : [ 1, "inx",  "implicit"                ],
0xe9 : [ 2, "sbc",  "immediate"               ],
0xea : [ 1, "nop",  "implicit"                ],
0xeb : [ 1, "xba",  "implicit"                ],
0xec : [ 3, "cpx",  "absolute"                ],
0xed : [ 3, "sbc",  "absolute"                ],
0xee : [ 3, "inc",  "absolute"                ],
0xef : [ 4, "sbc",  "absolutelong"            ],

0xf0 : [ 2, "beq",  "relative", pcr           ],
0xf1 : [ 2, "sbc",  "indirecty"               ],
0xf2 : [ 2, "sbc",  "indirectzeropage"        ],
0xf3 : [ 2, "sbc",  "stackrelativeindirecty"  ],
0xf4 : [ 3, "pea",  "absolute"                ],
0xf5 : [ 2, "sbc",  "zeropagex"               ],
0xf6 : [ 2, "inc",  "zeropagex"               ],
0xf7 : [ 2, "sbc",  "directpageindirectlongy" ],
0xf8 : [ 1, "sed",  "implicit"                ],
0xf9 : [ 3, "sbc",  "absolutey"               ],
0xfa : [ 1, "plx",  "implicit"                ],
0xfb : [ 1, "xce",  "implicit"                ],
0xfd : [ 3, "sbc",  "absolutex"               ],
0xfe : [ 3, "inc",  "absolutex"               ],
0xff : [ 4, "sbc",  "absolutelongx"           ],
}

# End of processor specific code
##########################################################################
