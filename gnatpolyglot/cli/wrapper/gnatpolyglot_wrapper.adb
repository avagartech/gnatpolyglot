--
--  Copyright (C) 2025-2026, AdaCore
--  SPDX-License-Identifier: GPL-3.0-or-later
--

with Ada.Command_Line;        use Ada.Command_Line;
with Ada.Characters.Handling; use Ada.Characters.Handling;
with Ada.Directories;
with Ada.Environment_Variables;
with Ada.Strings.Fixed;       use Ada.Strings.Fixed;
with Ada.Text_IO;             use Ada.Text_IO;
with GNAT.OS_Lib;             use GNAT.OS_Lib;

procedure GNATpolyglot_Wrapper is

   Args   : Argument_List (1 .. Argument_Count);
   Status : Boolean;
   S      : String_Access;

   function Executable_Location return String;
   --  Return the name of the parent directory where the executable is stored
   --  (so if you are running "prefix"/bin/gnatpolyglot, you would get "prefix").
   --  A special case is done for "bin" directories, which are skipped.
   --  The returned directory always ends up with a directory separator.

   function Locate_Exec_In_Libexec (Exec : String) return String_Access;
   --  Locate Exec in <prefix>/libexec/gnatpolyglot/. The function
   --  allocates memory that needs to be freed by the caller.

   procedure Setup_Search_Paths;
   --  Set the GNATPOLYGLOT_RUNTIME environment variable to the installation's
   --  runtime unless it was already set. Additionally, extends dynamic library
   --  search paths (PATH for Windows, LD_LIBRARY_PATH on Linux, and
   --  DYLD_LIBRARY_PATH on macOS) to point on
   --  $PREFIX/lib/gnatpolyglot, to allow the worker processe that relies on
   --  dynamic libraries to find its dependencies without requiring users to
   --  explicitly set these paths.

   -------------------------
   -- Executable_Location --
   -------------------------

   function Executable_Location return String is
      Exec_Name : constant String := Ada.Command_Line.Command_Name;

      function Get_Install_Dir (S : String) return String;
      --  S is the executable name preceeded by the absolute or relative path,
      --  e.g. "c:\usr\bin\gnatpolyglot.exe" or "..\bin\gnatpolyglot". Returns
      --  the absolute or relative directory where "bin" lies (in the example
      --  "C:\usr" or ".."). If the executable is not a "bin" directory, return
      --  "".

      function Is_Directory_Separator (C : Character) return Boolean;
      --  Return True if C is a directory separator

      ---------------------
      -- Get_Install_Dir --
      ---------------------

      function Get_Install_Dir (S : String) return String is
         Exec      : constant String :=
           Normalize_Pathname (S, Resolve_Links => True);
         Path_Last : Integer := 0;

      begin
         for J in reverse Exec'Range loop
            if Is_Directory_Separator (Exec (J)) then
               Path_Last := J - 1;
               exit;
            end if;
         end loop;

         --  If we are not in a bin/ directory

         if Path_Last < Exec'First + 2
           or else To_Lower (Exec (Path_Last - 2 .. Path_Last)) /= "bin"
           or else (Path_Last - 3 >= Exec'First
                    and then not Is_Directory_Separator (Exec (Path_Last - 3)))
         then
            return Exec (Exec'First .. Path_Last) & Directory_Separator;

         else
            --  Skip bin/, but keep the last directory separator

            return Exec (Exec'First .. Path_Last - 3);
         end if;
      end Get_Install_Dir;

      ----------------------------
      -- Is_Directory_Separator --
      ----------------------------

      function Is_Directory_Separator (C : Character) return Boolean is
      begin
         --  In addition to the default directory_separator allow the '/' to
         --  act as separator.

         return C = Directory_Separator or else C = '/';
      end Is_Directory_Separator;

      --  Start of processing for Executable_Location

   begin
      --  First determine if a path prefix was placed in front of the
      --  executable name.

      for J in reverse Exec_Name'Range loop
         if Is_Directory_Separator (Exec_Name (J)) then
            return Get_Install_Dir (Exec_Name);
         end if;
      end loop;

      --  If you are here, the user has typed the executable name with no
      --  directory prefix.

      declare
         Ex  : String_Access := Locate_Exec_On_Path (Exec_Name);
         Dir : constant String := Get_Install_Dir (Ex.all);

      begin
         Free (Ex);
         return Dir;
      end;
   end Executable_Location;

   -----------------
   -- Locate_Exec --
   -----------------

   function Locate_Exec_In_Libexec (Exec : String) return String_Access is
      use Ada.Directories;

      Suffix  : String_Access := Get_Target_Executable_Suffix;
      Result  : constant String :=
        Compose
          (Compose (Compose (Executable_Location, "libexec"), "gnatpolyglot"),
           Exec);
      Is_Exec : constant Boolean := Is_Executable_File (Result & Suffix.all);

   begin
      Free (Suffix);
      return (if Is_Exec then new String'(Result) else null);
   end Locate_Exec_In_Libexec;

   ------------------------
   -- Setup_Search_Paths --
   ------------------------

   procedure Setup_Search_Paths is
      use Ada;
      use Ada.Directories;

      procedure Add_Path (Env_Var : String; Path : String);

      --------------
      -- Add_Path --
      --------------

      procedure Add_Path (Env_Var : String; Path : String) is
      begin
         if Environment_Variables.Exists (Env_Var) then
            Environment_Variables.Set
              (Env_Var,
               Path & Path_Separator & Environment_Variables.Value (Env_Var));
         else
            Environment_Variables.Set (Env_Var, Path);
         end if;
      end Add_Path;

      Prefix           : constant String := Executable_Location;
      Lib_Polyglot     : constant String :=
        Compose (Compose (Prefix, "lib"), "gnatpolyglot");
      Share_Polyglot   : constant String :=
        Compose (Compose (Prefix, "share"), "gnatpolyglot");
      Runtime_Location : constant String :=
        Compose (Share_Polyglot, "runtimes");
   begin
      Add_Path ("LD_LIBRARY_PATH", Lib_Polyglot);
      Add_Path ("DYLD_LIBRARY_PATH", Lib_Polyglot);
      Add_Path ("PATH", Lib_Polyglot);
      if not Environment_Variables.Exists ("GNATPOLYGLOT_RUNTIME") then
         Environment_Variables.Set ("GNATPOLYGLOT_RUNTIME", Runtime_Location);
      end if;
   end Setup_Search_Paths;

begin
   -- Locate the gnatpolyglot executable in libexec
   S := Locate_Exec_In_Libexec ("gnatpolyglot");

   if S = null then
      Put_Line ("error: gnatpolyglot not found");
      Set_Exit_Status (Failure);
      return;
   end if;

   -- Set the environment to get the shared libs dependencies
   Setup_Search_Paths;

   for I in 1 .. Argument_Count loop
      Args (I) := new String'(Argument (I));
   end loop;

   Spawn (S.all, Args, Status);
   Set_Exit_Status (if Status then Success else Failure);
end GNATpolyglot_Wrapper;

