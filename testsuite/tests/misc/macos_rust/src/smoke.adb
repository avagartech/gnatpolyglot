--  Copyright (C) 2026, AdaCore
--  SPDX-License-Identifier: GPL-3.0-or-later

package body Smoke is
   Value : int := 37;
   function Add (Left, Right : int) return int is (Left + Right);
   function Initial_Value return int is (Value);
begin
   Value := Value + 5;
end Smoke;
