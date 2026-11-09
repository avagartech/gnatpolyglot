--  Copyright (C) 2026, AdaCore
--  SPDX-License-Identifier: GPL-3.0-or-later

with Interfaces.C; use Interfaces.C;
with GNATpolyglot.Ada.Arrays.Native;
with GNATpolyglot.Ada.Strings;

package Smoke is
   function Add (Left, Right : int) return int
     with Export, Convention => C, External_Name => "macos_smoke_add";
   function Initial_Value return int
     with Export, Convention => C, External_Name => "macos_smoke_initial";
end Smoke;
