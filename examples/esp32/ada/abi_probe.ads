--  Copyright (C) 2026, AdaCore
--  SPDX-License-Identifier: GPL-3.0-or-later

pragma Restrictions (No_Elaboration_Code);
pragma Restrictions (No_Allocators, No_Implicit_Heap_Allocations, No_Tasking);
with Interfaces; use Interfaces;

package ABI_Probe with Pure is
   function Checked_Add
     (Left, Right : Integer_32; Total : in out Integer_32) return Integer_32
     with Export, Convention => C, External_Name => "polyglot_checked_add";

   function Fold_64 (Value : Unsigned_64) return Unsigned_64
     with Export, Convention => C, External_Name => "polyglot_fold_64";

   function Scale_32 (Value : IEEE_Float_32) return IEEE_Float_32
     with Export, Convention => C, External_Name => "polyglot_scale_32";

   function Scale_64 (Value : IEEE_Float_64) return IEEE_Float_64
     with Export, Convention => C, External_Name => "polyglot_scale_64";

   function Negate_16 (Value : Integer_16) return Integer_16
     with Export, Convention => C, External_Name => "polyglot_negate_16";
end ABI_Probe;
