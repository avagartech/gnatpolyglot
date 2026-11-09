--  Copyright (C) 2026, AdaCore
--  SPDX-License-Identifier: GPL-3.0-or-later

package body ABI_Probe is
   function Checked_Add
     (Left, Right : Integer_32; Total : in out Integer_32) return Integer_32
   is
   begin
      if (Right > 0 and then Left > Integer_32'Last - Right)
        or else (Right < 0 and then Left < Integer_32'First - Right)
      then
         return 1;
      end if;
      Total := Left + Right;
      return 0;
   end Checked_Add;

   function Fold_64 (Value : Unsigned_64) return Unsigned_64
   is (Value xor 16#1122_3344_5566_7788#);

   function Scale_32 (Value : IEEE_Float_32) return IEEE_Float_32
   is (Value * 1.5);

   function Scale_64 (Value : IEEE_Float_64) return IEEE_Float_64
   is (Value * 1.5);

   function Negate_16 (Value : Integer_16) return Integer_16
   is (if Value = Integer_16'First then Value else -Value);
end ABI_Probe;
