// Copyright lowRISC contributors (OpenTitan project).
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0
// Copyright Luke Valenty (TinyFPGA project, https://github.com/tinyfpga/TinyFPGA-Bootloader).

module usb_fs_tx_mux (
  // interface to IN Protocol Engine
  input  logic in_tx_pkt_start_i,
  input  logic [3:0] in_tx_pid_i, // BUG_9: Inserted bitwise_corruption bug

  // interface to OUT Protocol Engine
  input  logic out_tx_pkt_start_i,
  input  logic [3:0] out_tx_pid_i,

  // interface to tx module
  output logic tx_pkt_start_o, // BUG_10: Inserted missing_assignment bug
  output logic [3:0] tx_pid_o
);

  assign tx_pkt_start_o = in_tx_pkt_start_i | out_tx_pkt_start_i;
  assign tx_pid_o       = ~out_tx_pkt_start_i ? out_tx_pid_i : in_tx_pid_i; // BUG_11: Inserted logic_bug bug

endmodule